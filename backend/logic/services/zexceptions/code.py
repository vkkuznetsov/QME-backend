from dataclasses import dataclass

from backend.logic.services.zexceptions.base import ServiceException


@dataclass
class CodeNotFoundException(ServiceException):
    code: str

    @property
    def message(self):
        return f"Code - {self.code} not found"


@dataclass
class CodeNotEqualException(ServiceException):
    @property
    def message(self):
        return "Code not equal"
