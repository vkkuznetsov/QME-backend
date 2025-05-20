from functools import wraps
from typing import Callable

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from backend.config import settings

DATABASE_URL = (f"{settings.DATABASE.DRIVER}://"
                f"{settings.DATABASE.USER}:"
                f"{settings.DATABASE.PASSWORD}@"
                f"{settings.DATABASE.HOST}:"
                f"{settings.DATABASE.PORT}/"
                f"{settings.DATABASE.NAME}")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


def db_session(func: Callable):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        async with AsyncSessionLocal() as db:
            kwargs['db'] = db
            return await func(*args, **kwargs)

    return wrapper


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)