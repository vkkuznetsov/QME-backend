import asyncio
import time

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker

from sqlalchemy import select

from backend.database.models.student import Student
from backend.database.models.group import Group
from backend.database.models.elective import Elective
from backend.database.database import Base
from backend.database.models.student import student_group

from sqlalchemy.orm import joinedload
from sqlalchemy import exists

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


async def main():
    filename = r'C:\Users\vik\Desktop\PROJECT\parsing\data\choose.xlsx'
    df = pd.read_excel(filename)
    filtered_df = get_data_frame(df)
    start_time = time.time()
    from backend.database.database import DATABASE_URL
    engine = create_async_engine(DATABASE_URL, echo=False)

    await reset_database(engine)

    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        await parse_and_insert_data_with_pandas(filtered_df, session)
        await parse_and_insert_data_with_pandas2(filtered_df, session)
    end = time.time() - start_time
    print(f"{end}")

if __name__ == "__main__":
    asyncio.run(main())
