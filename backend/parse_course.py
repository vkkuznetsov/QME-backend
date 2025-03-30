import pandas as pd
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import db_session
from backend.database.database import engine
from sqlalchemy.orm import selectinload

from backend.database.models.group import Group

from logging import getLogger
from backend.utils.time_measure import time_log

name = __name__
log = getLogger(name)


class ElectiveFileParser:
    def __init__(self, file: UploadFile):
        self.file = file
        self.db_engine = engine
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
                row['Время проведения']
            )
            final_d.add(new_data)

        for elective_name, group_name, free_spots, day, time_interval in final_d:
            result = await db.execute(
                select(Group)
                .options(selectinload(Group.students))
                .filter(Group.name == group_name)
            )
            group = result.scalar_one_or_none()
            if group is not None:
                group.day = day
                group.time_interval = time_interval
                group.free_spots = free_spots
                group.capacity = len(group.students) + free_spots
            else:
                log.error(f'Не нашли группу для {elective_name, group_name}')


        result = await db.execute(select(Group).options(selectinload(Group.students)))
        all_groups = result.scalars().all()
        for group in all_groups:
            group.init_usage = len(group.students)

        await db.commit()
        log.info("Парсинг расписания прошел")
