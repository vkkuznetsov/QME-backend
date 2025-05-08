from logging import getLogger

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.business_logic import AuthorizeCodeUseCase, ConfirmCodeUseCase, ORMStudentService, RedisCodeService, ServiceException, YandexSenderService
from backend.config import settings
from backend.database.redis import redis_client

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
        self.router.add_api_route("/student", self.get_student, methods=["GET"])
        self.router.add_api_route("/upload/student-choices", self.handle_student_choices, methods=["POST"])
        self.router.add_api_route("/auth/send-otp", self.send_otp, methods=["POST"])
        self.router.add_api_route("/auth/verify-otp", self.verify_otp, methods=["POST"])

    async def handle_student_choices(self, file: UploadFile = File(...)):
        log.info("Получен файл")
        return {"filename": file.filename}

    async def get_student(self, email: str):
        return email

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
