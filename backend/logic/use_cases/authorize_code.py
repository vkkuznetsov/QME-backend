from dataclasses import dataclass

from backend.logic.services.code_service.base import ICodeService
from backend.logic.services.manager_service.orm import ManagerService
from backend.logic.services.sender_service.base import ISenderService
from backend.logic.services.student_service.base import IStudentService


@dataclass
class AuthorizeCodeUseCase:
    student_service: IStudentService
    manager_service: ManagerService
    sender_service: ISenderService
    code_service: ICodeService

    async def execute(self, email: str):
        person = await self.student_service.get_student_by_email(email)

        if not person:
            person = await self.manager_service.get_manager_by_email(email)
            if not person:
                raise Exception

        code = await self.code_service.generate_code(person.email)
        await self.sender_service.send_code(student_email=person.email, code=code)
