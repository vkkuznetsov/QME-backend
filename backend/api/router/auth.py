from logging import getLogger

from fastapi import APIRouter, Body, HTTPException

from backend.config import settings
from backend.database.redis import redis_client
from backend.logic.services.code_service.redis import RedisCodeService
from backend.logic.services.manager_service.orm import ManagerService
from backend.logic.services.sender_service.yandex import YandexSenderService
from backend.logic.services.student_service.orm import ORMStudentService
from backend.logic.services.zexceptions.base import ServiceException
from backend.logic.use_cases.authorize_code import AuthorizeCodeUseCase
from backend.logic.use_cases.confirm_code import ConfirmCodeUseCase

log = getLogger(__name__)

OTP_EXPIRATION = settings.OTP.EXPIRATION
MAX_ATTEMPTS = settings.OTP.MAX_ATTEMPTS
MAX_SENDS = settings.OTP.MAX_SENDS
COOLDOWN_TIME = settings.OTP.COOLDOWN_TIME
BLOCK_TIME = settings.OTP.BLOCK_TIME

router = APIRouter(prefix='/auth', tags=['auth'])


@router.post('/send-otp')
async def send_otp(email: str = Body(...)):
    try:
        student_service = ORMStudentService()
        manager_service = ManagerService()
        sender_service = YandexSenderService()
        code_service = RedisCodeService(redis_client)

        await AuthorizeCodeUseCase(student_service, manager_service, sender_service, code_service).execute(email)
        return {"message": f"sent successfully to {email}"}
    except ServiceException as e:
        return HTTPException(detail=e.message, status_code=400)


@router.post('/verify-otp')
async def verify_otp(email: str = Body(...), otp: str = Body(...)):
    student_service = ORMStudentService()
    manager_service = ManagerService()
    code_service = RedisCodeService(redis_client)

    use_case = ConfirmCodeUseCase(student_service, manager_service, code_service)
    try:
        role, url = await use_case.execute(email, otp)
        return {"status": "success", "role": role, 'redirectUrl': url}
    except ServiceException as e:
        raise HTTPException(detail=e.message, status_code=404)
