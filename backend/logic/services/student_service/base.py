from abc import ABC, abstractmethod


class IStudentService(ABC):
    @abstractmethod
    async def get_student_by_email(self, student_email):
        ...
