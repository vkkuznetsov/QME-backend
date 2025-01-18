from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import db_session
from backend.database.models.student import Student


class IStudentService(ABC):
    @abstractmethod
    async def get_student_by_email(self, student_email):
        ...


class ORMStudentService(IStudentService):
    @db_session # TODO переделать на экзистс
    async def get_student_by_email(self, student_email, db: AsyncSession):
        stmt = select(Student).where(Student.email == student_email).limit(1)
        result = await db.scalar(stmt)
        print(result)
        return result

if __name__ == '__main__':
    import asyncio
    async def main():
        res = await ORMStudentService().get_student_by_email('vita.201581@yandex.ru')
    asyncio.run(main())