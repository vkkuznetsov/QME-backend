from fastapi import APIRouter, Depends

from backend.logic.services.elective_service.orm import ORMElectiveService
from backend.schemas.elective import ElectiveSchema, GroupSchema

router = APIRouter(tags=['elective'])


@router.get('/all_elective')
async def get_all_elective(
        elective_service: ORMElectiveService = Depends()
):
    return await elective_service.get_all_electives()


@router.get('/elective/{elective_id}', response_model=ElectiveSchema)
async def get_elective(
        elective_id: int,
        elective_service: ORMElectiveService = Depends()
):
    return await elective_service.get_groups_students_by_elective(elective_id)


@router.get('/elective/{elective_id}/groups', response_model=list[GroupSchema])
async def get_elective_groups(
        elective_id: int,
        elective_service: ORMElectiveService = Depends()
):
    return await elective_service.get_groups_by_elective(elective_id)
