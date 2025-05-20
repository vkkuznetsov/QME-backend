from logging import getLogger

from fastapi import APIRouter, File, UploadFile

from backend.logic.services.journal_service.orm import JournalService

from backend.parse_choose import ChooseFileParser
from backend.parse_course import ElectiveFileParser

log = getLogger(__name__)

router = APIRouter(prefix='/upload', tags=['upload'])


@router.post('/student-choices')
async def handle_student_choices(file: UploadFile = File(...)):
    journal_service = JournalService()
    parser = ChooseFileParser(file)
    await ChooseFileParser.reset_database()

    await journal_service.add_record_upload_choose()
    await parser()
    await journal_service.add_record_upload_choose_success()

    return {"filename": file.filename}


@router.post('/courses-info')
async def handle_courses_info(file: UploadFile = File(...)):
    journal = JournalService()
    parser = ElectiveFileParser(file)

    await journal.add_record_upload_elective()
    await parser()
    await journal.add_record_upload_elective_success()

    return {"filename": file.filename}
