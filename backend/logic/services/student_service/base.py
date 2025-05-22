from abc import ABC, abstractmethod


class IStudentService(ABC):
    @abstractmethod
    async def get_student_by_email(self, student_email):
        ...

    @abstractmethod
    async def get_student_group_elective_email(self, student_email):
        ...

    @abstractmethod
    async def get_student_groups_for_elective(self, student_id: int, elective_id: int):
        ...