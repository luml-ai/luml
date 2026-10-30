from redis.asyncio import Redis

from luml.settings import config

redis_client: Redis = Redis.from_url(config.REDIS_URL)
