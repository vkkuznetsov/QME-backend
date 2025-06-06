from typing import List

from sqlalchemy import select, func, delete, insert, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database.database import db_session
from backend.database.models import Elective, Group, Student, student_group
from backend.database.models.transfer import Transfer, TransferStatus, transfer_group, GroupRole
from backend.logic.services.transfer_service.base import ITransferService
from logging import getLogger

from backend.logic.services.transfer_service.schemas import TransferReorder
from backend.logic.services.zexceptions.orm import AlreadyExistsTransfer
from backend.logic.services.log_service.orm import DatabaseLogger

logger = getLogger(__name__)
log = DatabaseLogger(__name__)


class ORMTransferService(ITransferService):

    @db_session
    async def get_transfer_by_student_id(self, student_id: int, db: AsyncSession):
        stmt = (
            select(Transfer)
            .where(Transfer.student_id == student_id)
            .options(
                selectinload(Transfer.from_elective),
                selectinload(Transfer.to_elective),
                selectinload(Transfer.groups_to),
            )
        )

        transfers = (await db.execute(stmt)).scalars().all()
        result = []

        for transfer in transfers:
            selected_groups = [
                {
                    "id": group.id,
                    "type": getattr(group, "type", "неизвестно"),
                    "name": group.name,
                }
                for group in transfer.groups_to
            ]

            try:
                ts = TransferStatus(transfer.status)
            except ValueError:
                ts = None

            translated_status = {
                TransferStatus.pending:   "Ожидается",
                TransferStatus.approved:  "Одобрено",
                TransferStatus.rejected:  "Отклонено",
            }.get(ts, "Неизвестный статус")

            result.append({
                "id": transfer.id,
                "userId": transfer.student_id,
                "electiveId": transfer.to_elective_id,
                "sourceElectiveId": transfer.from_elective_id,
                "sourceElectiveName": transfer.from_elective.name if transfer.from_elective else "Неизвестный электив",
                "electiveName": transfer.to_elective.name if transfer.to_elective else "Неизвестный электив",
                "selectedGroups": selected_groups,
                "status": translated_status,
                "priority": transfer.priority,
            })

        return result

    @db_session
    async def get_all_transfers(self, db: AsyncSession):
        query = select(Transfer).options(
            selectinload(Transfer.student),
            selectinload(Transfer.from_elective),
            selectinload(Transfer.to_elective),
            selectinload(Transfer.groups_from),
            selectinload(Transfer.groups_to)
        )
        result = await db.execute(query)
        transfers = result.scalars().all()
        
        result_list = []
        for transfer in transfers:
            result_list.append({
                "id": transfer.id,
                "student_fio": transfer.student.fio,
                "from_elective_name": transfer.from_elective.name,
                "to_elective_name": transfer.to_elective.name,
                "groups_from": [(group.name, group.type, group.init_usage, group.capacity) for group in transfer.groups_from],
                "groups_to": [(group.name, group.type, group.init_usage, group.capacity) for group in transfer.groups_to],
                "status": transfer.status,
                "priority": transfer.priority,
                "created_at": transfer.created_at.isoformat() if transfer.created_at else None
            })
        return result_list

    @db_session
    async def create_transfer(self, student_id: int,
                              from_elective_id: int,
                              to_elective_id: int,
                              groups_from_ids: list[int],
                              groups_to_ids: list[int],
                              db: AsyncSession):
        try:
            if await self._check_existing_transfer(
                    db=db,
                    student_id=student_id,
                    groups_from_ids=groups_from_ids,
                    groups_to_ids=groups_to_ids,
                    from_elective_id=from_elective_id,
                    to_elective_id=to_elective_id
            ):
                log.error(f"Заявка уже существует: студент {student_id}, с электива {from_elective_id} на {to_elective_id}")
                raise AlreadyExistsTransfer(student_id, from_elective_id, to_elective_id)

            priority = await self._calculate_priority(
                db=db,
                student_id=student_id,
                from_elective_id=from_elective_id
            )

            transfer = await self._create_new_transfer(
                db=db,
                student_id=student_id,
                groups_from_ids=groups_from_ids,
                groups_to_ids=groups_to_ids,
                from_elective_id=from_elective_id,
                to_elective_id=to_elective_id,
                priority=priority
            )
            
            log.info(f"Создана новая заявка: ID={transfer.id}, студент={student_id}, с электива {from_elective_id} на {to_elective_id}")
            return transfer
            
        except Exception as e:
            log.error(f"Ошибка при создании заявки: {str(e)}")
            raise

    @staticmethod
    async def _check_existing_transfer(db: AsyncSession, student_id: int,
                                       groups_from_ids: list[int],
                                       groups_to_ids: list[int],
                                       from_elective_id: int,
                                       to_elective_id: int) -> bool:
        """
        Проверяет, существует ли уже такая заявка.
        Сравнивает заявки по student_id, from_elective_id, to_elective_id, а также по наборам групп (из которых и в которые производится перевод).
        """
        result = await db.execute(
            select(Transfer).where(
                Transfer.student_id == student_id,
                Transfer.from_elective_id == from_elective_id,
                Transfer.to_elective_id == to_elective_id
            )
        )
        transfers = result.scalars().all()
        for transfer in transfers:
            existing_groups_from = {group.id for group in transfer.groups_from}
            existing_groups_to = {group.id for group in transfer.groups_to}
            if existing_groups_from == set(groups_from_ids) and existing_groups_to == set(groups_to_ids):
                return True
        return False

    @staticmethod
    async def _calculate_priority(db: AsyncSession, student_id: int, from_elective_id: int) -> int:
        """
        Рассчитывает приоритет для нового запроса на основе student_id и from_elective_id.
        """
        priority_query = await db.execute(
            select(func.count()).where(
                Transfer.student_id == student_id,
                Transfer.from_elective_id == from_elective_id
            )
        )
        return priority_query.scalar() + 1

    @staticmethod
    async def _create_new_transfer(
        db: AsyncSession,
        student_id: int,
        groups_from_ids: list[int],
        groups_to_ids: list[int],
        from_elective_id: int,
        to_elective_id: int,
        priority: int
    ) -> Transfer:
        """
        Создает новую запись Transfer в базе данных и записывает ассоциации с группами.
        
        Параметры:
        - groups_from_ids: список id групп, из которых производится перевод.
        - groups_to_ids: список id групп, в которые производится перевод.
        """
        transfer = Transfer(
            student_id=student_id,
            from_elective_id=from_elective_id,
            to_elective_id=to_elective_id,
            priority=priority
        )
        db.add(transfer)
        await db.commit()
        await db.refresh(transfer)

        for group_id in groups_from_ids:
            stmt = insert(transfer_group).values(
                transfer_id=transfer.id,
                group_id=group_id,
                group_role=GroupRole.FROM
            )
            await db.execute(stmt)

        for group_id in groups_to_ids:
            stmt = insert(transfer_group).values(
                transfer_id=transfer.id,
                group_id=group_id,
                group_role=GroupRole.TO
            )
            await db.execute(stmt)

        await db.commit()
        return transfer

    @db_session
    async def delete_transfer(self, db: AsyncSession, transfer_id: int) -> None:
        """
        Удаляет запись о переводе по указанному transfer_id.
        """
        await db.execute(
            delete(Transfer).where(Transfer.id == transfer_id)
        )
        await db.commit()
        return

    @db_session
    async def _change_transfer_status(self, transfer_id: int, status: TransferStatus, manager_id: int, db: AsyncSession):
        """
        Изменяет статус заявки на указанный.
        """
        transfer = await db.get(Transfer, transfer_id)
        if transfer is None:
            raise Exception(f"Transfer with id {transfer_id} не найден")
        transfer.status = status.value
        transfer.manager_id = manager_id
        await db.commit()
        await db.refresh(transfer)
        return transfer
    
    @db_session
    async def approve_transfer(self, transfer_id: int, manager_id: int, db: AsyncSession):
        """
        Одобряет заявку на перевод, обновляя связи студента с группами.
        При одобрении заявки отклоняет все другие заявки этого студента с того же исходного электива.
        """
        try:
            transfer = await db.get(Transfer, transfer_id)
            student = await db.get(Student, transfer.student_id)

            # Отклоняем другие заявки с того же исходного электива
            stmt = (
                select(Transfer)
                .where(
                    Transfer.student_id == student.id,
                    Transfer.from_elective_id == transfer.from_elective_id,
                    Transfer.id != transfer_id,
                    Transfer.status != TransferStatus.approved.value
                )
            )
            other_transfers = (await db.execute(stmt)).scalars().all()
            for other_transfer in other_transfers:
                await self._change_transfer_status(other_transfer.id, TransferStatus.rejected, manager_id)
                log.info(f"Отклонена заявка {other_transfer.id} при одобрении заявки {transfer_id}")

            # Удаляем старые связи студента с группами from_elective
            stmt = delete(student_group).where(
                student_group.c.group_id.in_(
                    select(transfer_group.c.group_id).where(
                        transfer_group.c.transfer_id == transfer_id,
                        transfer_group.c.group_role == GroupRole.FROM
                    )
                ),
                student_group.c.student_id == student.id
            )
            await db.execute(stmt)

            # Добавляем новые связи студента с группами to_elective
            stmt = (
                select(Group)
                .join(transfer_group)
                .where(
                    transfer_group.c.transfer_id == transfer_id,
                    transfer_group.c.group_role == GroupRole.TO
                )
            )
            groups = (await db.execute(stmt)).scalars().all()
            
            for group in groups:
                stmt = insert(student_group).values(
                    student_id=student.id,
                    group_id=group.id
                )
                await db.execute(stmt)

            await self._change_transfer_status(transfer_id, TransferStatus.approved, manager_id)
            log.info(f"Одобрена заявка {transfer_id}: студент {student.id} переведен с электива {transfer.from_elective_id} на {transfer.to_elective_id}")
            
            await db.commit()
            await db.refresh(student)
            
            return transfer
            
        except Exception as e:
            log.error(f"Ошибка при одобрении заявки {transfer_id}: {str(e)}")
            raise
    

    async def reject_transfer(self, transfer_id: int, manager_id: int):
        try:
            await self._change_transfer_status(transfer_id, TransferStatus.rejected, manager_id)
            log.info(f"Отклонена заявка {transfer_id}")
        except Exception as e:
            log.error(f"Ошибка при отклонении заявки {transfer_id}: {str(e)}")
            raise

    @staticmethod
    @db_session
    async def reorder_transfers(new_orders: List[TransferReorder], db: AsyncSession):
        for order in new_orders:
            stmt = (
                update(Transfer)
                .where(Transfer.id == order.id)
                .values(priority=order.priority)
            )
            await db.execute(stmt)
        await db.commit()

    @staticmethod
    @db_session
    async def count_active_transfer(db: AsyncSession) -> int:
        result = await db.execute(
            select(func.count()).select_from(Transfer).where(Transfer.status == TransferStatus.pending.value)
        )
        return result.scalar_one()
