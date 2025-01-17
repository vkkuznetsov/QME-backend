import os
import random
import smtplib
from datetime import datetime, timedelta
from logging import getLogger
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import redis
from dotenv import load_dotenv
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

load_dotenv()

log = getLogger()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

redis_client = redis.StrictRedis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True
)

SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

OTP_EXPIRATION = int(os.getenv("OTP_EXPIRATION", 300))
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", 5))
MAX_SENDS = int(os.getenv("MAX_SENDS", 5))
COOLDOWN_TIME = int(os.getenv("COOLDOWN_TIME", 60))
BLOCK_TIME = int(os.getenv("BLOCK_TIME", 600))

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
    
    # Отправка OTP
    async def send_otp(self, email: str = Form(...)):
        last_sent_key = f"otp_last_sent:{email}"
        last_sent = redis_client.get(last_sent_key)
        if last_sent:
            last_sent_time = datetime.fromisoformat(last_sent)
            cooldown = timedelta(seconds=COOLDOWN_TIME)
            if datetime.now() - last_sent_time < cooldown:
                raise HTTPException(
                    status_code=429,
                    detail="Слишком частые запросы. Попробуйте позже."
                )

        send_count_key = f"otp_send_count:{email}"
        send_count = redis_client.get(send_count_key)
        if send_count and int(send_count) >= MAX_SENDS:
            raise HTTPException(
                status_code=429,
                detail="Превышен лимит отправки. Попробуйте позже."
            )

        otp = random.randint(100000, 999999)
        redis_client.setex(f"otp:{email}", OTP_EXPIRATION, otp)

        redis_client.set(last_sent_key, datetime.now().isoformat(), ex=OTP_EXPIRATION)
        redis_client.incr(send_count_key)
        redis_client.expire(send_count_key, 3600)

        try:
            message = MIMEMultipart()
            message["From"] = SMTP_USERNAME
            message["To"] = email
            message["Subject"] = "Ваш код подтверждения"
            message.attach(MIMEText(f"Ваш код подтверждения: {otp}", "plain"))

            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.sendmail(SMTP_USERNAME, email, message.as_string())

            log.info(f"OTP отправлен на {email}")
            return {"message": "OTP отправлен на ваш email."}
        except smtplib.SMTPException as e:
            log.error(f"Ошибка при отправке OTP: {e}")
            raise HTTPException(status_code=500, detail="Ошибка при отправке OTP")
    
    # Проверка OTP
    async def verify_otp(self, email: str = Form(...), otp: str = Form(...)):
        lock_key = f"otp_lock:{email}"
        if redis_client.get(lock_key):
            raise HTTPException(
                status_code=429,
                detail="Вы временно заблокированы. Попробуйте позже."
            )

        stored_otp = redis_client.get(f"otp:{email}")
        if stored_otp is None:
            log.info(f"OTP для {email} отсутствует или истёк.")
            raise HTTPException(status_code=400, detail="OTP истек или не запрашивался.")

        if stored_otp != otp:
            attempt_key = f"otp_attempts:{email}"
            attempts = redis_client.incr(attempt_key)
            redis_client.expire(attempt_key, OTP_EXPIRATION)

            if int(attempts) >= MAX_ATTEMPTS:
                redis_client.setex(lock_key, BLOCK_TIME, "blocked")
                log.warning(f"{email} заблокирован из-за превышения попыток")
                raise HTTPException(
                    status_code=429,
                    detail="Превышено количество попыток. Вы временно заблокированы."
                )

            log.info(f"Неверный OTP для {email}. Осталось попыток: {MAX_ATTEMPTS - int(attempts)}")
            raise HTTPException(
                status_code=400,
                detail=f"Неверный OTP. Осталось попыток: {MAX_ATTEMPTS - int(attempts)}"
            )

        log.info(f"OTP для {email} успешно подтвержден.")
        redis_client.delete(f"otp:{email}")
        redis_client.delete(f"otp_attempts:{email}")
        return {"message": "OTP успешно подтвержден!"}