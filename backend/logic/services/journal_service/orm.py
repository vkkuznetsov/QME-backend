from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database.models.journal import Journal

from backend.database.database import db_session


class JournalService:

    @db_session
    async def get_all_records(self, db: AsyncSession):
        result = await db.execute(select(Journal).order_by(Journal.created_at.desc()))
        return result.scalars().all()

    @db_session
    async def add_record_upload_choose(self, db: AsyncSession):
        journal = Journal(
            status="Обработка началась",
            type="Кем загружен",
            message="Загрузка файла выбора: обработка началась"
        )
        db.add(journal)
        await db.commit()
        await db.refresh(journal)
        return journal

    @db_session
    async def add_record_upload_elective(self, db: AsyncSession):
        journal = Journal(
            status="Обработка началась",
            type="Кем загружен",
            message="Загрузка файла расписания элективов: обработка началась"
        )
        db.add(journal)
        await db.commit()
        await db.refresh(journal)
        return journal

    @db_session
    async def add_record_upload_choose_success(self, db: AsyncSession):
        journal = Journal(
            status="Успешно завершено",
            type="Кем загружен",
            message="Загрузка файла выбора: успешно завершена"
        )
        db.add(journal)
        await db.commit()
        await db.refresh(journal)
        return journal

    @db_session
    async def add_record_upload_elective_success(self, db: AsyncSession):
        journal = Journal(
            status="Успешно завершено",
            type="Кем загружен",
            message="Загрузка файла расписания элективов: успешно завершена"
        )
        db.add(journal)
        await db.commit()
        await db.refresh(journal)
        return journal
