from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import ClassVar, Literal
from abc import ABC, abstractmethod

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import AsyncIterable

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


import random

from redis.asyncio import StrictRedis




from sqlalchemy.exc import SQLAlchemyError

import sqlalchemy as sa


import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


import logging
from datetime import datetime
from typing import Dict, Any

from pythonjsonlogger.json import JsonFormatter




from dynaconf import Dynaconf


from sqlalchemy import select

from backend.database.database import db_session
from backend.database.models.student import Student


PROJECT_PATH = Path(__file__).parent.resolve()

settings = Dynaconf(
    root_path=PROJECT_PATH,
    envvar_prefix='',
    environments=True,
    includes=["config/*.yml"]
)



class BaseConfig(BaseSettings):
    BASE_DIR: ClassVar[Path] = Path(__file__).parent.parent.parent
    model_config = SettingsConfigDict(env_file=Path(BASE_DIR, ".env"), extra='ignore')


class FastAPISettings(BaseConfig):
    PROJECT_NAME: str
    VERSION: str
    DEBUG: bool

    HOST: str
    PORT: int

    RELOAD: bool


class LoggingSettings(BaseConfig):
    LOGGING_LEVEL: Literal["DEBUG", "INFO", "WARN", "ERROR", "FATAL"] = "INFO"

    LOGGING_FORMAT: str


class PostgresSettings(BaseConfig):
    PG_DB_USER: str
    PG_DB_PASS: str
    PG_DB_NAME: str
    PG_DB_HOST: str
    PG_DB_PORT: str

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.PG_DB_USER}:{self.PG_DB_PASS}@{self.PG_DB_HOST}:{self.PG_DB_PORT}/{self.PG_DB_NAME}"

    @property
    def test_database_url(self) -> str:
        return f"postgresql+asyncpg://{self.PG_DB_USER}:{self.PG_DB_PASS}@{self.PG_DB_HOST}:{self.PG_DB_PORT}/test_{self.PG_DB_NAME}"


class RedisSettings(BaseConfig):
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: str
    REDIS_PASSWORD: str


class SMTPSettings(BaseConfig):
    SMTP_SERVER: str
    SMTP_PORT: int
    SMTP_USERNAME: str
    SMTP_PASSWORD: str


class OTPSettings(BaseConfig):
    EXPIRATION: int = 300
    MAX_ATTEMPTS: int = 5
    MAX_SENDS: int = 5
    COOLDOWN_TIME: int = 60
    BLOCK_TIME: int = 600


@dataclass
class Config:
    postgres_settings: PostgresSettings
    app_settings: FastAPISettings
    redis_settings: RedisSettings
    logging_settings: LoggingSettings
    smtp_settings: SMTPSettings
    otp_settings: OTPSettings


@lru_cache
def get_config() -> Config:
    return Config(
        postgres_settings=PostgresSettings(),
        app_settings=FastAPISettings(),
        redis_settings=RedisSettings(),
        logging_settings=LoggingSettings(),
        smtp_settings=SMTPSettings(),
        otp_settings=OTPSettings()
    )





class DBProvider(Provider):
    @provide(scope=Scope.APP)
    def config(self) -> Config:
        return get_config()

    @provide(scope=Scope.REQUEST)
    def sqlalchemy_engine(self, config: Config) -> AsyncEngine:
        return create_async_engine(config.postgres_settings.database_url)

    @provide(scope=Scope.REQUEST)
    def session_pool(self, sqlalchemy_engine: AsyncEngine) -> async_sessionmaker:
        return async_sessionmaker(
            bind=sqlalchemy_engine, expire_on_commit=False, class_=AsyncSession
        )

    @provide(scope=Scope.REQUEST)
    async def session(
        self, async_session_maker: async_sessionmaker
    ) -> AsyncIterable[AsyncSession]:  # noqa E501
        async with async_session_maker() as session:
            yield session




class HealthCheckProvider(Provider):
    @provide(scope=Scope.REQUEST)
    async def postgres_healthcheck_service(self, session: AsyncSession) -> PostgresHealthcheckService:
        return PostgresHealthcheckService(session)

    @provide(scope=Scope.REQUEST)
    async def healthcheck_service_factory(self, postgres: PostgresHealthcheckService) -> IHealthCheckService:
        services = [
            postgres,
        ]
        return CompositeHealthCheckService(services)




