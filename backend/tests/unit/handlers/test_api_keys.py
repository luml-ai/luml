from unittest.mock import AsyncMock, patch

import pytest

from dataforce_studio.handlers import APIKeyHandler
from dataforce_studio.infra.exceptions import UserAPIKeyCreateError
from dataforce_studio.schemas import APIKeyCreateOut, UserOut

handler = APIKeyHandler()


@patch(
    "dataforce_studio.handlers.api_keys.UserRepository.create_user_api_key",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_user_api_key(
    mock_create_user_api_key: AsyncMock,
) -> None:
    user_id = "cLZHBYAXuzDCWTTQ9ouoXa"
    mock_create_user_api_key.return_value = True

    result = await handler.create_user_api_key(user_id)

    assert isinstance(result, APIKeyCreateOut)
    assert result.key is not None
    assert result.key.startswith("dfs_")
    mock_create_user_api_key.assert_awaited_once()


@patch(
    "dataforce_studio.handlers.api_keys.UserRepository.create_user_api_key",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_user_api_key_failed(
    mock_create_user_api_key: AsyncMock,
) -> None:
    user_id = "cLZHBYAXuzDCWTTQ9ouoXa"
    mock_create_user_api_key.return_value = False

    with pytest.raises(UserAPIKeyCreateError):
        await handler.create_user_api_key(user_id)


@patch(
    "dataforce_studio.handlers.api_keys.UserRepository.get_user_by_api_key_hash",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_authenticate_api_key(
    mock_get_user_by_api_key_hash: AsyncMock,
) -> None:
    expected_user = UserOut(
        id="cLZHBYAXuzDCWTTQ9ouoXa",
        email="test@example.com",
        full_name="Test User",
        disabled=False,
        photo=None,
        has_api_key=True,
    )
    mock_get_user_by_api_key_hash.return_value = expected_user

    result = await handler.authenticate_api_key("dfs_test_api_key")

    assert result == expected_user
    mock_get_user_by_api_key_hash.assert_awaited_once()


@patch(
    "dataforce_studio.handlers.api_keys.UserRepository.get_user_by_api_key_hash",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_authenticate_api_key_not_found(
    mock_get_user_by_api_key_hash: AsyncMock,
) -> None:
    mock_get_user_by_api_key_hash.return_value = None

    result = await handler.authenticate_api_key("invalid_api_key")

    assert result is None
    mock_get_user_by_api_key_hash.assert_awaited_once()


@patch(
    "dataforce_studio.handlers.api_keys.UserRepository.delete_api_key_by_user_id",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_user_api_key(
    mock_delete_api_key_by_user_id: AsyncMock,
) -> None:
    user_id = "cLZHBYAXuzDCWTTQ9ouoXa"

    await handler.delete_user_api_key(user_id)

    mock_delete_api_key_by_user_id.assert_awaited_once_with(user_id)
