import hashlib
import hmac
import logging

import jwt
from fastapi import HTTPException, Request
from jwt.exceptions import InvalidTokenError
from redis.asyncio import Redis
from redis.exceptions import RedisError

from luml.infra.redis import redis_client
from luml.settings import config

logger = logging.getLogger(__name__)

KEY_PREFIX = "auth-rate-limit:"
IP_LIMIT = 20
EMAIL_LIMIT = 5

CONSUME_SCRIPT = """
local attempts = redis.call('INCR', KEYS[1])
if attempts == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return {attempts, redis.call('TTL', KEYS[1])}
"""


class AuthRateLimiter:
    def __init__(self, client: Redis, window_seconds: int = 60) -> None:
        self._window_seconds = window_seconds
        self._consume = client.register_script(CONSUME_SCRIPT)

    async def consume(self, limits: dict[str, int]) -> int:
        retry_after = 0
        for key, limit in limits.items():
            attempts, ttl = await self._consume(
                keys=[f"{KEY_PREFIX}{key}"], args=[self._window_seconds]
            )
            if attempts > limit:
                retry_after = max(retry_after, ttl, 1)
        return retry_after


limiter: AuthRateLimiter | None = (
    AuthRateLimiter(redis_client) if redis_client is not None else None
)
if limiter is None:
    logger.warning("REDIS_URL is not set, authentication rate limits are disabled")


async def limit_auth_attempts(
    request: Request, email: str | None = None, *, reset_token: str | None = None
) -> None:
    if limiter is None:
        return
    if reset_token is not None:
        try:
            payload = jwt.decode(
                reset_token, config.AUTH_SECRET_KEY, algorithms=["HS256"]
            )
        except InvalidTokenError:
            payload = {}
        if payload.get("type") == "password_reset" and isinstance(
            payload.get("sub"), str
        ):
            email = payload["sub"]

    ip = request.client.host if request.client else "unknown"
    scopes = {f"ip:{ip}": IP_LIMIT}
    if email is not None:
        scopes[f"email:{email.strip().casefold()}"] = EMAIL_LIMIT
    limits = {
        hmac.new(
            config.AUTH_SECRET_KEY.encode(),
            f"{request.url.path}:{scope}".encode(),
            hashlib.sha256,
        ).hexdigest(): limit
        for scope, limit in scopes.items()
    }
    try:
        retry_after = await limiter.consume(limits)
    except RedisError:
        logger.exception("Authentication rate limiter is unavailable")
        return
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Too many authentication attempts",
            headers={"Retry-After": str(retry_after)},
        )
