from abc import ABC, abstractmethod


class ISenderService(ABC):
    @abstractmethod
    async def send_code(self, student_email: str, code: str):
        ...
