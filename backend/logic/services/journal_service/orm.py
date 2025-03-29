from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database.models.journal import Journal

from backend.database.database import db_session


class JournalService:

    @db_session
    async def get_all_records(self, db: AsyncSession):
        result = await db.execute(select(Journal))
        return result.scalars().all()

    @db_session
    async def add_record_upload_choose(self, db: AsyncSession):
        journal = Journal(
            status="В обработке",
            type='Кем загружен',
            message='Загрузка файла выбора'
        )
        db.add(journal)
        await db.commit()
        await db.refresh(journal)
        return journal

    @db_session
    async def add_record_upload_elective(self, db: AsyncSession):
        journal = Journal(
            status="В обработке",
            type='Кем загружен',
            message='Загрузка файла расписания элективов'
        )
        db.add(journal)
        await db.commit()
        await db.refresh(journal)
        return journal