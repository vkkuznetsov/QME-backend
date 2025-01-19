import smtplib
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend.logic.services.sender_service.base import ISenderService
from backend.logic.services.zexceptions.sender import SendSMTPException
from backend.project.config import get_config

config = get_config()


@dataclass
class YandexSenderService(ISenderService):
    SMTP_SERVER = config.smtp_settings.SMTP_SERVER
    SMTP_PORT = config.smtp_settings.SMTP_PORT
    SMTP_USERNAME = config.smtp_settings.SMTP_USERNAME
    SMTP_PASSWORD = config.smtp_settings.SMTP_PASSWORD

    async def send_code(self, student_email: str, code: str):
        message = MIMEMultipart()
        message["From"] = self.SMTP_USERNAME
        message["To"] = student_email
        message["Subject"] = "Ваш код подтверждения"
        message.attach(MIMEText(f"Ваш код подтверждения: {code}", "plain"))

        try:
            with smtplib.SMTP_SSL(self.SMTP_SERVER, self.SMTP_PORT) as server:
                server.login(self.SMTP_USERNAME, self.SMTP_PASSWORD)
                server.sendmail(self.SMTP_USERNAME, student_email, message.as_string())

        except smtplib.SMTPException:
            raise SendSMTPException()
