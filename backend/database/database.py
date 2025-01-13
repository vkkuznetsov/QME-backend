from functools import wraps
from typing import Callable

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from backend.config import settings

DATABASE_URL = (f"{settings.DATABASE_DRIVER}://"
                f"{settings.DATABASE_USERNAME}:"
                f"{settings.DATABASE_PASSWORD}@"
                f"{settings.DATABASE_HOST}:"
                f"{settings.DATABASE_PORT}"
                f"{settings.DATABASE_NAME}")

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
