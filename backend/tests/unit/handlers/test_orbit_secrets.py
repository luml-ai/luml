import datetime
from unittest.mock import AsyncMock, patch

import pytest

from dataforce_studio.handlers.orbit_secrets import OrbitSecretHandler
from dataforce_studio.infra.exceptions import NotFoundError
from dataforce_studio.schemas.orbit_secret import (
    OrbitSecret,
    OrbitSecretCreate,
    OrbitSecretCreateIn,
    OrbitSecretOut,
    OrbitSecretUpdate,
)
from dataforce_studio.schemas.organization import OrgRole
from dataforce_studio.schemas.permissions import Action, Resource

handler = OrbitSecretHandler()


@patch(
    "dataforce_studio.handlers.orbit_secrets.OrbitSecretRepository.create_orbit_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbit_secrets.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_orbit_secret(
    mock_check_orbit_action_access: AsyncMock, mock_create_orbit_secret: AsyncMock
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 1
    expected = OrbitSecretOut(
        id=1,
        orbit_id=orbit_id,
        name="test",
        value="test-value",
        created_at=datetime.datetime.now(),
        updated_at=None,
    )
    mock_check_orbit_action_access.return_value = OrgRole.OWNER, None
    mock_create_orbit_secret.return_value = expected

    secret_create_obj = OrbitSecretCreate(
        name=expected.name, value=expected.value, orbit_id=expected.orbit_id
    )

    created_secret = await handler.create_orbit_secret(
        user_id,
        organization_id,
        orbit_id,
        OrbitSecretCreateIn(name=expected.name, value=expected.value),
    )

    assert created_secret == expected
    mock_create_orbit_secret.assert_awaited_once_with(secret_create_obj)
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.ORBIT_SECRET, Action.CREATE
    )


