from dataclasses import dataclass

from backend.services.code_service.base import ICodeService
from backend.services.sender_service.base import ISenderService
from backend.services.student_service.base import IStudentService


@dataclass
class AuthorizeCodeUseCase:
    student_service: IStudentService
    sender_service: ISenderService
    code_service: ICodeService

    async def execute(self, email: str):
        student = await self.student_service.get_student_by_email(email)
        print(student)
        code = await self.code_service.generate_code(student.email)
        await self.sender_service.send_code(student_email=student.email, code=code)
