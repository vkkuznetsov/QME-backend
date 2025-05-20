from logging import getLogger

from fastapi import APIRouter, Depends

from backend.logic.services.student_service.orm import ORMStudentService
from backend.api.deps.limit_deps import pagination_params

log = getLogger(__name__)

router = APIRouter(tags=['student'])


@router.get('/student_info')
async def get_student(email: str):
    student_service = ORMStudentService()
    return await student_service.get_student_group_elective_email(email)


@router.get('/students')
async def get_students(
        paging: dict = Depends(pagination_params),
        student_service: ORMStudentService = Depends()
):
    students = await student_service.get_all_student_group_elective_email(
        start=paging["start"],
        limit=paging["limit"],
    )
    return students
