from dataclasses import dataclass

from backend.logic.services.zexceptions.base import ServiceException


@dataclass
class AlreadyExistsTransfer(ServiceException):
    student_id: int
    from_id: int
    to_id: int

    @property
    def message(self):
        return f'Заявка студента- {self.student_id} с электива {self.from_id} на {self.to_id} уже существует'
