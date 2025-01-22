from abc import ABC, abstractmethod


class IStudentService(ABC):
    @abstractmethod
    async def get_student_by_email(self, student_email):
        ...

    @abstractmethod
    async def get_student_group_elective_email(self, student_email):
        ...

    @abstractmethod
    async def get_groups_students_by_elective(self, id_elective):
        ...