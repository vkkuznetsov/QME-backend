from dataclasses import dataclass
from backend.logic.services.code_service.base import ICodeService
from backend.logic.services.student_service.base import IStudentService
from backend.logic.services.manager_service.orm import ManagerService


@dataclass
class ConfirmCodeUseCase:
    student_service: IStudentService
    manager_service: ManagerService
    code_service: ICodeService

    async def execute(self, email: str, code: str):
        await self.student_service.get_student_by_email(email)
        await self.code_service.validate_code(student_email=email, code=code)

        return await self.get_role(email)

    async def get_role(self, email: str) -> str:
        manager = await self.manager_service.get_manager_by_email(email)
        if manager:
            return "admin", '/admin'

        student = await self.student_service.get_student_by_email(email)
        if student:
            return "user", '/'

        raise Exception("User not found")
