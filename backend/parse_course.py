import pandas as pd
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import db_session
from sqlalchemy.orm import selectinload

from backend.database.models.group import Group, Teacher

from logging import getLogger
from backend.utils.time_measure import time_log

name = __name__
log = getLogger(name)


class ElectiveFileParser:
    def __init__(self, file: UploadFile):
        self.file = file
        self.raw_df = None
        self.filtered_df = None

    async def __call__(self):
        await self.read_file()
        await self.parse_file()

    @time_log(name)
    async def read_file(self):
        excel_file = pd.ExcelFile(self.file.file)
        schedule_df = excel_file.parse("Расписание")
        self.filtered_df = schedule_df

    @time_log(name)
    @db_session
    async def parse_file(self, db: AsyncSession):
        final_d = set()
        for _, row in self.filtered_df.iterrows():
            new_data = (
                row['РМУП название'],
                row['Команда название'],
                row['свободных мест в команде'],
                row['День недели'],
                row['Время проведения'],
                row['Сотрудники в команде']
            )
            final_d.add(new_data)

        # Первый этап: обработка учителей
        teacher_map = {}  # Словарь для хранения соответствия имени учителя и его объекта
        for _, _, _, _, _, teacher in final_d:
            teachers_list = [t.strip() for t in teacher.split(',')]
            for teacher_name in teachers_list:
                if teacher_name not in teacher_map:
                    teacher_result = await db.execute(
                        select(Teacher).filter(Teacher.fio == teacher_name)
                    )
                    teacher = teacher_result.scalar_one_or_none()
                    if teacher is None:
                        teacher = Teacher(fio=teacher_name)
                        db.add(teacher)
                        await db.flush()
                    teacher_map[teacher_name] = teacher
        await db.commit()

        # Второй этап: обработка групп и связей
        for elective_name, group_name, free_spots, day, time_interval, teacher in final_d:
            result = await db.execute(
                select(Group)
                .options(selectinload(Group.students), selectinload(Group.teachers))
                .filter(Group.name == group_name)
            )
            group = result.scalar_one_or_none()
            if group is not None:
                group.day = day
                group.time_interval = time_interval
                group.free_spots = free_spots
                
                if group.free_spots < 0:
                    group.capacity = len(group.students)
                else:
                    group.capacity = len(group.students) + free_spots

                teachers_list = [t.strip() for t in teacher.split(',')]
                group_teachers = [teacher_map[t] for t in teachers_list]
                
                new_teachers = set(group_teachers)
                group.teachers.clear()
                group.teachers.extend(list(new_teachers))
                
                await db.commit()
            else:
                log.error(f'Не нашли группу для {elective_name, group_name}')

        result = await db.execute(select(Group).options(selectinload(Group.students)))
        all_groups = result.scalars().all()
        for group in all_groups:
            if group.free_spots is None:
                group.capacity = 200
            group.init_usage = len(group.students)

        await db.commit()
        log.info("Парсинг расписания прошел")
