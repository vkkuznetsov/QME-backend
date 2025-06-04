from sqlalchemy import select, func, distinct, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from backend.database.database import db_session
from backend.database.models.elective import Elective
from backend.database.models.group import Group, Teacher, group_teacher
from backend.database.models.transfer import Transfer

class ORMElectiveService:

    @db_session
    async def get_all_electives(self, db: AsyncSession) -> list[dict]:
        query = (
            select(
                Elective.id,
                Elective.name,
                Elective.cluster,
                func.min(Group.capacity - func.coalesce(Group.init_usage, 0)).label("free_spots"),
                func.array_agg(distinct(Teacher.fio)).label("teachers"),
                func.array_agg(distinct(Group.day)).label("days")
            )
            .join(Group, Group.elective_id == Elective.id)
            .join(group_teacher, group_teacher.c.group_id == Group.id)
            .join(Teacher, Teacher.id == group_teacher.c.teacher_id)
            .group_by(Elective.id, Elective.name, Elective.cluster)
            .order_by(Elective.id)
        )

        result = await db.execute(query)

        electives = [
            {
                "id": id, 
                "name": name, 
                "cluster": cluster, 
                "free_spots": free_spots,
                "teachers": [t for t in teachers if t is not None],  # Фильтруем None значения
                "days": [d for d in days if d is not None]  # Фильтруем None значения
            }
            for id, name, cluster, free_spots, teachers, days in result.all()
        ]

        return electives

    @db_session
    async def get_groups_students_by_elective(self, elective_id: int, db: AsyncSession):
        query = (
            select(Elective)
            .options(joinedload(Elective.groups).joinedload(Group.students))
            .where(Elective.id == elective_id)
        )

        result = await db.execute(query)
        return result.unique().scalar_one_or_none()

    @db_session
    async def get_groups_by_elective(self, elective_id: int, db: AsyncSession):
        query = (
            select(Group)
            .options(
                joinedload(Group.students),
                joinedload(Group.transfers_to).joinedload(Transfer.student),
                joinedload(Group.transfers_from).joinedload(Transfer.student)
            )
            .where(Group.elective_id == elective_id)
            .order_by(
                case(
                    (Group.type == "Лекции", 1),
                    (Group.type == "Практики", 2),
                    (Group.type == "Лабораторные", 3),
                    (Group.type == "Консультации", 4),
                    else_=5
                ),
                Group.name
            )
        )

        result = await db.execute(query)
        groups = result.unique().scalars().all()
        return groups
