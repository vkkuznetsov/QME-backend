from logging import getLogger
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.config import settings
from backend.logic.services.journal_service.orm import JournalService
from backend.logic.services.transfer_service.schemas import TransferData, TransferReorder
from backend.parse_choose import ChooseFileParser

from backend.database.redis import redis_client
from backend.logic.services.code_service.redis import RedisCodeService
from backend.logic.services.sender_service.yandex import YandexSenderService
from backend.logic.services.student_service.orm import ORMStudentService
from backend.logic.services.zexceptions.base import ServiceException
from backend.logic.use_cases.authorize_code import AuthorizeCodeUseCase
from backend.logic.use_cases.confirm_code import ConfirmCodeUseCase
from backend.logic.use_cases.create_transfer import CreateTransferUseCase
from backend.logic.services.transfer_service.orm import ORMTransferService
from backend.parse_course import ElectiveFileParser

log = getLogger(__name__)

OTP_EXPIRATION = settings.OTP.EXPIRATION
MAX_ATTEMPTS = settings.OTP.MAX_ATTEMPTS
MAX_SENDS = settings.OTP.MAX_SENDS
COOLDOWN_TIME = settings.OTP.COOLDOWN_TIME
BLOCK_TIME = settings.OTP.BLOCK_TIME


class API:
    def __init__(self):
        self._router = APIRouter()
        self._setup_routes()

    @property
    def router(self):
        return self._router

    def _setup_routes(self):
        self.router.add_api_route("/student_info", self.get_student, methods=["GET"])
        self.router.add_api_route("/students", self.get_students, methods=["GET"])
        self.router.add_api_route("/elective/{elective_id}", self.get_elective, methods=["GET"])
        self.router.add_api_route("/elective/{elective_id}/groups", self.get_elective_groups, methods=["GET"])
        self.router.add_api_route("/all_elective", self.get_all_elective, methods=["GET"])

        self.router.add_api_route("/recomendation/{direction}", self.get_recomendation, methods=["GET"])

        self.router.add_api_route("/upload/student-choices", self.handle_student_choices, methods=["POST"])
        self.router.add_api_route("/upload/courses-info", self.handle_courses_info, methods=["POST"])

        self.router.add_api_route("/auth/send-otp", self.send_otp, methods=["POST"])
        self.router.add_api_route("/auth/verify-otp", self.verify_otp, methods=["POST"])

        self.router.add_api_route("/transfer", self.create_transfer, methods=["POST"])
        self.router.add_api_route("/transfer", self.get_student_transfers, methods=["GET"])
        self.router.add_api_route('/transfer/{transfer_id}', self.delete_transfer, methods=['DELETE'])
        self.router.add_api_route("/all_transfer", self.get_all_transfers, methods=["GET"])
        self.router.add_api_route("/transfer/approve/{transfer_id}", self.approve_transfer, methods=["POST"])
        self.router.add_api_route("/transfer/reject/{transfer_id}", self.reject_transfer, methods=["POST"])
        self.router.add_api_route("/transfer/reorder", self.reorder_transfers, methods=["POST"])

        self.router.add_api_route('/journal', self.get_journal, methods=['GET'])

    async def get_student(self, email: str):
        student_service = ORMStudentService()
        return await student_service.get_student_group_elective_email(email)

    async def get_students(self):
        student_service = ORMStudentService()
        return await student_service.get_all_student_group_elective_email()

    async def get_elective(self, elective_id: int):
        student_service = ORMStudentService()
        return await student_service.get_groups_students_by_elective(elective_id)

    async def get_recomendation(self, direction: str):
        student_service = ORMStudentService()
        return await student_service.get_recomendation(direction)

    async def get_elective_groups(self, elective_id: int):
        student_service = ORMStudentService()
        return await student_service.get_groups_by_elective(elective_id)

    async def get_all_elective(self):
        student_service = ORMStudentService()
        return await student_service.get_all_electives()

    async def handle_student_choices(self, file: UploadFile = File(...)):
        await ChooseFileParser.reset_database()
        journal_service = JournalService()
        parser = ChooseFileParser(file)

        await journal_service.add_record_upload_choose()
        await parser()
        return {"filename": file.filename}

    async def handle_courses_info(self, file:UploadFile = File(...)):

        journal_service = JournalService()
        parser = ElectiveFileParser(file)

        await journal_service.add_record_upload_elective()
        await parser()
        return {"filename": file.filename}

    async def send_otp(self, email: str = Form(...)):
        try:
            student_service = ORMStudentService()
            sender_service = YandexSenderService()
            code_service = RedisCodeService(redis_client)

            await AuthorizeCodeUseCase(student_service, sender_service, code_service).execute(email)
            return {"message": f"sent successfully to {email}"}
        except ServiceException as e:
            return HTTPException(detail=e.message, status_code=400)

    async def verify_otp(self, email: str = Form(...), otp: str = Form(...)):
        student_service = ORMStudentService()
        code_service = RedisCodeService(redis_client)

        use_case = ConfirmCodeUseCase(student_service, code_service)
        try:
            await use_case.execute(email, otp)
            return {"status": "success"}
        except ServiceException as e:
            raise HTTPException(detail=e.message, status_code=404)

    async def create_transfer(self, transfer: TransferData):
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

    async def delete_transfer(self, transfer_id: int):
        transfer_service = ORMTransferService()
        result = await transfer_service.delete_transfer(transfer_id=transfer_id)
        return result

    async def get_student_transfers(self, student_id: int):
        try:
            transfer_service = ORMTransferService()
            transfers = await transfer_service.get_transfer_by_student_id(student_id)
            return transfers
        except ServiceException as e:
            raise HTTPException(detail=e.message, status_code=404)

    async def get_all_transfers(self):
        try:
            transfer_service = ORMTransferService()
            transfers = await transfer_service.get_all_transfers()
            return transfers
        except ServiceException as e:
            raise HTTPException(detail=e.message, status_code=400)

    async def approve_transfer(self, transfer_id: int):
        transfer_service = ORMTransferService()
        result = await transfer_service.approve_transfer(transfer_id)
        return result

    async def reject_transfer(self, transfer_id: int):
        transfer_service = ORMTransferService()
        result = await transfer_service.reject_transfer(transfer_id)
        return result

    async def reorder_transfers(self, order: List[TransferReorder]):
        transfer_service = ORMTransferService()
        result = await transfer_service.reorder_transfers(order)
        return result

    async def get_journal(self):
        journal_service = JournalService()
        result = await journal_service.get_all_records()
        return result
