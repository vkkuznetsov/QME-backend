from logging import getLogger

from fastapi import APIRouter

from backend.logic.services.student_service.orm import ORMStudentService

log = getLogger(__name__)

router = APIRouter(prefix='/recomendation', tags=['recomendation'])


@router.get('/{direction}')
async def get_recomendation(direction: str):
    student_service = ORMStudentService()
    return await student_service.get_staistic(direction)


@router.get('/recommendation/{student_id}')
async def get_student_recommendation(student_id: int):
    student_service = ORMStudentService()
    return await student_service.get_student_recommendation(student_id)
