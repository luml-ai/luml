from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest
from luml.handlers.permissions import PermissionsHandler
from luml.infra.exceptions import (
    InsufficientPermissionsError,
    NotFoundError,
)
from luml.schemas.orbit import OrbitRole
from luml.schemas.organization import OrgRole
from luml.schemas.permissions import Action, Resource

handler = PermissionsHandler()

USER_A = UUID("0199c337-0a00-7d8f-b0c4-b68349bbe24b")
ORG_A = UUID("0199c337-0a01-7af1-af5e-83fd7a5b51a0")
ORBIT_A = UUID("0199c337-0a02-753e-9def-b27745e69be6")
ORG_V = UUID("0199c337-0a03-7af1-af5e-83fd7a5b51a1")
ORBIT_V = UUID("0199c337-0a04-753e-9def-b27745e69be7")

ORBIT_NOT_FOUND = (404, "Orbit not found")


def test_get_orbit_permissions_include_orbit_role_for_org_admin() -> None:
    permissions = handler.get_orbit_permissions_by_role(OrgRole.ADMIN, OrbitRole.ADMIN)

    assert Action.DELETE.value in permissions[Resource.ORBIT.value]


def test_get_orbit_permissions_do_not_grant_org_admin_orbit_delete() -> None:
    permissions = handler.get_orbit_permissions_by_role(OrgRole.ADMIN)

    assert Action.DELETE.value not in permissions[Resource.ORBIT.value]


