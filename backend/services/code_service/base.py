import random
from abc import ABC, abstractmethod
from dataclasses import dataclass

from redis.asyncio import StrictRedis
from backend.config import settings
from backend.services.zexceptions.code import CodeNotFoundException, CodeNotEqualException


class ICodeService(ABC):
    @abstractmethod
    async def generate_code(self, student_email: str):
        ...

    @abstractmethod
    async def validate_code(self, student_email: str, code: str):
        ...


@dataclass
class RedisCodeService(ICodeService):
    redis: StrictRedis

    expire = settings.OTP.EXPIRATION

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

