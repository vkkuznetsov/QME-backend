from enum import Enum

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from backend.database.database import db_session, AsyncSessionLocal
from backend.database.models import Elective, Group
from backend.database.models.transfer import Transfer
from backend.logic.services.transfer_service.base import ITransferService


class TransferStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ORMTransferService(ITransferService):

    @db_session
    async def get_transfer_by_student_id(self, student_id, db: AsyncSession):
        # Маппинг статусов на русский язык
        status_mapping = {
            "pending": "Ожидается",
            "rejected": "Отклонено",
            "approved": "Одобрено"
        }

        transfers_result = await db.execute(
            select(Transfer).where(Transfer.student_id == student_id)
        )
        transfers = transfers_result.scalars().all()

        result = []
        for transfer in transfers:
            from_elective = await db.get(Elective, transfer.from_elective_id)
            to_elective = await db.get(Elective, transfer.to_elective_id)

            selected_groups = []

            group_mapping = [
                (transfer.to_lecture_group_id, "лекция", Group),
                (transfer.to_practice_group_id, "практика", Group),
                (transfer.to_lab_group_id, "лабораторная", Group),
                (transfer.to_consultation_group_id, "консультация", Group)
            ]

            for group_id, group_type, model in group_mapping:
                if group_id:
                    group = await db.get(model, group_id)
                    if group:
                        selected_groups.append({
                            "id": group.id,
                            "type": group_type,
                            "name": group.name
                        })

            # Преобразуем статус
            raw_status = transfer.status
            translated_status = status_mapping.get(raw_status, "Неизвестный статус")

            result.append({
                "id": transfer.id,
                "userId": transfer.student_id,
                "electiveId": transfer.to_elective_id,
                "sourceElectiveId": transfer.from_elective_id,
                "sourceElectiveName": from_elective.name if from_elective else "Неизвестный электив",
                "electiveName": to_elective.name if to_elective else "Неизвестный электив",
                "selectedGroups": selected_groups,
                "status": translated_status,  # Используем переведенный статус
                "priority": transfer.priority
            })

        return result

    @db_session
    async def get_all_transfers(self, db: AsyncSession):
        query = select(Transfer)
        result = await db.execute(query)
        transfers = result.all()
        return transfers

    @db_session
    async def create_transfer(self, student_id: int, to_groups: list[int], from_elective_id: int,
                              to_elective_id: int, db: AsyncSession):
        existing_count = await db.execute(
            select(func.count()).where(Transfer.student_id == student_id)
        )
        priority = existing_count.scalar() + 1

        groups = await db.execute(select(Group).where(Group.id.in_(to_groups)))
        result = groups.scalars().all()

        transfer = Transfer(student_id=student_id, from_elective_id=from_elective_id,
                            to_elective_id=to_elective_id, priority=priority)
        transfer.groups.extend(result)
        db.add(transfer)
        await db.commit()
        return transfer


if __name__ == '__main__':
    import asyncio


    async def get_transfer_by_student_id_with_session(student_id):
        from_el = aliased(Elective)
        to_el = aliased(Elective)
        async with AsyncSessionLocal() as db:
            stmt = (select(Transfer, from_el, to_el)
                    .where(Transfer.student_id == student_id)
                    .join(from_el, Transfer.from_elective_id == from_el.id)
                    .join(to_el, Transfer.to_elective_id == to_el.id)
                    )
            print(stmt.compile(compile_kwargs={"literal_binds": True}))
            transfers_result = await db.execute(
                stmt
            )
            result = transfers_result.all()

            for transfer, from_elective, to_elective in result:
                print(transfer, from_elective.name, to_elective.name, sep=' | ')


    async def create_transfer():
        async with AsyncSessionLocal() as db:
            transfer = Transfer(student_id=1, from_elective_id=1, to_elective_id=2)
            groups = await db.execute(select(Group).where(Group.id.in_([1, 2, 3])))
            result = groups.scalars().all()
            print(result)
            transfer.groups.extend(result)
            print(transfer.groups)
            db.add(transfer)
            await db.commit()


    asyncio.run(create_transfer())

# TODO убрать тыщу ебаных FK на разные виды групп (оставить to_group)
# TODO Улучшить мапперы с Enum
# TODO Join'ить запросы к группам и элективам, чтобы не открывалось ЕБАНЫХ 150 транзакций за весь запрос
