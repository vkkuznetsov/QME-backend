import json
from pathlib import Path

import pandas as pd
from fastapi import UploadFile
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.dialects.postgresql import insert
from backend.config import PROJECT_PATH
from backend.database.database import Base, db_session
from backend.database.database import engine
from backend.database.models.elective import Elective
from backend.database.models.group import Group
from backend.database.models.student import Student
from backend.database.models.student import student_group

from backend.logic.services.log_service.orm import DatabaseLogger
from backend.utils.time_measure import time_log
name = __name__
log = DatabaseLogger(name)


class ChooseFileParser:
    def __init__(self, file: UploadFile, *, reset: bool = False):
        self.file = file
        self.reset = reset
        self.db_engine = engine
        self.raw_df = None
        self.filtered_df = None

    async def __call__(self):
        await self.read_file()
        await self.filter_na()

        if self.reset:
            await self.reset_database()
        await self.parse_data_frame()

    async def read_file(self):
        self.raw_df = pd.read_excel(self.file.file)

    async def filter_na(self) -> None:
        self.filtered_df = self.raw_df[self.raw_df['Дата и причина отчисления'].isna()]

    @staticmethod
    async def reset_database():
        preserved_table_names = ['journal','manager','logs']
        tables_to_drop = [table for table in Base.metadata.sorted_tables if table.name not in preserved_table_names]
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=tables_to_drop)
            await conn.run_sync(Base.metadata.create_all)
        log.info("База данных инициализирована.")

    @time_log(name)
    @db_session
    async def parse_data_frame(self, db: AsyncSession):
        await insert_student_and_electives(self.filtered_df, db, skip_existing_electives=not self.reset)
        df_with_normal_groups, df_broken_groups = filter_groups_df(self.filtered_df)
        await insert_groups(df_with_normal_groups, db)
        await add_description_to_elective(db)
        await add_cluster(db)


@time_log(name)
async def insert_student_and_electives(students_without_expulsion: pd.DataFrame, session: AsyncSession, *, skip_existing_electives: bool = False):
    unique_students = students_without_expulsion.drop_duplicates(subset=['email']).to_dict(orient="records")
    unique_electives = students_without_expulsion.drop_duplicates(subset=['РМУП название']).to_dict(orient='records')

    if skip_existing_electives:
        existing_electives = await session.execute(select(Elective.name))
        existing_elective_names = set(existing_electives.scalars().all())
        unique_electives = [e for e in unique_electives if e['РМУП название'] not in existing_elective_names]

    student_objects = [
        Student(
            fio=student['Студент ФИО'],
            email=student['email'],
            sp_code=student['Код специальности'],
            sp_profile=student['Профиль спецальности'],
            potok=student['Поток обучения']
        )
        for student in unique_students
    ]

    elective_objects = [
        Elective(name=elective['РМУП название'])
        for elective in unique_electives if elective['РМУП название'] != "Возможно не участвовал в выборе"
    ]

    session.add_all(student_objects)
    session.add_all(elective_objects)

    await session.commit()


@time_log(name)
async def insert_groups(students_without_expulsion: pd.DataFrame, session: AsyncSession):
    student_result = await session.execute(select(Student))
    student_dict = {s.email: s for s in student_result.scalars()}

    elective_result = await session.execute(select(Elective))
    elective_dict = {e.name: e for e in elective_result.scalars()}

    # Извлекаем уже существующие группы из базы перед началом обработки строк
    group_result = await session.execute(select(Group))
    existing_groups = {(g.name, g.elective_id): g for g in group_result.scalars()}

    gr_set = {}
    new_groups = []
    student_group_links = []
    group_id_counter = 1

    for _, row in students_without_expulsion.iterrows():
        student_email = row['email']
        elective_name = row['РМУП название']
        group_type = row['group_type']
        group_name = row['group_name']

        student = student_dict.get(student_email)
        elective = elective_dict.get(elective_name)

        key = (group_name, elective.id)
        if key not in existing_groups and group_name not in gr_set:
            group = Group(name=group_name, type=group_type, capacity=30, elective=elective)
            new_groups.append(group)
            gr_set[group_name] = group_id_counter
            group_id_counter += 1

    session.add_all(new_groups)
    await session.flush()

    # Обновляем existing_groups после вставки новых групп
    group_result = await session.execute(select(Group))
    existing_groups = {(g.name, g.elective_id): g for g in group_result.scalars()}

    for _, row in students_without_expulsion.iterrows():
        student_email = row['email']
        elective_name = row['РМУП название']
        group_name = row['group_name']
        student = student_dict.get(student_email)
        elective = elective_dict.get(elective_name)
        group = existing_groups.get((group_name, elective.id))
        if group:
            student_group_links.append({"student_id": student.id, "group_id": group.id})

    if student_group_links:
        stmt = insert(student_group).values(student_group_links).on_conflict_do_nothing()
        await session.execute(stmt)

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
    """Добавляет данные о кластерах из JSON файла только для тех записей, где cluster не задан"""
    json_path = Path(PROJECT_PATH) / 'data' / 'courses_clusters.json'

    with open(json_path, "r", encoding="utf-8") as f:
        clusters_data = json.load(f)

    cluster_mapping = {item["name"]: item["cluster"] for item in clusters_data}

    result = await db.execute(select(Elective))
    electives = result.scalars().all()

    updated_count = 0
    for elective in electives:
        if elective.name in cluster_mapping:
            await db.execute(
                update(Elective)
                .where(and_(
                    Elective.id == elective.id,
                    Elective.cluster.is_(None)
                ))
                .values(cluster=cluster_mapping[elective.name])
            )
            updated_count += 1

    await db.commit()


@time_log(name)
def filter_groups_df(filtered_df: pd.DataFrame):
    group_columns = ['Лекции', 'Практики', 'Лабораторные', 'Консультации']
    df = filtered_df.copy()
    temp = df[group_columns]

    mask = temp.notna()

    df['group_type'] = mask.idxmax(axis=1)
    df['group_type'] = df['group_type'].where(mask.any(axis=1), None)

    df['group_name'] = temp.bfill(axis=1).iloc[:, 0]
    df['group_name'] = df['group_name'].where(mask.any(axis=1), None)

    determined_df = df[df['group_type'].notna()].copy()
    undetermined_df = df[df['group_type'].isna()].copy()

    return determined_df, undetermined_df
