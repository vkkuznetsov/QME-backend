from dataclasses import dataclass

import sqlalchemy as sa
from redis.asyncio import StrictRedis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import db_session
from backend.database.redis import redis_client
from backend.logic.services.healthcheck.base import IHealthCheckService


@dataclass
class PostgresHealthcheckService(IHealthCheckService):
    @db_session
    async def check(self, db: AsyncSession) -> dict[str, bool]:
        try:
            cursor = await db.execute(sa.select(1))
            result = cursor.scalar()
            return {self.__class__.__name__: result == 1}

        except Exception:
            return {self.__class__.__name__: False}


@dataclass
class RedisHealthcheckService(IHealthCheckService):
    redis: StrictRedis = redis_client

    async def check(self) -> dict[str, bool]:
        try:
            is_redis_alive = await self.redis.ping()
            return {self.__class__.__name__: is_redis_alive}

        except Exception:
            return {self.__class__.__name__: False}
