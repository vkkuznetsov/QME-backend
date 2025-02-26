import io
import json
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from sqlalchemy.dialects.postgresql import insert
from backend.config import PROJECT_PATH
from backend.database.database import Base, db_session
from backend.database.database import engine
from backend.database.models.elective import Elective
from backend.database.models.group import Group
from backend.database.models.student import Student
from backend.database.models.student import student_group


async def reset_database(engine: AsyncEngine):
    async with engine.begin() as conn:
        print("Удаление всех таблиц...")
        await conn.run_sync(Base.metadata.drop_all)
        print("Создание таблиц...")
        await conn.run_sync(Base.metadata.create_all)
    print("База данных инициализирована.")


def get_data_frame(df: pd.DataFrame) -> pd.DataFrame:
    return df[df['Дата и причина отчисления'].isna()]


async def insert_student_and_electives(students_without_expulsion: pd.DataFrame, session: AsyncSession):
    unique_students = students_without_expulsion.drop_duplicates(subset=['email'])
    unique_electives = students_without_expulsion.drop_duplicates(subset=['РМУП название'])

    students_data = unique_students.to_dict(orient='records')
    electives_data = unique_electives.to_dict(orient='records')

    student_objects = [
        Student(
            fio=student['Студент ФИО'],
            email=student['email'],
            sp_code=student['Код специальности'],
            sp_profile=student['Профиль спецальности'],
            potok=student['Поток обучения']
        )
        for student in students_data
    ]

    elective_objects = [
        Elective(name=elective['РМУП название'])
        for elective in electives_data
    ]

    session.add_all(student_objects)
    session.add_all(elective_objects)

    await session.commit()


async def parse_and_insert_data_with_pandas2(students_without_expulsion: pd.DataFrame, session: AsyncSession):
    student_result = await session.execute(select(Student))
    student_dict = {s.email: s for s in student_result.scalars()}

    elective_result = await session.execute(select(Elective))
    elective_dict = {e.name: e for e in elective_result.scalars()}

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

        if not student or not elective:
            continue

        if group_name not in gr_set:
            group = Group(name=group_name, type=group_type, capacity=30, elective=elective)
            new_groups.append(group)
            gr_set[group_name] = group_id_counter
            group_id_counter += 1

        student_group_links.append({"student_id": student.id, "group_id": gr_set[group_name]})

    session.add_all(new_groups)
    await session.flush()

    if student_group_links:
        stmt = insert(student_group).values(student_group_links).on_conflict_do_nothing()
        await session.execute(stmt)

    await session.commit()


async def parse_file(file):
    contents = await file.read()
    byttes = io.BytesIO(contents)
    df = pd.read_excel(byttes)

    filtered_df = get_data_frame(df)
    start_time = time.time()

    await reset_database(engine)

    await parse_data_frame(filtered_df)

    end = time.time() - start_time
    print(f"{end}")


async def add_data_to_elective_from_xlsx(db: AsyncSession):
    try:
        file_path = Path(PROJECT_PATH) / 'data' / 'parsed_questions.xlsx'
        df = pd.read_excel(file_path, engine='openpyxl')

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

        updated_count = 0
        for elective in electives:
            row_data = excel_data.get(elective.name)

            if not row_data:
                print(f"Предупреждение: Для электива '{elective.name}' нет данных в файле")
                continue

            has_changes = False

            for excel_col, model_field in available_columns.items():
                value = row_data.get(excel_col)

                if pd.notna(value):
                    current_value = getattr(elective, model_field)
                    if current_value != value:
                        setattr(elective, model_field, value)
                        has_changes = True
                else:
                    print(f"Предупреждение: Пустое значение для '{excel_col}' у электива '{elective.name}'")

            if has_changes:
                updated_count += 1
                await db.commit()

        print(f"Всего обработано элективов: {len(electives)}")
        print(f"Обновлено записей: {updated_count}")

    except Exception as e:
        print(f"Критическая ошибка: {str(e)}")
        await db.rollback()
    finally:
        await db.close()


async def add_cluster(db: AsyncSession):
    """Добавляет данные о кластерах из JSON файла только для тех записей, где cluster не задан"""
    json_path = Path(PROJECT_PATH) / 'data' / 'courses_clusters.json'

    with open(json_path, "r", encoding="utf-8") as f:
        clusters_data = json.load(f)

    cluster_mapping = {item["name"]: item["cluster"] for item in clusters_data}

    result = await db.execute(
        select(Elective).where(Elective.cluster.is_(None))
    )
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


@db_session
async def parse_data_frame(filtered_df, db: AsyncSession):
    t1 = time.time()
    await insert_student_and_electives(filtered_df, db)
    t2 = time.time()
    print(t2 - t1)

    df_with_normal_groups, df_broken_groups = filter_groups_df(filtered_df)
    print('Rabienie')
    print(time.time() - t2)
    await parse_and_insert_data_with_pandas2(df_with_normal_groups, db)
    t3 = time.time()
    await add_data_to_elective_from_xlsx(db)
    t4 = time.time()
    await add_cluster(db)
    t5 = time.time()

    print(t3 - t2)
    print(t4 - t3)
    print(t5 - t4)
