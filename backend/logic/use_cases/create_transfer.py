from dataclasses import dataclass

from backend.logic.services.student_service.base import IStudentService
from backend.logic.services.transfer_service.base import ITransferService


@dataclass
class CreateTransferUseCase:
    student_service: IStudentService
    transfer_service: ITransferService

    async def execute(
            self,
            student_id: int,
            from_elective_id: int,
            to_elective_id: int,
            groups_to_ids: list[int],
    ):
        groups_from = await self.student_service.get_student_groups_for_elective(
            student_id, from_elective_id
        )
        group_from_ids = [group.id for group in groups_from]
        await self.transfer_service.create_transfer(
            student_id, from_elective_id, to_elective_id, group_from_ids, groups_to_ids
        )
        return {"message": "Transfer created"}
