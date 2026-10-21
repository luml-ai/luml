import asyncio
from unittest.mock import patch

from luml.models import AuthRateLimitOrm
from luml.repositories.auth_rate_limits import AuthRateLimitRepository
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


async def test_limits_are_atomic_across_repository_instances(
    engine: AsyncEngine,
) -> None:
    repositories = [AuthRateLimitRepository(engine) for _ in range(20)]
    with patch("luml.repositories.auth_rate_limits.time", return_value=120):
        results = await asyncio.gather(
            *(repo.consume({"email": 5}) for repo in repositories)
        )

    assert results.count(0) == 5
    assert results.count(60) == 15


async def test_scopes_expire_and_old_counters_are_removed(engine: AsyncEngine) -> None:
    repository = AuthRateLimitRepository(engine)
    with patch("luml.repositories.auth_rate_limits.time", return_value=120):
        assert await repository.consume({"ip-one": 2, "email-one": 1}) == 0
        assert await repository.consume({"ip-two": 2, "email-one": 1}) == 60
        assert await repository.consume({"ip-one": 2, "email-two": 1}) == 0
        assert await repository.consume({"ip-one": 2, "email-three": 1}) == 60
    with patch("luml.repositories.auth_rate_limits.time", return_value=150):
        assert await repository.consume({"ip-one": 2}) == 30
    with patch("luml.repositories.auth_rate_limits.time", return_value=180):
        assert await repository.consume({"ip-one": 2, "email-one": 1}) == 0

    async with AsyncSession(engine) as session:
        assert (
            await session.scalar(select(func.count()).select_from(AuthRateLimitOrm))
            == 2
        )
