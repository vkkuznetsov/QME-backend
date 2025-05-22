from typing import List, Optional

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
    @db_session  # TODO: переделать на EXISTS для оптимизации
    async def get_student_by_email(
            self,
            student_email: str,
            db: AsyncSession
    ) -> Optional[Student]:
        """
        Получить студента по email без загрузки связанных сущностей.

        Args:
            student_email (str): Email студента.
            db (AsyncSession): Асинхронная сессия SQLAlchemy.

        Returns:
            Optional[Student]: Объект Student, если найден, иначе None.
        """
        query = select(Student).where(Student.email == student_email).limit(1)
        student: Optional[Student] = await db.scalar(query)
        return student

    @db_session
    async def get_student_group_elective_email(
            self,
            student_email: str,
            db: AsyncSession
    ) -> Optional[Student]:
        """
        Получить студента по email вместе с его группами и элективами.

        Загрузка происходит через joinedload, чтобы избежать N+1 проблем.

        Args:
            student_email (str): Email студента.
            db (AsyncSession): Асинхронная сессия SQLAlchemy.

        Returns:
            Optional[Student]: Объект Student с загруженными группами и элективами, иначе None.
        """
        query = (
            select(Student)
            .options(joinedload(Student.groups).joinedload(Group.elective))
            .where(Student.email == student_email)
        )
        result = await db.execute(query)
        student: Optional[Student] = result.unique().scalar_one_or_none()
        return student

    @db_session
    async def get_all_student_group_elective_email(
            self,
            db: AsyncSession,
            start: int,
            limit: int
    ) -> List[Student]:
        """
        Получить список студентов с пагинацией без загрузки связанных сущностей.

        Args:
            db (AsyncSession): Асинхронная сессия SQLAlchemy.
            start (int): Смещение для начала выборки.
            limit (int): Максимальное количество возвращаемых записей.

        Returns:
            List[Student]: Список объектов Student (может быть пустым).
        """
        query = (
            select(Student)
            .offset(start)
            .limit(limit)
        )
        result = await db.execute(query)
        students_list = result.unique().scalars().all()
        students: List[Student] = list(students_list)
        return students

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
                func.count(Student.id.distinct()).label("course_student_count"),
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
        stmt = select(
            subquery.c.cluster,
            func.sum(subquery.c.course_student_count).label("total_students"),
            func.json_agg(
                func.json_build_object(
                    "id",
                    subquery.c.id,
                    "name",
                    subquery.c.name,
                    "student_count",
                    subquery.c.course_student_count,
                )
            ).label("courses"),
        ).group_by(subquery.c.cluster)

        result = await db.execute(stmt)
        clusters_data = result.all()

        recommendations = []
        for cluster, students_count, courses in clusters_data:
            sorted_courses = sorted(
                [dict(c) for c in courses],
                key=lambda x: x["student_count"],
                reverse=True,
            )[:5]

            cluster_percent = round((students_count / total_students) * 100, 1)
            if cluster_percent <= 0:
                continue

            recommendations.append(
                {
                    "name": cluster,
                    "percent": cluster_percent,
                    "totalStudents": students_count,
                    "topCourses": [
                        {
                            **course,
                            "percent": round(
                                (course["student_count"] / total_students) * 100, 1
                            ),
                        }
                        for course in sorted_courses
                    ],
                }
            )

        return sorted(recommendations, key=lambda x: x["percent"], reverse=True)[:5]

    @db_session
    async def get_student_groups_for_elective(self, student_id: int, elective_id: int, db: AsyncSession) -> list[Group]:
        query = (
            select(Group)
            .join(student_group)
            .where(
                student_group.c.student_id == student_id,
                Group.elective_id == elective_id
            )
        )
        result = await db.execute(query)
        groups = result.unique().scalars().all()
        return groups