@patch(
    "dataforce_studio.handlers.orbit_secrets.OrbitSecretRepository.get_orbit_secrets",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbit_secrets.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_orbit_secrets(
    mock_check_orbit_action_access: AsyncMock, mock_get_orbit_secrets: AsyncMock
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 1
    expected = [
        OrbitSecretOut(
            id=1,
            orbit_id=orbit_id,
            name="test",
            value="",
            created_at=datetime.datetime.now(),
            updated_at=None,
        )
    ]
    mock_check_orbit_action_access.return_value = OrgRole.OWNER, None
    mock_get_orbit_secrets.return_value = expected

    secrets = await handler.get_orbit_secrets(user_id, organization_id, orbit_id)

    assert secrets == expected
    mock_get_orbit_secrets.assert_awaited_once_with(orbit_id)
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.ORBIT_SECRET, Action.LIST
    )


@patch(
    "dataforce_studio.handlers.orbit_secrets.OrbitSecretRepository.get_orbit_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbit_secrets.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_orbit_secret(
    mock_check_orbit_action_access: AsyncMock, mock_get_orbit_secret: AsyncMock
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 1
    secret_id = 1
    expected = OrbitSecretOut(
        id=secret_id,
        orbit_id=orbit_id,
        name="test",
        value="test-value",
        created_at=datetime.datetime.now(),
        updated_at=None,
    )

    mock_check_orbit_action_access.return_value = OrgRole.OWNER, None
    mock_get_orbit_secret.return_value = expected

    secret = await handler.get_orbit_secret(
        user_id, organization_id, orbit_id, secret_id
    )

    assert secret == expected
    mock_get_orbit_secret.assert_awaited_once_with(secret_id)
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.ORBIT_SECRET, Action.READ
    )


@patch(
    "dataforce_studio.handlers.orbit_secrets.OrbitSecretRepository.get_orbit_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbit_secrets.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_orbit_secret_not_found(
    mock_check_orbit_action_access: AsyncMock, mock_get_orbit_secret: AsyncMock
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 1
    secret_id = 1

    mock_check_orbit_action_access.return_value = OrgRole.OWNER, None
    mock_get_orbit_secret.return_value = None

    with pytest.raises(NotFoundError, match="Orbit secret not found") as error:
        await handler.get_orbit_secret(user_id, organization_id, orbit_id, secret_id)

    assert error.value.status_code == 404


@patch(
    "dataforce_studio.handlers.orbit_secrets.OrbitSecretRepository.update_orbit_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbit_secrets.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit_secret(
    mock_check_orbit_action_access: AsyncMock, mock_update_orbit_secret: AsyncMock
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 1
    secret_id = 1

    secret_update = OrbitSecretUpdate(name="updated-name", value="updated-value")
    expected = OrbitSecretOut(
        id=secret_id,
        orbit_id=orbit_id,
        name="updated-name",
        value="updated-value",
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )

    mock_check_orbit_action_access.return_value = OrgRole.OWNER, None
    mock_update_orbit_secret.return_value = expected

    result = await handler.update_orbit_secret(
        user_id, organization_id, orbit_id, secret_id, secret_update
    )

    assert result == expected
    mock_update_orbit_secret.assert_awaited_once_with(secret_id, secret_update)
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.ORBIT_SECRET, Action.UPDATE
    )


@patch(
    "dataforce_studio.handlers.orbit_secrets.OrbitSecretRepository.update_orbit_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbit_secrets.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit_secret_not_found(
    mock_check_orbit_action_access: AsyncMock, mock_update_orbit_secret: AsyncMock
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 1
    secret_id = 1

    secret_update = OrbitSecretUpdate(name="updated-name", value="updated-value")

    mock_check_orbit_action_access.return_value = OrgRole.OWNER, None
    mock_update_orbit_secret.return_value = None

    with pytest.raises(NotFoundError, match="Orbit secret not found") as error:
        await handler.update_orbit_secret(
            user_id, organization_id, orbit_id, secret_id, secret_update
        )

    assert error.value.status_code == 404
    mock_update_orbit_secret.assert_awaited_once_with(secret_id, secret_update)


@patch(
    "dataforce_studio.handlers.orbit_secrets.OrbitSecretRepository.delete_orbit_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbit_secrets.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_orbit_secret(
    mock_check_orbit_action_access: AsyncMock, mock_delete_orbit_secret: AsyncMock
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 1
    secret_id = 1

    mock_check_orbit_action_access.return_value = OrgRole.OWNER, None
    mock_delete_orbit_secret.return_value = None

    await handler.delete_orbit_secret(user_id, organization_id, orbit_id, secret_id)
    mock_delete_orbit_secret.assert_awaited_once_with(secret_id)
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.ORBIT_SECRET, Action.DELETE
    )


@patch(
    "dataforce_studio.handlers.orbit_secrets.OrbitSecretRepository.get_orbit_secrets",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_worker_orbit_secrets(mock_get_orbit_secrets: AsyncMock) -> None:
    orbit_id = 1

    expected = [
        OrbitSecret(
            id=1,
            orbit_id=orbit_id,
            name="secret1",
            value="value1",
            created_at=datetime.datetime.now(),
            updated_at=None,
        )
    ]

    mock_get_orbit_secrets.return_value = expected

    result = await handler.get_worker_orbit_secrets(orbit_id)

    assert result == expected
    mock_get_orbit_secrets.assert_awaited_once_with(orbit_id)


@patch(
    "dataforce_studio.handlers.orbit_secrets.OrbitSecretRepository.get_orbit_secret",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_worker_orbit_secret(mock_get_orbit_secret: AsyncMock) -> None:
    orbit_id = 1
    secret_id = 1

    expected_secret = OrbitSecret(
        id=secret_id,
        orbit_id=orbit_id,
        name="test-secret",
        value="secret-value",
        created_at=datetime.datetime.now(),
        updated_at=None,
    )

    mock_get_orbit_secret.return_value = expected_secret

    result = await handler.get_worker_orbit_secret(orbit_id, secret_id)

    assert result == expected_secret
    mock_get_orbit_secret.assert_awaited_once_with(secret_id)


@patch(
    "dataforce_studio.handlers.orbit_secrets.OrbitSecretRepository.get_orbit_secret",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_worker_orbit_secret_not_found(
    mock_get_orbit_secret: AsyncMock,
) -> None:
    orbit_id = 1
    secret_id = 1

    mock_get_orbit_secret.return_value = None

    with pytest.raises(NotFoundError, match="Orbit secret not found") as error:
        await handler.get_worker_orbit_secret(orbit_id, secret_id)

    assert error.value.status_code == 404
    mock_get_orbit_secret.assert_awaited_once_with(secret_id)
