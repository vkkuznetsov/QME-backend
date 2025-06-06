from abc import ABC, abstractmethod


class ICodeService(ABC):
    @abstractmethod
    async def generate_code(self, student_email: str): ...

    @abstractmethod
    async def validate_code(self, student_email: str, code: str): ...
