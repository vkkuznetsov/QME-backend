from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import db_session
from backend.logic.services.healthcheck.base import IHealthCheckService
import sqlalchemy as sa


@dataclass
class PostgresHealthcheckService(IHealthCheckService):
    session: AsyncSession

    async def check(self) -> dict[str, bool]:

        try:
            cursor = await self.session.execute(sa.select(1))
            result = cursor.scalar()
            return {self.__class__.__name__: result == 1}

        except SQLAlchemyError:
            raise
