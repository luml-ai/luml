import asyncio

from luml.infra.auth_rate_limits import AuthRateLimiter
from redis.asyncio import Redis


class TestAuthRateLimiter:
    async def test_limits_are_atomic_across_concurrent_requests(
        self, redis_client: Redis
    ) -> None:
        limiter = AuthRateLimiter(redis_client)

        results = await asyncio.gather(
            *(limiter.consume({"email": 5}) for _ in range(20))
        )

        assert results.count(0) == 5
        assert all(0 < retry_after <= 60 for retry_after in results if retry_after)
        assert len([retry_after for retry_after in results if retry_after]) == 15

    async def test_scopes_are_independent_and_denied_attempts_count(
        self, redis_client: Redis
    ) -> None:
        limiter = AuthRateLimiter(redis_client)

        assert await limiter.consume({"ip-one": 2, "email-one": 1}) == 0
        assert await limiter.consume({"ip-two": 2, "email-one": 1}) > 0
        assert await limiter.consume({"ip-one": 2, "email-two": 1}) == 0
        assert await limiter.consume({"ip-one": 2, "email-three": 1}) > 0
        assert await limiter.consume({"ip-one": 2}) > 0

    async def test_counters_expire_with_the_window(self, redis_client: Redis) -> None:
        limiter = AuthRateLimiter(redis_client, window_seconds=1)

        assert await limiter.consume({"email": 1}) == 0
        assert await limiter.consume({"email": 1}) == 1
        await asyncio.sleep(1.1)
        assert await limiter.consume({"email": 1}) == 0
        assert await redis_client.ttl("auth-rate-limit:email") == 1
