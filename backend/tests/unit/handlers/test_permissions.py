from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from dataforce_studio.handlers.permissions import PermissionsHandler
from dataforce_studio.infra.exceptions import (
    InsufficientPermissionsError,
)
from dataforce_studio.schemas.orbit import OrbitRole
from dataforce_studio.schemas.organization import OrgRole
from dataforce_studio.schemas.permissions import Action, Resource

handler = PermissionsHandler()


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_permission_user_not_org_member(
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")

    mock_get_organization_member_role.side_effect = InsufficientPermissionsError

    with pytest.raises(InsufficientPermissionsError) as error:
        await handler.check_permissions(
            organization_id, user_id, Resource.ORGANIZATION, Action.DELETE
        )

    assert error.value.status_code == 403
    mock_get_organization_member_role.assert_awaited_once_with(organization_id, user_id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_organization_permission_insufficient_permissions(
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")

    mock_get_organization_member_role.return_value = "member"

    with pytest.raises(InsufficientPermissionsError):
        await handler.check_permissions(
            organization_id, user_id, Resource.ORGANIZATION, Action.DELETE
        )

    mock_get_organization_member_role.assert_awaited_once_with(organization_id, user_id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_organization_permission_success(
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")

    mock_get_organization_member_role.return_value = OrgRole.OWNER.value

    await handler.check_permissions(
        organization_id, user_id, Resource.ORGANIZATION, Action.DELETE
    )

    mock_get_organization_member_role.assert_awaited_once_with(organization_id, user_id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_orbit_permission_user_not_member(
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    organization_id = UUID("0199c337-09f3-753e-9def-b27745e69b76")

    mock_get_organization_member_role.return_value = OrgRole.MEMBER.value
    mock_get_orbit_member_role.side_effect = InsufficientPermissionsError

    with pytest.raises(InsufficientPermissionsError) as error:
        await handler.check_permissions(
            organization_id, user_id, Resource.SATELLITE, Action.LIST, orbit_id
        )

    assert error.value.status_code == 403
    mock_get_orbit_member_role.assert_awaited_once_with(orbit_id, user_id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_orbit_permission_success(
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    organization_id = UUID("0199c337-09f3-753e-9def-b27745e69b76")

    mock_get_organization_member_role.return_value = OrgRole.MEMBER.value
    mock_get_orbit_member_role.return_value = OrbitRole.MEMBER.value

    await handler.check_permissions(
        organization_id, user_id, Resource.SATELLITE, Action.LIST, orbit_id
    )

    mock_get_orbit_member_role.assert_awaited_once_with(orbit_id, user_id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_orbit_action_access_org_admin(
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_get_organization_member_role.return_value = OrgRole.ADMIN.value

    await handler.check_permissions(
        organization_id, user_id, Resource.SATELLITE, Action.LIST, orbit_id
    )

    mock_get_organization_member_role.assert_awaited_once_with(organization_id, user_id)
    mock_get_orbit_member_role.assert_not_awaited()


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_orbit_action_access_orbit_member(
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_get_organization_member_role.return_value = OrbitRole.MEMBER.value
    mock_get_orbit_member_role.return_value = OrbitRole.MEMBER.value

    await handler.check_permissions(
        organization_id, user_id, Resource.SATELLITE, Action.LIST, orbit_id
    )

    mock_get_organization_member_role.assert_awaited_once_with(organization_id, user_id)
    mock_get_orbit_member_role.assert_awaited_once_with(orbit_id, user_id)
