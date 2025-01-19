from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import ClassVar, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


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


if __name__ == "__main__":
    config = get_config()
    print(config)
