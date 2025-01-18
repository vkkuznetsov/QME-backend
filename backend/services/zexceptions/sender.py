from dataclasses import dataclass

from backend.services.zexceptions.base import ServiceException


@dataclass
class SendSMTPException(ServiceException):

    @property
    def message(self):
        return f'Error sending SMTP message'

