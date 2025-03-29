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
        await self.read_file_w()

    async def read_file(self):
        self.raw_df = pd.read_excel(self.file.file)
        print(self.raw_df)

    @time_log(name)
    @db_session
    async def read_file_w(self, db: AsyncSession):
        try:
            excel_file = pd.ExcelFile(self.file.file)

            # Проверяем наличие листа "Расписание"
            if "Расписание" not in excel_file.sheet_names:
                print("Лист 'Расписание' не найден в файле.")
                return None

            # Загружаем лист "Расписание"
            schedule_df = excel_file.parse("Расписание")
            print("Содержимое листа 'Расписание' загружено.")

            # Создаём словарь с группировкой по "РМУП название"
            grouped_data = defaultdict(list)

            for _, row in schedule_df.iterrows():
                group = row["РМУП название"]
                entry = {
                    "Команда": row["Команда название"],
                    "Сотрудники": row["Сотрудники в команде"],
                    "Свободные места": row["свободных мест в команде"],
                    "День недели": row["День недели"],
                    "Время": row["Время проведения"]
                }
                grouped_data[group].append(entry)

            print(f"Обработано {len(grouped_data)} групп.")


            return grouped_data

        except Exception as e:
            print(f"Ошибка при чтении файла: {e}")
            return None

