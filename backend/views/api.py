from fastapi import APIRouter, UploadFile, File, HTTPException, Form
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from logging import getLogger
import random
import redis
from dotenv import load_dotenv
import os

load_dotenv()

log = getLogger()

redis_client = redis.StrictRedis(host="localhost", port=6379, db=0, decode_responses=True)

SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")


class API:
    def __init__(self):
        self._router = APIRouter()
        self._setup_routes()

    @property
    def router(self):
        return self._router

    def _setup_routes(self):
        self.router.add_api_route("/upload/data1", self.handle_txt_file, methods=["POST"])
        self.router.add_api_route('/upload/data2', self.handle_csv_file, methods=["POST"])
        self.router.add_api_route("/auth/send-otp", self.send_otp, methods=["POST"])
        self.router.add_api_route("/auth/verify-otp", self.verify_otp, methods=["POST"])

    async def handle_txt_file(self, file: UploadFile = File(...)):
        log.info("Получен файл")
        return {"filename": file.filename}

    async def handle_csv_file(self, file: UploadFile = File(...)):
        return {"filename": file.filename}
    
    # Отправка OTP
    async def send_otp(self, email: str = Form(...)):
        otp = random.randint(100000, 999999)

        redis_client.setex(f"otp:{email}", 300, otp)

        try:
            message = MIMEMultipart()
            message["From"] = SMTP_USERNAME
            message["To"] = email
            message["Subject"] = "Ваш код подтверждения"

            body = f"Ваш код подтверждения: {otp}"
            message.attach(MIMEText(body, "plain"))

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
        stored_otp = redis_client.get(f"otp:{email}")

        if stored_otp is None:
            log.info(f"OTP для {email} отсутствует или истёк.")
            raise HTTPException(status_code=400, detail="OTP истек или не запрашивался.")

        if stored_otp != otp:
            log.info(f"Неверный OTP для {email}. Введённый: {otp}, ожидаемый: {stored_otp}")
            raise HTTPException(status_code=400, detail="Неверный OTP.")

        log.info(f"OTP для {email} успешно подтверждён.")
        redis_client.delete(f"otp:{email}")
        return {"message": "OTP успешно подтвержден!"}