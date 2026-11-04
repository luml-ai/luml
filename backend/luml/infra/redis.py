from redis.asyncio import Redis

from luml.settings import config

redis_client: Redis | None = (
    Redis.from_url(config.REDIS_URL) if config.REDIS_URL else None
)
