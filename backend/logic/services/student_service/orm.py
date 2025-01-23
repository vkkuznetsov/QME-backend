from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.database.database import db_session
from backend.database.models.elective import Elective
from backend.database.models.group import Group
from backend.database.models.student import Student

from backend.logic.services.student_service.base import IStudentService


class ORMStudentService(IStudentService):
    @db_session  # TODO переделать на экзистс
    async def get_student_by_email(self, student_email, db: AsyncSession):
        stmt = select(Student).where(Student.email == student_email).limit(1)
        result = await db.scalar(stmt)
        return result

    @db_session
    async def get_student_group_elective_email(self, student_email, db: AsyncSession):
        query = (
            select(Student)
            .options(
                joinedload(Student.groups)
                .joinedload(Group.elective)
            )
            .where(Student.email == student_email)
        )

        result = await db.execute(query)
        student = result.unique().scalar_one_or_none()
        if student:
            return student
        return None

    @db_session
    async def get_groups_students_by_elective(self, id_elective: int, db: AsyncSession):
        query = (
            select(Elective)
            .options(
                joinedload(Elective.groups)
                .joinedload(Group.students)
            )
            .where(Elective.id == id_elective)
        )

        result = await db.execute(query)
        elective = result.unique().scalar_one_or_none()

        if elective:
            return elective
        return None

    @db_session
    async def get_all_electives(self, db: AsyncSession):

        result = await db.execute(select(Elective.id, Elective.name, Elective.cluster))
        electives = [{"id": id, "name": name, "cluster": cluster} for id, name, cluster in result.all()]

        return electives