def scoped_orbit_lookup(
    orbit_id: UUID, organization_id: UUID
) -> Callable[[UUID, UUID], Awaitable[Mock | None]]:
    """Fake the repository predicate: an orbit is only visible in its own org."""

    async def _get_orbit_simple(
        requested_orbit_id: UUID, requested_organization_id: UUID
    ) -> Mock | None:
        if (requested_orbit_id, requested_organization_id) == (
            orbit_id,
            organization_id,
        ):
            return Mock(id=orbit_id, organization_id=organization_id)
        return None

    return _get_orbit_simple


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
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
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
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
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
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
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_orbit_permission_user_not_member(
    mock_get_orbit_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    organization_id = UUID("0199c337-09f3-753e-9def-b27745e69b76")

    mock_get_organization_member_role.return_value = OrgRole.MEMBER.value
    mock_get_orbit_simple.side_effect = scoped_orbit_lookup(orbit_id, organization_id)
    mock_get_orbit_member_role.side_effect = InsufficientPermissionsError

    with pytest.raises(InsufficientPermissionsError) as error:
        await handler.check_permissions(
            organization_id, user_id, Resource.SATELLITE, Action.LIST, orbit_id
        )

    assert error.value.status_code == 403
    mock_get_orbit_member_role.assert_awaited_once_with(orbit_id, user_id)


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_orbit_permission_success(
    mock_get_orbit_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    organization_id = UUID("0199c337-09f3-753e-9def-b27745e69b76")

    mock_get_organization_member_role.return_value = OrgRole.MEMBER.value
    mock_get_orbit_simple.side_effect = scoped_orbit_lookup(orbit_id, organization_id)
    mock_get_orbit_member_role.return_value = OrbitRole.MEMBER.value

    await handler.check_permissions(
        organization_id, user_id, Resource.SATELLITE, Action.LIST, orbit_id
    )

    mock_get_orbit_member_role.assert_awaited_once_with(orbit_id, user_id)


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_orbit_action_access_org_admin(
    mock_get_orbit_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_get_organization_member_role.return_value = OrgRole.ADMIN.value
    mock_get_orbit_simple.side_effect = scoped_orbit_lookup(orbit_id, organization_id)

    await handler.check_permissions(
        organization_id, user_id, Resource.SATELLITE, Action.LIST, orbit_id
    )

    mock_get_organization_member_role.assert_awaited_once_with(organization_id, user_id)
    mock_get_orbit_member_role.assert_not_awaited()


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_orbit_action_access_orbit_member(
    mock_get_orbit_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_get_organization_member_role.return_value = OrbitRole.MEMBER.value
    mock_get_orbit_simple.side_effect = scoped_orbit_lookup(orbit_id, organization_id)
    mock_get_orbit_member_role.return_value = OrbitRole.MEMBER.value

    await handler.check_permissions(
        organization_id, user_id, Resource.SATELLITE, Action.LIST, orbit_id
    )

    mock_get_organization_member_role.assert_awaited_once_with(organization_id, user_id)
    mock_get_orbit_member_role.assert_awaited_once_with(orbit_id, user_id)


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_permissions_foreign_orbit_under_own_organization(
    mock_get_orbit_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    mock_get_organization_member_role.return_value = OrgRole.OWNER.value
    mock_get_orbit_simple.side_effect = scoped_orbit_lookup(ORBIT_V, ORG_V)

    with pytest.raises(NotFoundError) as error:
        await handler.check_permissions(
            ORG_A, USER_A, Resource.ORBIT_SECRET, Action.READ, ORBIT_V
        )

    assert (error.value.status_code, error.value.message) == ORBIT_NOT_FOUND
    mock_get_orbit_simple.assert_awaited_once_with(ORBIT_V, ORG_A)
    mock_get_orbit_member_role.assert_not_awaited()


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_permissions_missing_orbit_matches_foreign_orbit_failure(
    mock_get_orbit_simple: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    unknown_orbit_id = UUID("0199c337-0a05-753e-9def-b27745e69be8")

    mock_get_organization_member_role.return_value = OrgRole.OWNER.value
    mock_get_orbit_simple.side_effect = scoped_orbit_lookup(ORBIT_A, ORG_A)

    with pytest.raises(NotFoundError) as error:
        await handler.check_permissions(
            ORG_A, USER_A, Resource.ORBIT_SECRET, Action.READ, unknown_orbit_id
        )

    assert (error.value.status_code, error.value.message) == ORBIT_NOT_FOUND


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_permissions_non_member_cannot_probe_orbit_existence(
    mock_get_orbit_simple: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    mock_get_organization_member_role.return_value = None
    mock_get_orbit_simple.side_effect = scoped_orbit_lookup(ORBIT_V, ORG_V)

    with pytest.raises(InsufficientPermissionsError) as error:
        await handler.check_permissions(
            ORG_V, USER_A, Resource.ORBIT_SECRET, Action.READ, ORBIT_V
        )

    assert error.value.status_code == 403
    mock_get_orbit_simple.assert_not_awaited()


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_permissions_org_member_without_orbit_membership(
    mock_get_orbit_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    mock_get_organization_member_role.return_value = OrgRole.MEMBER.value
    mock_get_orbit_simple.side_effect = scoped_orbit_lookup(ORBIT_V, ORG_V)
    mock_get_orbit_member_role.return_value = None

    with pytest.raises(InsufficientPermissionsError) as error:
        await handler.check_permissions(
            ORG_V, USER_A, Resource.ORBIT_SECRET, Action.READ, ORBIT_V
        )

    assert error.value.status_code == 403
    mock_get_orbit_member_role.assert_awaited_once_with(ORBIT_V, USER_A)


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_permissions_own_orbit_unaffected(
    mock_get_orbit_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    mock_get_organization_member_role.return_value = OrgRole.OWNER.value
    mock_get_orbit_simple.side_effect = scoped_orbit_lookup(ORBIT_A, ORG_A)

    await handler.check_permissions(
        ORG_A, USER_A, Resource.ORBIT_SECRET, Action.READ, ORBIT_A
    )

    mock_get_orbit_simple.assert_awaited_once_with(ORBIT_A, ORG_A)
    mock_get_orbit_member_role.assert_not_awaited()


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_permissions_without_orbit_skips_orbit_lookup(
    mock_get_orbit_simple: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    mock_get_organization_member_role.return_value = OrgRole.OWNER.value

    await handler.check_permissions(ORG_A, USER_A, Resource.ORBIT, Action.CREATE)

    mock_get_orbit_simple.assert_not_awaited()
