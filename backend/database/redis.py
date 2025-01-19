from redis.asyncio import StrictRedis
from backend.config import settings
from backend.project.config import RedisSettings

redis_config = RedisSettings()

redis_client = StrictRedis(
    host=redis_config.REDIS_HOST,
    port=redis_config.REDIS_PORT,
    db=redis_config.REDIS_DB,
    password=redis_config.REDIS_PASSWORD,
    decode_responses=True
)
