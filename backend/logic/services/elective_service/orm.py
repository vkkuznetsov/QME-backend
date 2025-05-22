from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.database.database import db_session
from backend.database.models.elective import Elective
from backend.database.models.group import Group


class ORMElectiveService:

    @db_session
    async def get_all_electives(self, db: AsyncSession) -> list[dict]:
        query = (
            select(
                Elective.id,
                Elective.name,
                Elective.cluster,
                func.min(Group.capacity - func.coalesce(Group.init_usage, 0)).label("free_spots")
            )
            .join(Group, Group.elective_id == Elective.id)
            .group_by(Elective.id, Elective.name, Elective.cluster)
            .order_by(Elective.id)
        )

        result = await db.execute(query)

        electives = [
            {"id": id, "name": name, "cluster": cluster, "free_spots": free_spots}
            for id, name, cluster, free_spots in result.all()
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
            .options(joinedload(Group.students))
            .where(Group.elective_id == elective_id)
        )

        result = await db.execute(query)
        return result.unique().scalars().all()
