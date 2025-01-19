import asyncio
from typing import AsyncIterable

from dishka import Provider, Scope, provide, container, make_async_container
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.logic.services.healthcheck.alchemy import PostgresHealthcheckService
from backend.logic.services.healthcheck.base import IHealthCheckService
from backend.logic.services.healthcheck.composite import CompositeHealthCheckService
from backend.project.config import Config, get_config
from backend.project.providers.db import DBProvider


class HealthCheckProvider(Provider):
    @provide(scope=Scope.REQUEST)
    async def postgres_healthcheck_service(self, session: AsyncSession) -> PostgresHealthcheckService:
        return PostgresHealthcheckService(session)

    @provide(scope=Scope.REQUEST)
    async def healthcheck_service_factory(self, postgres: PostgresHealthcheckService) -> IHealthCheckService:
        services = [
            postgres,
        ]
        return CompositeHealthCheckService(services)


if __name__ == "__main__":
    async def main():
        container = make_async_container(DBProvider(), HealthCheckProvider())
        async with container() as c:
            pg = await c.get(IHealthCheckService)
            return await pg.check()

    res = asyncio.run(main())
    print(res)