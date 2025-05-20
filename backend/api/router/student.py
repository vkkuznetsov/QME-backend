from logging import getLogger

from fastapi import APIRouter

from backend.logic.services.student_service.orm import ORMStudentService

log = getLogger(__name__)

router = APIRouter(tags=['student'])


@router.get('/student_info')
async def get_student(email: str):
    student_service = ORMStudentService()
    return await student_service.get_student_group_elective_email(email)


@router.get('/students')
async def get_students():
    student_service = ORMStudentService()
    return await student_service.get_all_student_group_elective_email()
