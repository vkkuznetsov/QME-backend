from dataclasses import dataclass
from backend.logic.services.code_service.base import ICodeService
from backend.logic.services.student_service.base import IStudentService


@dataclass
class ConfirmCodeUseCase:
    student_service: IStudentService
    code_service: ICodeService

    async def execute(self, email: str, code: str):
        await self.student_service.get_student_by_email(email)
        await self.code_service.validate_code(student_email=email, code=code)
        # логика авторизации
