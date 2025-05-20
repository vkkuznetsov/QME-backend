from logging import getLogger

from fastapi import APIRouter

from backend.logic.services.student_service.orm import ORMStudentService

log = getLogger(__name__)

router = APIRouter(prefix='/recomendation', tags=['recomendation'])


@router.get('/{direction}')
async def get_recomendation(direction: str):
    student_service = ORMStudentService()
    return await student_service.get_recomendation(direction)
