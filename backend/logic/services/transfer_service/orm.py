from enum import Enum

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from backend.database.database import db_session
from backend.database.models import Elective, Group, Student
from backend.database.models.transfer import Transfer
from backend.logic.services.transfer_service.base import ITransferService
from logging import getLogger

from backend.logic.services.zexceptions.orm import AlreadyExistsTransfer

logger = getLogger(__name__)


class TransferStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ORMTransferService(ITransferService):

    @db_session
    async def get_transfer_by_student_id(self, student_id: int, db: AsyncSession):
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
                (transfer.to_lab_group_id, "лабораторные", Group),
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
        FromElective = aliased(Elective)
        ToElective = aliased(Elective)
        LectureGroup = aliased(Group)
        PracticeGroup = aliased(Group)
        LabGroup = aliased(Group)
        ConsultationGroup = aliased(Group)

        query = (
            select(
                Transfer.id,
                Student.fio.label("student_fio"),
                FromElective.name.label("from_elective_name"),
                ToElective.name.label("to_elective_name"),
                LectureGroup.name.label("to_lecture_group_name"),
                PracticeGroup.name.label("to_practice_group_name"),
                LabGroup.name.label("to_lab_group_name"),
                ConsultationGroup.name.label("to_consultation_group_name"),
                Transfer.status,
                Transfer.priority,
                Transfer.created_at
            )
            .join(Student, Transfer.student_id == Student.id)
            .join(FromElective, Transfer.from_elective_id == FromElective.id)  # Для from_elective
            .join(ToElective, Transfer.to_elective_id == ToElective.id)  # Для to_elective
            .outerjoin(LectureGroup, Transfer.to_lecture_group_id == LectureGroup.id)
            .outerjoin(PracticeGroup, Transfer.to_practice_group_id == PracticeGroup.id)
            .outerjoin(LabGroup, Transfer.to_lab_group_id == LabGroup.id)
            .outerjoin(ConsultationGroup, Transfer.to_consultation_group_id == ConsultationGroup.id)
        )

        result = await db.execute(query)
        transfers = result.mappings().all()
        return transfers

    @db_session
    async def create_transfer(self, student_id: int,
                              to_lecture_group_id: int | None,
                              to_practice_group_id: int | None,
                              to_lab_group_id: int | None,
                              to_consultation_group_id: int | None,
                              from_elective_id: int,
                              to_elective_id: int,
                              db: AsyncSession):

        if await self._check_existing_transfer(
                db=db,
                student_id=student_id,
                to_lecture_group_id=to_lecture_group_id,
                to_practice_group_id=to_practice_group_id,
                to_lab_group_id=to_lab_group_id,
                to_consultation_group_id=to_consultation_group_id,
                from_elective_id=from_elective_id,
                to_elective_id=to_elective_id
        ):
            logger.error(f"Заявка уже существует {student_id} {from_elective_id} {to_elective_id}")
            raise AlreadyExistsTransfer(student_id, from_elective_id, to_elective_id)

        priority = await self._calculate_priority(
            db=db,
            student_id=student_id,
            from_elective_id=from_elective_id
        )

        return await self._create_new_transfer(
            db=db,
            student_id=student_id,
            to_lecture_group_id=to_lecture_group_id,
            to_practice_group_id=to_practice_group_id,
            to_lab_group_id=to_lab_group_id,
            to_consultation_group_id=to_consultation_group_id,
            from_elective_id=from_elective_id,
            to_elective_id=to_elective_id,
            priority=priority
        )

    @staticmethod
    async def _check_existing_transfer(db: AsyncSession, student_id: int,
                                       to_lecture_group_id: int | None,
                                       to_practice_group_id: int | None,
                                       to_lab_group_id: int | None,
                                       to_consultation_group_id: int | None,
                                       from_elective_id: int,
                                       to_elective_id: int) -> bool:
        """
        Проверяет, существует ли уже такая заявка.
        """
        existing_transfer = await db.execute(
            select(Transfer).where(
                Transfer.student_id == student_id,
                Transfer.to_lecture_group_id == to_lecture_group_id,
                Transfer.to_practice_group_id == to_practice_group_id,
                Transfer.to_lab_group_id == to_lab_group_id,
                Transfer.to_consultation_group_id == to_consultation_group_id,
                Transfer.from_elective_id == from_elective_id,
                Transfer.to_elective_id == to_elective_id
            )
        )
        return existing_transfer.scalars().first() is not None

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
    async def _create_new_transfer(db: AsyncSession, student_id: int,
                                   to_lecture_group_id: int | None,
                                   to_practice_group_id: int | None,
                                   to_lab_group_id: int | None,
                                   to_consultation_group_id: int | None,
                                   from_elective_id: int,
                                   to_elective_id: int,
                                   priority: int) -> Transfer:
        """
        Создает новую запись Transfer в базе данных.
        """
        transfer = Transfer(
            student_id=student_id,
            to_lecture_group_id=to_lecture_group_id,
            to_practice_group_id=to_practice_group_id,
            to_lab_group_id=to_lab_group_id,
            to_consultation_group_id=to_consultation_group_id,
            from_elective_id=from_elective_id,
            to_elective_id=to_elective_id,
            priority=priority
        )
        db.add(transfer)
        await db.commit()
        await db.refresh(transfer)
        return transfer
