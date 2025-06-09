from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from backend.database.database import db_session
from backend.database.models.elective import Elective
from backend.database.models.group import Group
from backend.database.models.student import Student
from backend.database.models.transfer import Transfer


class ORMElectiveService:
    @db_session
    async def get_all_electives(self, db: AsyncSession) -> list[dict]:
        """
        Оптимизированная версия: свободные места считаются агрегатами в БД,
        поэтому не требуется загружать студентов и выполнять расчёты в Python.
        """

        # свободные места сначала считаем для КАЖДОЙ группы,
        # затем агрегируем по типам
        group_free_subq = (
            select(
                Group.id.label("group_id"),
                Group.elective_id.label("elective_id"),
                Group.type.label("type"),
                (Group.capacity - func.count(Student.id)).label("free_spots_group"),
            )
            .select_from(Group)
            .outerjoin(Group.students)
            .group_by(Group.id)
            .subquery()
        )

        free_by_type_subq = (
            select(
                group_free_subq.c.elective_id,
                group_free_subq.c.type,
                func.sum(group_free_subq.c.free_spots_group).label("free_spots"),
            )
            .group_by(group_free_subq.c.elective_id, group_free_subq.c.type)
            .subquery()
        )

        # минимальное свободное количество мест среди типов
        min_free_subq = (
            select(
                free_by_type_subq.c.elective_id,
                func.min(free_by_type_subq.c.free_spots).label("total_free"),
            )
            .group_by(free_by_type_subq.c.elective_id)
            .subquery()
        )

        transfer_count_subq = (
            select(
                Transfer.to_elective_id.label("elective_id"),
                func.count(Transfer.id).label("transfer_count"),
            )
            .group_by(Transfer.to_elective_id)
            .subquery()
        )

        # основной запрос по элективам
        electives_stmt = (
            select(
                Elective,
                func.coalesce(min_free_subq.c.total_free, 0).label("free_spots"),
                func.coalesce(transfer_count_subq.c.transfer_count, 0).label("transfer_count"),
            )
            .outerjoin(min_free_subq, min_free_subq.c.elective_id == Elective.id)
            .outerjoin(
                transfer_count_subq,
                transfer_count_subq.c.elective_id == Elective.id
            )
            .options(
                # загружаем только группы и преподавателей; студентов больше не нужны
                selectinload(Elective.groups).selectinload(Group.teachers)
            )
        )

        rows = (await db.execute(electives_stmt)).unique().all()

        result: list[dict] = []
        for elective, free_spots, transfer_count in rows:
            teachers = {t.fio for g in elective.groups for t in g.teachers if t.fio}
            days = {g.day for g in elective.groups if g.day}

            result.append(
                {
                    "id": elective.id,
                    "name": elective.name,
                    "cluster": elective.cluster,
                    "free_spots": free_spots,
                    "transfer_count": transfer_count,
                    "teachers": sorted(teachers),
                    "days": sorted(days),
                }
            )

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
                joinedload(Group.transfers_from).joinedload(Transfer.student),
            )
            .where(Group.elective_id == elective_id)
            .order_by(
                case(
                    (Group.type == "Лекции", 1),
                    (Group.type == "Практики", 2),
                    (Group.type == "Лабораторные", 3),
                    (Group.type == "Консультации", 4),
                    else_=5,
                ),
                Group.name,
            )
        )

        result = await db.execute(query)
        return result.unique().scalars().all()
