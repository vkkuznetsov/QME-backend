from logging import getLogger

from fastapi import APIRouter, Depends

from backend.logic.services.student_service.orm import ORMStudentService
from backend.api.deps.limit_deps import Pagination

log = getLogger(__name__)

router = APIRouter(tags=['student'])


@router.get('/student_info')
async def get_student(
        email: str,
        student_service: ORMStudentService = Depends()
):
    student_info = await student_service.get_student_group_elective_email(email)
    if not student_info:
        return {}
    return {
        "id": student_info.id,
        "fio": student_info.fio,
        "email": student_info.email,
        "sp_code": student_info.sp_code,
        "sp_profile": student_info.sp_profile,
        "potok": student_info.potok,
        "text_embed": student_info.text_embed,
        "groups": [
            {
                "id": group.id,
                "name": group.name,
                "elective": {
                    "id": group.elective.id,
                    "name": group.elective.name
                } if group.elective else None
            }
            for group in student_info.groups
        ]
    }


@router.get('/students')
async def get_students(
        paging: Pagination = Depends(),
        student_service: ORMStudentService = Depends()
):
    students = await student_service.get_all_student_group_elective_email(
        start=paging.start,
        limit=paging.limit,
    )
    return students
