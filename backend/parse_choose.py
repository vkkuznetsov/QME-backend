import io
import json
import time
import asyncio
from pathlib import Path

import pandas as pd

from sqlalchemy import select
from sqlalchemy import exists
from sqlalchemy.orm import joinedload

from backend.database.database import Base, db_session
from backend.database.models.group import Group
from backend.database.models.student import Student
from backend.database.models.elective import Elective
from backend.database.models.student import student_group

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker


async def reset_database(engine: AsyncEngine):
    async with engine.begin() as conn:
        print("Удаление всех таблиц...")
        await conn.run_sync(Base.metadata.drop_all)
        print("Создание таблиц...")
        await conn.run_sync(Base.metadata.create_all)
    print("База данных инициализирована.")


def get_data_frame(df: pd.DataFrame) -> pd.DataFrame:
    return df[df['Дата и причина отчисления'].isna()]


async def parse_and_insert_data_with_pandas(students_without_expulsion: pd.DataFrame, session: AsyncSession):
    for _, row in students_without_expulsion.iterrows():

        student_fio = row['Студент ФИО']
        student_email = row['email']
        sp_code = row['Код специальности']
        sp_profile = row['Профиль спецальности']
        potok = row['Поток обучения']

        elective_name = row['РМУП название']

        result = await session.execute(select(Student).filter_by(email=student_email))
        student = result.scalars().first()
        if not student:
            student = Student(
                fio=student_fio,
                email=student_email,
                sp_code=sp_code,
                sp_profile=sp_profile,
                potok=potok,
            )
            session.add(student)
            await session.flush()
        result = await session.execute(select(Elective).filter_by(name=elective_name))
        elective = result.scalars().first()
        if not elective:
            elective = Elective(name=elective_name)
            session.add(elective)

    await session.commit()


async def parse_and_insert_data_with_pandas2(students_without_expulsion: pd.DataFrame, session: AsyncSession):
    count = 0
    for _, row in students_without_expulsion.iterrows():
        student_email = row['email']
        elective_name = row['РМУП название']

        result = await session.execute(
            select(Student)
            .options(joinedload(Student.groups))
            .filter_by(email=student_email)
        )
        student = result.scalars().first()

        result = await session.execute(
            select(Elective)
            .options(joinedload(Elective.groups))
            .filter_by(name=elective_name)
        )
        elective = result.scalars().first()

        group_type = None

        for group_field, group_type_name in [
            ('Лекции', 'Лекции'),
            ('Практики', 'Практики'),
            ('Лабораторные', 'Лабораторные'),
            ('Консультации', 'Консультации'),
        ]:
            if pd.notna(row[group_field]):
                group_type = group_type_name
                break
        if group_type is not None:
            group_name = row[f'{group_type}']
            result = await session.execute(select(Group).filter_by(name=group_name, type=group_type))
            group = result.scalars().first()
            if not group:
                group = Group(name=group_name, type=group_type, capacity=30)
                elective.groups.append(group)
                student.groups.append(group)
                session.add(group)
            else:
                stmt = select(
                    exists().where(
                        (student_group.c.student_id == student.id) &
                        (student_group.c.group_id == group.id)
                    )
                )

                exists_result = await session.execute(stmt)
                link_exists = exists_result.scalar()

                if not link_exists:
                    elective.groups.append(group)
                    student.groups.append(group)
                    session.add(group)
        else:
            count += 1

    await session.commit()
    print(count)


async def parse_file(file):
    contents = await file.read()
    byttes = io.BytesIO(contents)
    df = pd.read_excel(byttes)

    filtered_df = get_data_frame(df)
    start_time = time.time()
    from backend.database.database import engine
    await reset_database(engine)

    await parse_data_frame(filtered_df)

    end = time.time() - start_time
    print(f"{end}")


async def add_data_to_elective_from_xlsx(db: AsyncSession):
    try:
        file_path = r'C:\Users\vik\Desktop\PROJECT\QME-backend\backend\data\parsed_questions.xlsx'
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


from sqlalchemy import update, and_


async def add_cluster(db: AsyncSession):
    """Добавляет данные о кластерах из JSON файла только для тех записей, где cluster не задан"""
    json_path = r'C:\Users\vik\Desktop\PROJECT\QME-backend\backend\data\courses_clusters.json'

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


@db_session
async def parse_data_frame(filtered_df, db: AsyncSession):
    t1 = time.time()
    await parse_and_insert_data_with_pandas(filtered_df, db)
    t2 = time.time()
    await parse_and_insert_data_with_pandas2(filtered_df, db)
    t3 = time.time()
    await add_data_to_elective_from_xlsx(db)
    t4 = time.time()
    await add_cluster(db)
    t5 = time.time()
    print(t2 - t1)
    print(t3 - t2)
    print(t4 - t3)
    print(t5 - t4)
