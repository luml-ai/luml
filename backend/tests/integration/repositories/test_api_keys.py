import uuid

import pytest
from luml.repositories.users import UserRepository
from luml.schemas.user import (
    CreateUser,
    UpdateUserAPIKey,
)
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def repository(engine: AsyncEngine) -> UserRepository:
    return UserRepository(engine)


class TestUserApiKeyRepository:
    async def test_create_user_api_key_returns_true(
        self, repository: UserRepository, new_user: CreateUser
    ) -> None:
        created_user = await repository.create_user(new_user)

        api_key_update = UpdateUserAPIKey(
            id=created_user.id, hashed_api_key="api_key_hash"
        )
        result = await repository.create_user_api_key(api_key_update)

        assert created_user
        assert result is True

    async def test_get_user_by_api_key_hash_returns_key_owner(
        self, repository: UserRepository, new_user: CreateUser
    ) -> None:
        created_user = await repository.create_user(new_user)

        api_key_hash = f"test_api_key_hash_{uuid.uuid4()}"
        api_key_update = UpdateUserAPIKey(
            id=created_user.id, hashed_api_key=api_key_hash
        )
        await repository.create_user_api_key(api_key_update)

        fetched_user = await repository.get_user_by_api_key_hash(api_key_hash)

        assert fetched_user
        assert fetched_user.id == created_user.id
        assert fetched_user.has_api_key is True

    async def test_delete_api_key_by_user_id_removes_key(
        self, repository: UserRepository, new_user: CreateUser
    ) -> None:
        created_user = await repository.create_user(new_user)
        assert created_user
        key_hash = f"api_key_hash_{uuid.uuid4()}"

        api_key_update = UpdateUserAPIKey(id=created_user.id, hashed_api_key=key_hash)
        await repository.create_user_api_key(api_key_update)

        user_with_key = await repository.get_public_user_by_id(created_user.id)
        assert user_with_key
        assert user_with_key.has_api_key is True

        await repository.delete_api_key_by_user_id(created_user.id)

        user_without_key = await repository.get_public_user_by_id(created_user.id)
        assert user_without_key
        assert user_without_key.has_api_key is False

        fetched_user = await repository.get_user_by_api_key_hash(key_hash)
        assert fetched_user is None
