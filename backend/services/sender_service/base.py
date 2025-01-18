import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend.config import settings
from backend.services.zexceptions.sender import SendSMTPException


class ISenderService(ABC):
    @abstractmethod
    async def send_code(self, student_email: str, code: str):
        ...


@dataclass
class YandexSenderService(ISenderService):
    SMTP_SERVER = settings.SMTP.SERVER
    SMTP_PORT = settings.SMTP.PORT
    SMTP_USERNAME = settings.SMTP.USERNAME
    SMTP_PASSWORD = settings.SMTP.PASSWORD

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
            print(f"{student_email=}{code=}")
            print(self.SMTP_SERVER)
            print(self.SMTP_PORT)
            print(self.SMTP_USERNAME)
            print(self.SMTP_PASSWORD)
            raise SendSMTPException()
if __name__ == '__main__':
    import asyncio
    async def main():
        await YandexSenderService().send_code('vita.201581@yandex.ru','15')
    asyncio.run(main())