from fastapi import APIRouter

from backend.logic.services.student_service.orm import ORMStudentService

router = APIRouter(tags=['elective'])


@router.get('/elective/{elective_id}')
async def get_elective(elective_id: int):
    student_service = ORMStudentService()
    return await student_service.get_groups_students_by_elective(elective_id)


@router.get('/elective/{elective_id}/groups')
async def get_elective_groups(elective_id: int):
    student_service = ORMStudentService()
    return await student_service.get_groups_by_elective(elective_id)


@router.get('/all_elective')
async def get_all_elective():
    student_service = ORMStudentService()
    return await student_service.get_all_electives()
