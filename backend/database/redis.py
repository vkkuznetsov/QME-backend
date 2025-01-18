from redis.asyncio import StrictRedis
from backend.config import settings

redis_client = StrictRedis(
    host=settings.REDIS.HOST,
    port=settings.REDIS.PORT,
    db=settings.REDIS.DB,
    password=settings.REDIS.PASSWORD,
    decode_responses=True
)
