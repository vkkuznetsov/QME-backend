import json
from pathlib import Path

import pandas as pd
from fastapi import UploadFile
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import PROJECT_PATH
from backend.database.database import db_session, recreate_db
from backend.database.models.elective import Elective
from backend.database.models.group import Group, Teacher, group_teacher
from backend.database.models.student import Student
from backend.database.models.student import student_group
from backend.logic.services.log_service.orm import DatabaseLogger
from backend.utils.time_measure import time_log

name = __name__
log = DatabaseLogger(name)


class AllFileParser:
    def __init__(self, file: UploadFile):
        self.file = file
        self.raw_df = None
        self.filtered_df = None

    async def __call__(self):
        await self.reset_database()
        await self.read_file()
        await self.parse_data_frame()

    @staticmethod
    async def reset_database():
        saved_tables = ['journal', 'manager', 'logs']
        await recreate_db(saved_tables)
        log.info("База данных инициализирована.")

    async def read_file(self):
        excel_file = pd.ExcelFile(self.file.file)
        self.students_df = excel_file.parse("result")
        self.free_spots_df = excel_file.parse("Лист3")

    @time_log(name)
    @db_session
    async def parse_data_frame(self, db: AsyncSession):
        await insert_student_and_electives(self.students_df, db)
        await link_groups(self.students_df, db)
        await add_description_to_elective(db)
        await add_cluster(db)
        await update_type_and_free_spots(self.free_spots_df, db)


@time_log(name)
async def insert_student_and_electives(students_without_expulsion: pd.DataFrame, session: AsyncSession):
    unique_students = students_without_expulsion.drop_duplicates(subset=['email']).to_dict(orient="records")
    unique_electives = students_without_expulsion.drop_duplicates(subset=['РМУП название']).to_dict(orient='records')
    unique_groups = students_without_expulsion.drop_duplicates(subset=['Группа название']).to_dict(orient='records')

    raw_teachers = students_without_expulsion['Сотрудники'].dropna().tolist()
    teacher_names = set()
    for entry in raw_teachers:
        for name in str(entry).split(','):
            clean_name = name.strip()
            if clean_name:
                teacher_names.add(clean_name)

    teacher_objects = [Teacher(fio=name) for name in teacher_names]

    student_objects = [
        Student(
            fio=student['Студент'],
            email=student['email'],
            sp_code=student['Специальность'],
            sp_profile=student['Профиль'],
            potok=student['Поток']
        )
        for student in unique_students
    ]
    elective_objects = [
        Elective(name=elective['РМУП название'])
        for elective in unique_electives
    ]
    groups_objects = [
        Group(
            name=group['Группа название'],
            time_interval=None if pd.isna(group['Время проведения']) else group['Время проведения'],
            day=None if pd.isna(group['День недели']) else group['День недели']
        )
        for group in unique_groups
    ]
    session.add_all(student_objects)
    session.add_all(elective_objects)
    session.add_all(groups_objects)
    session.add_all(teacher_objects)

    await session.commit()
    log.error('закончили первую часть')


@time_log(name)
async def link_groups(students_without_expulsion: pd.DataFrame, session: AsyncSession):
    # Загружаем объекты
    student_result = await session.execute(select(Student))
    student_dict = {s.email: s for s in student_result.scalars()}

    elective_result = await session.execute(select(Elective))
    elective_dict = {e.name: e for e in elective_result.scalars()}

    group_result = await session.execute(select(Group))
    group_dict = {g.name: g for g in group_result.scalars()}

    teacher_result = await session.execute(select(Teacher))
    teacher_dict = {t.fio: t for t in teacher_result.scalars()}

    student_group_links = []
    groups_to_update = []
    group_teacher_links = []

    for _, row in students_without_expulsion.iterrows():
        student_email = row['email']
        elective_name = row['РМУП название']
        group_name = row['Группа название']
        teacher_field = row.get('Сотрудники')

        student = student_dict.get(student_email)
        elective = elective_dict.get(elective_name)
        group = group_dict.get(group_name)

        # Связываем студента с группой
        if student and group:
            student_group_links.append({
                "student_id": student.id,
                "group_id": group.id
            })

        # Устанавливаем elective_id
        if group and elective and group.elective_id is None:
            group.elective_id = elective.id
            groups_to_update.append(group)

        # Привязываем преподавателей к группе
        if group and pd.notna(teacher_field):
            for name in str(teacher_field).split(','):
                fio = name.strip()
                teacher = teacher_dict.get(fio)
                if teacher:
                    group_teacher_links.append({
                        "group_id": group.id,
                        "teacher_id": teacher.id
                    })

    session.add_all(groups_to_update)

    stmt_students = insert(student_group).values(student_group_links).on_conflict_do_nothing()
    await session.execute(stmt_students)

    stmt_teachers = insert(group_teacher).values(group_teacher_links).on_conflict_do_nothing()
    await session.execute(stmt_teachers)

    await session.commit()


