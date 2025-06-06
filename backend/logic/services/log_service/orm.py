import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import db_session
from backend.database.models.log import Log


class ORMLogService:
    @db_session
    async def add_log(
            self, level: str, message: str, source: str, db: AsyncSession
    ) -> Log:
        """Добавляет новую запись в лог"""
        log = Log(level=level, message=message, source=source)
        db.add(log)
        await db.commit()
        await db.refresh(log)
        await db.flush()
        return log

    @db_session
    async def get_logs(self, limit: int, db: AsyncSession) -> list[Log]:
        """Получает последние логи"""
        query = select(Log).order_by(Log.timestamp.desc()).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    @db_session
    async def get_logs_by_level(
            self, level: str, limit: int, db: AsyncSession
    ) -> list[Log]:
        """Получает логи определенного уровня"""
        query = (
            select(Log)
            .where(Log.level == level)
            .order_by(Log.timestamp.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @db_session
    async def get_logs_by_source(
            self, source: str, limit: int, db: AsyncSession
    ) -> list[Log]:
        """Получает логи определенного источника"""
        query = (
            select(Log)
            .where(Log.source == source)
            .order_by(Log.timestamp.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())


class DatabaseLogger:
    def __init__(self, name: str):
        self.log_service = ORMLogService()
        self.logger = logging.getLogger(name)
        self.name = name

    async def _log_to_db(self, level: str, message: str):
        await self.log_service.add_log(level, message, self.name)

    def info(self, message: str):
        self.logger.info(message)
        asyncio.create_task(self._log_to_db("info", message))

    def error(self, message: str):
        self.logger.error(message)
        asyncio.create_task(self._log_to_db("error", message))

    def warning(self, message: str):
        self.logger.warning(message)
        asyncio.create_task(self._log_to_db("warning", message))

    def debug(self, message: str):
        self.logger.debug(message)
        asyncio.create_task(self._log_to_db("debug", message))
