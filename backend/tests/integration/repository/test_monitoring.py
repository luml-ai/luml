import time
from uuid import uuid7

import pytest
from luml.repositories.monitoring import MonitoringLaunchTokenRepository
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_consume_is_single_use(
    create_database_and_apply_migrations: str,
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = MonitoringLaunchTokenRepository(engine)

    jti = uuid7()
    expire = int(time.time()) + 60

    first = await repo.consume(jti, expire)
    second = await repo.consume(jti, expire)

    assert first is True
    assert second is False


@pytest.mark.asyncio
async def test_consume_distinct_jtis_succeed(
    create_database_and_apply_migrations: str,
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = MonitoringLaunchTokenRepository(engine)

    expire = int(time.time()) + 60

    assert await repo.consume(uuid7(), expire) is True
    assert await repo.consume(uuid7(), expire) is True


@pytest.mark.asyncio
async def test_expired_jti_is_cleaned_up(
    create_database_and_apply_migrations: str,
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = MonitoringLaunchTokenRepository(engine)

    jti = uuid7()
    expire = int(time.time()) - 60

    # consume() calls delete_expired_tokens(), so an already-expired jti is
    # removed and does not block a later consume of the same jti.
    assert await repo.consume(jti, expire) is True
    assert await repo.consume(jti, expire) is True
