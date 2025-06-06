from logging import getLogger

from fastapi import APIRouter

from backend.logic.services.journal_service.orm import JournalService

log = getLogger(__name__)

router = APIRouter(prefix="/journal", tags=["journal"])


@router.get("")
async def get_journal():
    journal_service = JournalService()
    result = await journal_service.get_all_records()
    return result
