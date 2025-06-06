from logging import getLogger

from fastapi import APIRouter

from backend.logic.services.transfer_service.orm import ORMTransferService
from backend.logic.use_cases.optimize_transfers import OptimizeTransfers
from backend.optimization.data_for_optimization import DataGetter
from backend.optimization.ilp_method import ILPSolver

log = getLogger(__name__)

router = APIRouter(tags=["optimal"])


@router.get("/optimal")
async def optimize():
    transfer_service = ORMTransferService()
    data_getter = DataGetter
    solver = ILPSolver
    optimizer = OptimizeTransfers(solver, data_getter)
    recommended_transfer_ids = await optimizer.execute()
    all_transfers = await transfer_service.get_all_transfers()
    return {
        "transfers": all_transfers,
        "recommended_transfers": recommended_transfer_ids,
    }
