from abc import ABC, abstractmethod


class ITransferService(ABC):
    @abstractmethod
    async def get_transfer_by_student_id(self, student_id):
        ...

    @abstractmethod
    async def get_all_transfers(self):
        ...

    @abstractmethod
    async def create_transfer(self, student_id: int, to_lecture_group_id: int | None, to_practice_group_id: int | None, to_lab_group_id: int | None, to_consultation_group_id: int | None, from_elective_id: int, to_elective_id: int):
        ...
