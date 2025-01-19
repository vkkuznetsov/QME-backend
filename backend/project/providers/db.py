from typing import AsyncIterable

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.project.config import Config, get_config


class DBProvider(Provider):
    @provide(scope=Scope.APP)
    def config(self) -> Config:
        return get_config()

    @provide(scope=Scope.REQUEST)
    def sqlalchemy_engine(self, config: Config) -> AsyncEngine:
        return create_async_engine(config.postgres_settings.database_url)

    @provide(scope=Scope.REQUEST)
    def session_pool(self, sqlalchemy_engine: AsyncEngine) -> async_sessionmaker:
        return async_sessionmaker(
            bind=sqlalchemy_engine, expire_on_commit=False, class_=AsyncSession
        )

    @provide(scope=Scope.REQUEST)
    async def session(
        self, async_session_maker: async_sessionmaker
    ) -> AsyncIterable[AsyncSession]:  # noqa E501
        async with async_session_maker() as session:
            yield session
