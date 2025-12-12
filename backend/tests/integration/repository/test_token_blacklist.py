import time
import uuid

import pytest
from luml.repositories.token_blacklist import TokenBlackListRepository
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_add_token(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = TokenBlackListRepository(engine)

    token = f"test-token-test_add_token_{uuid.uuid4()}"
    expire = int(time.time()) + 60

    await repo.add_token(token, expire)
    is_blacklisted = await repo.is_token_blacklisted(token)

    assert is_blacklisted is True


@pytest.mark.asyncio
async def test_is_token_blacklisted(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = TokenBlackListRepository(engine)

    token = f"test-token-test_is_token_blacklisted_{uuid.uuid4()}"
    expire = int(time.time()) - 60

    await repo.add_token(token, expire)
    is_blacklisted = await repo.is_token_blacklisted(token)

    assert is_blacklisted is False


@pytest.mark.asyncio
async def test_delete_expired_tokens(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = TokenBlackListRepository(engine)

    token = f"test-token-test_delete_expired_tokens_{uuid.uuid4()}"
    expire = int(time.time()) - 60
    for _ in range(3):
        await repo.add_token(token, expire)

    await repo.delete_expired_tokens()
    is_blacklisted = await repo.is_token_blacklisted(token)

    assert is_blacklisted is False
