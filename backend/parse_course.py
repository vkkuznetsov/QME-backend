import json
from collections import defaultdict
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
            new_data = row['РМУП название'], row['Команда название'], row['свободных мест в команде'], row['Время проведения']
            final_d.add(new_data)
        print(final_d)
