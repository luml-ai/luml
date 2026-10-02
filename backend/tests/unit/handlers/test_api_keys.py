import pytest
from luml.handlers.api_keys import APIKeyHandler
from luml.infra.exceptions import UserAPIKeyCreateError
from luml.schemas.user import APIKeyCreateOut, UserOut

from tests.support.ids import USER_ID
from tests.support.mocks import CollaboratorMocks, mock_collaborators


@pytest.fixture
def mocks() -> CollaboratorMocks[APIKeyHandler]:
    return mock_collaborators(APIKeyHandler())


class TestAPIKeyHandler:
    async def test_create_user_api_key_returns_prefixed_key(
        self, mocks: CollaboratorMocks[APIKeyHandler]
    ) -> None:
        mocks.user_repository.create_user_api_key.return_value = True

        result = await mocks.handler.create_user_api_key(USER_ID)

        assert isinstance(result, APIKeyCreateOut)
        assert result.key is not None
        assert result.key.startswith("dfs_")
        mocks.user_repository.create_user_api_key.assert_awaited_once()

    async def test_create_user_api_key_raises_when_repository_fails(
        self, mocks: CollaboratorMocks[APIKeyHandler]
    ) -> None:
        mocks.user_repository.create_user_api_key.return_value = False

        with pytest.raises(UserAPIKeyCreateError):
            await mocks.handler.create_user_api_key(USER_ID)

    async def test_authenticate_api_key_returns_user(
        self, mocks: CollaboratorMocks[APIKeyHandler]
    ) -> None:
        expected_user = UserOut(
            id=USER_ID,
            email="test@example.com",
            full_name="Test User",
            disabled=False,
            photo=None,
            has_api_key=True,
        )
        mocks.user_repository.get_user_by_api_key_hash.return_value = expected_user

        result = await mocks.handler.authenticate_api_key("dfs_test_api_key")

        assert result == expected_user
        mocks.user_repository.get_user_by_api_key_hash.assert_awaited_once()

    async def test_authenticate_api_key_returns_none_when_key_unknown(
        self, mocks: CollaboratorMocks[APIKeyHandler]
    ) -> None:
        mocks.user_repository.get_user_by_api_key_hash.return_value = None

        result = await mocks.handler.authenticate_api_key("invalid_api_key")

        assert result is None
        mocks.user_repository.get_user_by_api_key_hash.assert_awaited_once()

    async def test_delete_user_api_key_deletes_by_user_id(
        self, mocks: CollaboratorMocks[APIKeyHandler]
    ) -> None:
        await mocks.handler.delete_user_api_key(USER_ID)

        mocks.user_repository.delete_api_key_by_user_id.assert_awaited_once_with(
            USER_ID
        )
