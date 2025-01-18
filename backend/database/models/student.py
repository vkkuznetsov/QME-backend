import asyncio

from backend.database.database import Base, engine
from sqlalchemy.orm import Mapped, mapped_column


class Student(Base):
    __tablename__ = 'student'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fio: Mapped[str]
    email: Mapped[str]
    course: Mapped[str]

    def __str__(self):
        return f'{self.id} - {self.fio} - {self.email}'


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(create_tables())
