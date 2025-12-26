import datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from luml.handlers.orbit_secrets import OrbitSecretHandler
from luml.infra.exceptions import (
    ApplicationError,
    DatabaseConstraintError,
    NotFoundError,
)
from luml.schemas.orbit_secret import (
    OrbitSecret,
    OrbitSecretCreate,
    OrbitSecretCreateIn,
    OrbitSecretOut,
    OrbitSecretUpdate,
)
from luml.schemas.organization import OrgRole
from luml.schemas.permissions import Action, Resource

handler = OrbitSecretHandler()


@patch(
    "luml.handlers.orbit_secrets.OrbitSecretRepository.create_orbit_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbit_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_orbit_secret(
    mock_check_permissions: AsyncMock, mock_create_orbit_secret: AsyncMock
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    orbit_secret = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    expected = OrbitSecretOut(
        id=orbit_secret,
        orbit_id=orbit_id,
        name="test",
        value="test-value",
        created_at=datetime.datetime.now(),
        updated_at=None,
    )
    mock_check_permissions.return_value = OrgRole.OWNER, None
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
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ORBIT_SECRET, Action.CREATE, orbit_id
    )


@patch(
    "luml.handlers.orbit_secrets.OrbitSecretRepository.get_orbit_secrets",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbit_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_orbit_secrets(
    mock_check_permissions: AsyncMock, mock_get_orbit_secrets: AsyncMock
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    orbit_secret = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    expected = [
        OrbitSecretOut(
            id=orbit_secret,
            orbit_id=orbit_id,
            name="test",
            value="",
            created_at=datetime.datetime.now(),
            updated_at=None,
        )
    ]
    mock_check_permissions.return_value = OrgRole.OWNER, None
    mock_get_orbit_secrets.return_value = expected

    secrets = await handler.get_orbit_secrets(user_id, organization_id, orbit_id)

    assert secrets == expected
    mock_get_orbit_secrets.assert_awaited_once_with(orbit_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ORBIT_SECRET, Action.LIST, orbit_id
    )


@patch(
    "luml.handlers.orbit_secrets.OrbitSecretRepository.get_orbit_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbit_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_orbit_secret(
    mock_check_permissions: AsyncMock, mock_get_orbit_secret: AsyncMock
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    secret_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    expected = OrbitSecretOut(
        id=secret_id,
        orbit_id=orbit_id,
        name="test",
        value="test-value",
        created_at=datetime.datetime.now(),
        updated_at=None,
    )

    mock_check_permissions.return_value = OrgRole.OWNER, None
    mock_get_orbit_secret.return_value = expected

    secret = await handler.get_orbit_secret(
        user_id, organization_id, orbit_id, secret_id
    )

    assert secret == expected
    mock_get_orbit_secret.assert_awaited_once_with(secret_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ORBIT_SECRET, Action.READ, orbit_id
    )


@patch(
    "luml.handlers.orbit_secrets.OrbitSecretRepository.get_orbit_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbit_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_orbit_secret_not_found(
    mock_check_permissions: AsyncMock, mock_get_orbit_secret: AsyncMock
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    secret_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    mock_check_permissions.return_value = OrgRole.OWNER, None
    mock_get_orbit_secret.return_value = None

    with pytest.raises(NotFoundError, match="Orbit secret not found") as error:
        await handler.get_orbit_secret(user_id, organization_id, orbit_id, secret_id)

    assert error.value.status_code == 404


@patch(
    "luml.handlers.orbit_secrets.OrbitSecretRepository.update_orbit_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbit_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit_secret(
    mock_check_permissions: AsyncMock, mock_update_orbit_secret: AsyncMock
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    secret_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    secret_update = OrbitSecretUpdate(name="updated-name", value="updated-value")
    expected = OrbitSecretOut(
        id=secret_id,
        orbit_id=orbit_id,
        name="updated-name",
        value="updated-value",
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )

    mock_check_permissions.return_value = OrgRole.OWNER, None
    mock_update_orbit_secret.return_value = expected

    result = await handler.update_orbit_secret(
        user_id, organization_id, orbit_id, secret_id, secret_update
    )

    assert result == expected
    mock_update_orbit_secret.assert_awaited_once_with(secret_id, secret_update)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ORBIT_SECRET, Action.UPDATE, orbit_id
    )


@patch(
    "luml.handlers.orbit_secrets.OrbitSecretRepository.update_orbit_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbit_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit_secret_not_found(
    mock_check_permissions: AsyncMock, mock_update_orbit_secret: AsyncMock
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    secret_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    secret_update = OrbitSecretUpdate(name="updated-name", value="updated-value")

    mock_check_permissions.return_value = OrgRole.OWNER, None
    mock_update_orbit_secret.return_value = None

    with pytest.raises(NotFoundError, match="Orbit secret not found") as error:
        await handler.update_orbit_secret(
            user_id, organization_id, orbit_id, secret_id, secret_update
        )

    assert error.value.status_code == 404
    mock_update_orbit_secret.assert_awaited_once_with(secret_id, secret_update)


@patch(
    "luml.handlers.orbit_secrets.OrbitSecretRepository.delete_orbit_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbit_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_orbit_secret(
    mock_check_permissions: AsyncMock, mock_delete_orbit_secret: AsyncMock
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    secret_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    mock_check_permissions.return_value = OrgRole.OWNER, None
    mock_delete_orbit_secret.return_value = None

    await handler.delete_orbit_secret(user_id, organization_id, orbit_id, secret_id)
    mock_delete_orbit_secret.assert_awaited_once_with(secret_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ORBIT_SECRET, Action.DELETE, orbit_id
    )


@patch(
    "luml.handlers.orbit_secrets.OrbitSecretRepository.get_orbit_secrets",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_worker_orbit_secrets(mock_get_orbit_secrets: AsyncMock) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    secret_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    expected = [
        OrbitSecret(
            id=secret_id,
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
    "luml.handlers.orbit_secrets.OrbitSecretRepository.get_orbit_secret",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_worker_orbit_secret(mock_get_orbit_secret: AsyncMock) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    secret_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

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
    "luml.handlers.orbit_secrets.OrbitSecretRepository.get_orbit_secret",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_worker_orbit_secret_not_found(
    mock_get_orbit_secret: AsyncMock,
) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    secret_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    mock_get_orbit_secret.return_value = None

    with pytest.raises(NotFoundError, match="Orbit secret not found") as error:
        await handler.get_worker_orbit_secret(orbit_id, secret_id)

    assert error.value.status_code == 404
    mock_get_orbit_secret.assert_awaited_once_with(secret_id)


@patch(
    "luml.handlers.orbit_secrets.OrbitSecretRepository.create_orbit_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbit_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_orbit_secret_duplicate_name(
    mock_check_permissions: AsyncMock, mock_create_orbit_secret: AsyncMock
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    secret_name = "duplicate-name"

    mock_check_permissions.return_value = OrgRole.OWNER, None
    mock_create_orbit_secret.side_effect = DatabaseConstraintError(
        "Secret with this name already exists"
    )

    with pytest.raises(
        ApplicationError, match=f"Secret with name {secret_name} already exist in orbit"
    ) as error:
        await handler.create_orbit_secret(
            user_id,
            organization_id,
            orbit_id,
            OrbitSecretCreateIn(name=secret_name, value="test-value"),
        )

    assert error.value.status_code == 400
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ORBIT_SECRET, Action.CREATE, orbit_id
    )
