from logging import getLogger

from fastapi import APIRouter, File, UploadFile

from backend.logic.services.journal_service.orm import JournalService
from backend.parse_choose import ChooseFileParser
from backend.parse_course import ElectiveFileParser
from backend.parse_students import StudentsDataParser

log = getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/student-choices")
async def handle_student_choices(file: UploadFile = File(...)):
    journal_service = JournalService()
    parser = ChooseFileParser(
        file, reset=False
    )  # reset=False will append data; set to True to drop and recreate

    await journal_service.add_record_upload_choose()
    await parser()
    await journal_service.add_record_upload_choose_success()

    return {"filename": file.filename}


# Endpoint to update Student.diagnostics and Student.competencies from uploaded Excel files
@router.post("/update-students-data")
async def update_students_data(
    diagnostics_file: UploadFile = File(...), competencies_file: UploadFile = File(...)
):
    parser = StudentsDataParser(diagnostics_file, competencies_file)
    await parser()
    return {"status": "students data updated"}


@router.post("/courses-info")
async def handle_courses_info(file: UploadFile = File(...)):
    journal = JournalService()
    parser = ElectiveFileParser(file)

    await journal.add_record_upload_elective()
    await parser()
    await journal.add_record_upload_elective_success()

    return {"filename": file.filename}
