from logging import getLogger

from fastapi import APIRouter, Depends

from backend.api.deps.limit_deps import Pagination
from backend.logic.services.student_service.orm import ORMStudentService

log = getLogger(__name__)

router = APIRouter(tags=["student"])


@router.get("/student_info")
async def get_student(email: str, student_service: ORMStudentService = Depends()):
    student_info = await student_service.get_student_group_elective_email(email)
    if not student_info:
        return {}
    return student_info


@router.get("/students")
async def get_students(
        paging: Pagination = Depends(),
        student_service: ORMStudentService = Depends()
):
    students = await student_service.get_all_student_group_elective_email(
        start=paging.start,
        limit=paging.limit,
    )
    return students


@router.get("/students/{student_id}/electives/{elective_id}/can-transfer")
async def check_can_student_transfer(
        student_id: int,
        elective_id: int,
        student_service: ORMStudentService = Depends(),
):
    return await student_service.can_student_transfer(student_id, elective_id)
