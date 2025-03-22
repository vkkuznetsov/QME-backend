from abc import ABC, abstractmethod


class ITransferService(ABC):
    @abstractmethod
    async def get_transfer_by_student_id(self, student_id):
        ...

    @abstractmethod
    async def get_all_transfers(self):
        ...

    @abstractmethod
    async def create_transfer(self, student_id: int,
                              from_elective_id: int,
                              to_elective_id: int,
                              groups_from_ids: list[int],
                              groups_to_ids: list[int]):
        ...

    @abstractmethod
    async def approve_transfer(self, transfer_id: int):
        ... 