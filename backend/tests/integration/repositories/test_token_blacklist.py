import time
import uuid

import pytest
from luml.repositories.token_blacklist import TokenBlackListRepository
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def repository(engine: AsyncEngine) -> TokenBlackListRepository:
    return TokenBlackListRepository(engine)


class TestTokenBlackListRepository:
    async def test_add_token_blacklists_token(
        self, repository: TokenBlackListRepository
    ) -> None:
        token = f"test-token-test_add_token_{uuid.uuid4()}"
        expire = int(time.time()) + 60

        await repository.add_token(token, expire)
        is_blacklisted = await repository.is_token_blacklisted(token)

        assert is_blacklisted is True

    async def test_is_token_blacklisted_returns_false_when_token_expired(
        self, repository: TokenBlackListRepository
    ) -> None:
        token = f"test-token-test_is_token_blacklisted_{uuid.uuid4()}"
        expire = int(time.time()) - 60

        await repository.add_token(token, expire)
        is_blacklisted = await repository.is_token_blacklisted(token)

        assert is_blacklisted is False

    async def test_delete_expired_tokens_removes_expired_token(
        self, repository: TokenBlackListRepository
    ) -> None:
        token = f"test-token-test_delete_expired_tokens_{uuid.uuid4()}"
        expire = int(time.time()) - 60
        for _ in range(3):
            await repository.add_token(token, expire)

        await repository.delete_expired_tokens()
        is_blacklisted = await repository.is_token_blacklisted(token)

        assert is_blacklisted is False
