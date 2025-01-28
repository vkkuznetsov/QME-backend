from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.database.database import db_session
from backend.database.models.elective import Elective
from backend.database.models.group import Group
from backend.database.models.student import Student
from backend.database.models.student import student_group

from backend.logic.services.student_service.base import IStudentService


class ORMStudentService(IStudentService):
    @db_session  # TODO переделать на экзистс
    async def get_student_by_email(self, student_email, db: AsyncSession):
        stmt = select(Student).where(Student.email == student_email).limit(1)
        result = await db.scalar(stmt)
        return result

    @db_session
    async def get_recomendation(self, direction: str, db: AsyncSession):
        total_students_query = select(func.count(Student.id)).where(
            Student.sp_code == direction
        )
        total_students = await db.scalar(total_students_query)

        if not total_students:
            return []

        # Сначала получаем данные по курсам
        subquery = (
            select(
                Elective.cluster,
                Elective.id,
                Elective.name,
                func.count(Student.id.distinct()).label('course_student_count')
            )
            .select_from(Student)
            .join(student_group)
            .join(Group)
            .join(Elective)
            .where(Student.sp_code == direction)
            .group_by(Elective.cluster, Elective.id, Elective.name)
            .subquery()
        )

        # Затем агрегируем по кластерам
        stmt = (
            select(
                subquery.c.cluster,
                func.sum(subquery.c.course_student_count).label('total_students'),
                func.json_agg(
                    func.json_build_object(
                        'id', subquery.c.id,
                        'name', subquery.c.name,
                        'student_count', subquery.c.course_student_count
                    )
                ).label('courses')
            )
            .group_by(subquery.c.cluster)
        )

        result = await db.execute(stmt)
        clusters_data = result.all()

        recommendations = []
        for cluster, students_count, courses in clusters_data:
            sorted_courses = sorted(
                [dict(c) for c in courses],
                key=lambda x: x['student_count'],
                reverse=True
            )[:5]

            cluster_percent = round((students_count / total_students) * 100, 1)
            if cluster_percent <= 0:
                continue

            recommendations.append({
                "name": cluster,
                "percent": cluster_percent,
                "totalStudents": students_count,
                "topCourses": [
                    {
                        **course,
                        "percent": round((course['student_count'] / total_students) * 100, 1)
                    }
                    for course in sorted_courses
                ]
            })

        return sorted(
            recommendations,
            key=lambda x: x['percent'],
            reverse=True
        )[:5]

    @db_session
    async def get_groups_by_elective(self, elective_id: int, db: AsyncSession):
        query = (
            select(Group)
            .options(joinedload(Group.students))
            .where(Group.elective_id == elective_id)
        )

        result = await db.execute(query)
        groups = result.unique().scalars().all()

        return groups or []

    @db_session
    async def get_student_group_elective_email(self, student_email, db: AsyncSession):
        query = (
            select(Student)
            .options(
                joinedload(Student.groups)
                .joinedload(Group.electives)
            )
            .where(Student.email == student_email)
        )

        result = await db.execute(query)
        student = result.unique().scalar_one_or_none()
        if student:
            return student
        return None

    @db_session
    async def get_all_student_group_elective_email(self, db: AsyncSession):
        query = (
            select(Student)
            .options(
                joinedload(Student.groups)
                .joinedload(Group.electives)
            )
        )

        result = await db.execute(query)
        students = result.unique().scalars().all()
        if students:
            return students
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

        query = (
            select(
                Elective.id,
                Elective.name,
                Elective.cluster
            )
            .order_by(
                Elective.cluster.is_not(None).desc(),
                Elective.cluster,
                Elective.name
            )
        )

        result = await db.execute(query)
        electives = [
            {"id": id, "name": name, "cluster": cluster}
            for id, name, cluster in result.all()
        ]

        return electives
