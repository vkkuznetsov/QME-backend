import random
from dataclasses import dataclass

from redis.asyncio import StrictRedis
from backend.config import settings
from backend.logic.services.code_service.base import ICodeService
from backend.logic.services.zexceptions.code import CodeNotFoundException, CodeNotEqualException
from backend.project.config import get_config

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
