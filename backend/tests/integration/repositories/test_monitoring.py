import time
from uuid import uuid7

import pytest
from luml.repositories.monitoring import MonitoringLaunchTokenRepository
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def repository(engine: AsyncEngine) -> MonitoringLaunchTokenRepository:
    return MonitoringLaunchTokenRepository(engine)


class TestMonitoringLaunchTokenRepository:
    async def test_consume_returns_false_when_jti_already_consumed(
        self, repository: MonitoringLaunchTokenRepository
    ) -> None:
        jti = uuid7()
        expire = int(time.time()) + 60

        first = await repository.consume(jti, expire)
        second = await repository.consume(jti, expire)

        assert first is True
        assert second is False

    async def test_consume_returns_true_for_distinct_jtis(
        self, repository: MonitoringLaunchTokenRepository
    ) -> None:
        expire = int(time.time()) + 60

        assert await repository.consume(uuid7(), expire) is True
        assert await repository.consume(uuid7(), expire) is True

    async def test_consume_succeeds_again_when_expired_jti_was_deleted(
        self, repository: MonitoringLaunchTokenRepository
    ) -> None:
        jti = uuid7()
        expire = int(time.time()) - 60

        assert await repository.consume(jti, expire) is True
        assert await repository.consume(jti, expire) is True