@time_log(name)
async def add_description_to_elective(db: AsyncSession):
    file_path = Path(PROJECT_PATH) / 'data' / 'parsed_questions.xlsx'
    df = pd.read_excel(file_path)
    excel_data = df.set_index('Название').to_dict(orient='index')

    optional_columns = {
        'Ссылка на МУП': 'modeus_link',
        'Описание расширенное': 'description',
        'Полный текст образовательного результата': 'text',
        'Вопросы': 'questions'
    }

    available_columns = {
        excel_col: model_field
        for excel_col, model_field in optional_columns.items()
        if excel_col in df.columns
    }

    result = await db.execute(select(Elective))
    electives = result.scalars().all()

    update_mappings = []
    for elective in electives:
        row_data = excel_data.get(elective.name)
        if not row_data:
            log.warning(f"Для электива '{elective.name}' нет данных в файле")
            continue

        mapping = {'id': elective.id}
        has_changes = False
        for excel_col, model_field in available_columns.items():
            value = row_data.get(excel_col)
            if pd.notna(value):
                mapping[model_field] = value
                has_changes = True

        if has_changes:
            update_mappings.append(mapping)

    if update_mappings:
        await db.execute(
            update(Elective),
            update_mappings
        )
        await db.commit()


@time_log(name)
async def add_cluster(db: AsyncSession):
    """Обновляет поле cluster.
    - Если в JSON найдено соответствие, выставляет его.
    - Если соответствия нет и cluster всё ещё NULL, присваивает «Без области знаний».
    """
    json_path = Path(PROJECT_PATH) / "data" / "courses_clusters.json"

    with open(json_path, "r", encoding="utf-8") as f:
        clusters_data = json.load(f)

    cluster_mapping = {item["name"]: item["cluster"] for item in clusters_data}

    result = await db.execute(select(Elective))
    electives = result.scalars().all()

    update_mappings = []
    for elective in electives:
        if elective.cluster is not None:
            # уже установлен – пропускаем
            continue

        new_cluster = cluster_mapping.get(elective.name, "Без области знаний")
        update_mappings.append({"id": elective.id, "cluster": new_cluster})

    if update_mappings:
        await db.execute(update(Elective), update_mappings)
        await db.commit()


@time_log(name)
async def update_type_and_free_spots(df: pd.DataFrame, session: AsyncSession):
    # Загружаем уже созданные группы с отношением к студентам
    group_result = await session.execute(select(Group).options(selectinload(Group.students)))
    group_dict = {g.name: g for g in group_result.scalars()}

    for _, row in df.iterrows():
        group_name = row['Группа название']
        group = group_dict.get(group_name)

        if group:
            if pd.notna(row['Л']):
                group_type = "Лекции"
                free_spots = int(row['Л'])
            elif pd.notna(row['ЛБ']):
                group_type = "Лабораторные"
                free_spots = int(row['ЛБ'])
            elif pd.notna(row['П']):
                group_type = "Практики"
                free_spots = int(row['П'])
            else:
                continue  # Если все три поля пустые — пропускаем

            group.type = group_type
            group.free_spots = free_spots

            group.init_usage = len(group.students)
            group.capacity = group.init_usage + group.free_spots

    await session.commit()
