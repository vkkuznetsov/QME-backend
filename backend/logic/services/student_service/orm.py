from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import db_session
from backend.database.models.student import Student
from backend.logic.services.student_service.base import IStudentService


class ORMStudentService(IStudentService):
    @db_session  # TODO переделать на экзистс
    async def get_student_by_email(self, student_email, db: AsyncSession):
        stmt = select(Student).where(Student.email == student_email).limit(1)
        result = await db.scalar(stmt)
        print(result)
        return result
