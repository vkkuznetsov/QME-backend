from logging import getLogger
from typing import List

from fastapi import APIRouter, HTTPException, Depends

from backend.logic.services.student_service.orm import ORMStudentService
from backend.logic.services.transfer_service.orm import ORMTransferService
from backend.logic.services.transfer_service.schemas import TransferData, TransferReorder
from backend.logic.services.zexceptions.base import ServiceException
from backend.logic.use_cases.create_transfer import CreateTransferUseCase

log = getLogger(__name__)

router = APIRouter(tags=['transfer'])


@router.get('/transfer')
async def get_student_transfers(student_id: int):
    try:
        transfer_service = ORMTransferService()
        transfers = await transfer_service.get_transfer_by_student_id(student_id)
        return transfers
    except ServiceException as e:
        raise HTTPException(detail=e.message, status_code=404)


@router.post('/transfer')
async def create_transfer(transfer: TransferData):
    try:
        student_service = ORMStudentService()
        transfer_service = ORMTransferService()

        result = await CreateTransferUseCase(student_service, transfer_service).execute(
            student_id=transfer.student_id,
            from_elective_id=transfer.from_elective_id,
            to_elective_id=transfer.to_elective_id,
            groups_to_ids=transfer.groups_to_ids
        )
        return result
    except ServiceException as e:
        raise HTTPException(detail=e.message, status_code=400)


@router.delete('/transfer/{transfer_id}')
async def delete_transfer(transfer_id: int):
    transfer_service = ORMTransferService()
    result = await transfer_service.delete_transfer(transfer_id=transfer_id)
    return result


@router.get('/all_transfer')
async def get_all_transfers():
    try:
        transfer_service = ORMTransferService()
        transfers = await transfer_service.get_all_transfers()
        return transfers
    except ServiceException as e:
        raise HTTPException(detail=e.message, status_code=400)


from pydantic import BaseModel


class TransferActionRequest(BaseModel):
    manager_id: int


@router.post('/transfer/approve/{transfer_id}')
async def approve_transfer(
        transfer_id: int,
        request: TransferActionRequest,
        transfer_service: ORMTransferService = Depends(),
):
    return await transfer_service.approve_transfer(transfer_id, request.manager_id)


@router.post('/transfer/reject/{transfer_id}')
async def reject_transfer(
        transfer_id: int,
        request: TransferActionRequest,
        transfer_service: ORMTransferService = Depends(),
):
    return await transfer_service.reject_transfer(transfer_id, request.manager_id)


@router.post('/transfer/reorder')
async def reorder_transfers(order: List[TransferReorder]):
    transfer_service = ORMTransferService()
    result = await transfer_service.reorder_transfers(order)
    return result


@router.get('/transfer/active-count')
async def count_active_transfers(
        transfer_service: ORMTransferService = Depends()
) -> int:
    result = await transfer_service.count_active_transfer()
    return result