class ICodeService(ABC):
    @abstractmethod
    async def generate_code(self, student_email: str):
        ...

    @abstractmethod
    async def validate_code(self, student_email: str, code: str):
        ...




config = get_config()


@dataclass
class RedisCodeService(ICodeService):
    redis: StrictRedis

    expire: int = config.otp_settings.EXPIRATION

    async def generate_code(self, student_email: str):
        code = str(random.randint(10_000, 99_999))
        await self.redis.set(student_email, code, ex=self.expire)
        return code

    async def validate_code(self, student_email: str, code: str):
        cached_code = await self.redis.get(student_email)
        if not cached_code:
            raise CodeNotFoundException(code)
        if cached_code != code:
            raise CodeNotEqualException()
        await self.redis.delete(student_email)



@dataclass
class IHealthCheckService(ABC):
    @abstractmethod
    async def check(self):
        ...





@dataclass
class PostgresHealthcheckService(IHealthCheckService):
    session: AsyncSession

    async def check(self) -> dict[str, bool]:

        try:
            cursor = await self.session.execute(sa.select(1))
            result = cursor.scalar()
            return {self.__class__.__name__: result == 1}

        except SQLAlchemyError:
            raise





@dataclass
class CompositeHealthCheckService(IHealthCheckService):
    services: list[IHealthCheckService]

    async def check(self) -> dict[str, bool]:
        ans = dict()
        for service in self.services:
            result = await service.check()
            ans.update(result)
        return ans





class ISenderService(ABC):
    @abstractmethod
    async def send_code(self, student_email: str, code: str):
        ...




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


class IStudentService(ABC):
    @abstractmethod
    async def get_student_by_email(self, student_email):
        ...



class ORMStudentService(IStudentService):
    @db_session  # TODO переделать на экзистс
    async def get_student_by_email(self, student_email, db: AsyncSession):
        stmt = select(Student).where(Student.email == student_email).limit(1)
        result = await db.scalar(stmt)
        print(result)
        return result

@dataclass(eq=False)
class ServiceException(Exception):
    @property
    def message(self):
        return 'Application exception occurred'
    


@dataclass
class CodeNotFoundException(ServiceException):
    code: str

    @property
    def message(self):
        return f'Code - {self.code} not found'


@dataclass
class CodeNotEqualException(ServiceException):

    @property
    def message(self):
        return 'Code not equal'
    

@dataclass
class SendSMTPException(ServiceException):

    @property
    def message(self):
        return 'Error sending SMTP message'



@dataclass
class AuthorizeCodeUseCase:
    student_service: IStudentService
    sender_service: ISenderService
    code_service: ICodeService

    async def execute(self, email: str):
        student = await self.student_service.get_student_by_email(email)
        print(student)
        code = await self.code_service.generate_code(student.email)
        await self.sender_service.send_code(student_email=student.email, code=code)


@dataclass
class ConfirmCodeUseCase:
    student_service: IStudentService
    code_service: ICodeService

    async def execute(self, email: str, code: str):
        await self.student_service.get_student_by_email(email)
        await self.code_service.validate_code(student_email=email, code=code)
        # логика авторизации

class CustomJsonFormatter(JsonFormatter):
    def add_fields(
            self,
            log_record: Dict[str, Any],
            record: logging.LogRecord,
            message_dict: Dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        if not log_record.get("timestamp"):
            now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            log_record["timestamp"] = now
        if log_record.get("level"):
            log_record["level"] = log_record["level"].upper()
        else:
            log_record["level"] = record.levelname


def get_formatter(logging_config: Config) -> logging.Formatter:
    return CustomJsonFormatter(
        logging_config.logging_settings.LOGGING_FORMAT
    )


def init_logging(log_level: str) -> logging.Logger:
    logger = logging.getLogger()
    log_handler = logging.StreamHandler()
    log_handler.setFormatter(get_formatter(get_config()))
    logger.addHandler(log_handler)
    logger.setLevel(log_level)
    return logger