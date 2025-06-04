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
        from collections import defaultdict
        electives_result = await db.execute(
            select(Elective).options(
                joinedload(Elective.groups)
                .options(
                    joinedload(Group.students),
                    joinedload(Group.teachers)
                )
            )
        )
        electives = electives_result.unique().scalars().all()

        result = []
        for e in electives:
            type_to_groups = defaultdict(list)
            for g in e.groups:
                type_to_groups[g.type].append(g)

            free_spots_per_type = []
            for g_list in type_to_groups.values():
                total = sum(g.capacity - len(g.students) for g in g_list)
                free_spots_per_type.append(total)

            total_free = min(free_spots_per_type) if free_spots_per_type else 0

            teachers = {t.fio for g in e.groups for t in g.teachers if t.fio}
            days = {g.day for g in e.groups if g.day}

            result.append({
                "id": e.id,
                "name": e.name,
                "cluster": e.cluster,
                "free_spots": total_free,
                "teachers": sorted(teachers),
                "days": sorted(days)
            })

        return result

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
