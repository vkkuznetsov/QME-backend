from functools import wraps
from typing import Callable

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from backend.project.config import get_config

engine = create_async_engine(get_config().postgres_settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


def db_session(func: Callable):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        async with AsyncSessionLocal() as db:
            kwargs['db'] = db
            return await func(*args, **kwargs)

    return wrapper
