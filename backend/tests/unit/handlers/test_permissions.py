from collections.abc import Awaitable, Callable
from unittest.mock import Mock
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

from tests.support.ids import (
    ORBIT_ID,
    ORGANIZATION_ID,
    OTHER_ORBIT_ID,
    OTHER_ORGANIZATION_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks, mock_collaborators

ORBIT_NOT_FOUND = (404, "Orbit not found")


@pytest.fixture
def mocks() -> CollaboratorMocks[PermissionsHandler]:
    return mock_collaborators(PermissionsHandler())


def _scoped_orbit_lookup(
    orbit_id: UUID, organization_id: UUID
) -> Callable[[UUID, UUID], Awaitable[Mock | None]]:
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


class TestPermissionsHandler:
    def test_get_orbit_permissions_by_role_grants_orbit_delete_when_orbit_admin(
        self, mocks: CollaboratorMocks[PermissionsHandler]
    ) -> None:
        permissions = mocks.handler.get_orbit_permissions_by_role(
            OrgRole.ADMIN, OrbitRole.ADMIN
        )

        assert Action.DELETE.value in permissions[Resource.ORBIT.value]

    def test_get_orbit_permissions_by_role_denies_orbit_delete_when_only_org_admin(
        self, mocks: CollaboratorMocks[PermissionsHandler]
    ) -> None:
        permissions = mocks.handler.get_orbit_permissions_by_role(OrgRole.ADMIN)

        assert Action.DELETE.value not in permissions[Resource.ORBIT.value]

    async def test_check_permissions_raises_forbidden_when_not_org_member(
        self, mocks: CollaboratorMocks[PermissionsHandler]
    ) -> None:
        mocks.user_repository.get_organization_member_role.side_effect = (
            InsufficientPermissionsError
        )

        with pytest.raises(InsufficientPermissionsError) as error:
            await mocks.handler.check_permissions(
                ORGANIZATION_ID, USER_ID, Resource.ORGANIZATION, Action.DELETE
            )

        assert error.value.status_code == 403
        mocks.user_repository.get_organization_member_role.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID
        )

    async def test_check_permissions_raises_forbidden_when_org_role_lacks_action(
        self, mocks: CollaboratorMocks[PermissionsHandler]
    ) -> None:
        mocks.user_repository.get_organization_member_role.return_value = "member"

        with pytest.raises(InsufficientPermissionsError):
            await mocks.handler.check_permissions(
                ORGANIZATION_ID, USER_ID, Resource.ORGANIZATION, Action.DELETE
            )

        mocks.user_repository.get_organization_member_role.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID
        )

    async def test_check_permissions_passes_when_org_role_allows_action(
        self, mocks: CollaboratorMocks[PermissionsHandler]
    ) -> None:
        mocks.user_repository.get_organization_member_role.return_value = (
            OrgRole.OWNER.value
        )

        await mocks.handler.check_permissions(
            ORGANIZATION_ID, USER_ID, Resource.ORGANIZATION, Action.DELETE
        )

        mocks.user_repository.get_organization_member_role.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID
        )

    async def test_check_permissions_raises_forbidden_when_not_orbit_member(
        self, mocks: CollaboratorMocks[PermissionsHandler]
    ) -> None:
        mocks.user_repository.get_organization_member_role.return_value = (
            OrgRole.MEMBER.value
        )
        mocks.orbits_repository.get_orbit_simple.side_effect = _scoped_orbit_lookup(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.orbits_repository.get_orbit_member_role.side_effect = (
            InsufficientPermissionsError
        )

        with pytest.raises(InsufficientPermissionsError) as error:
            await mocks.handler.check_permissions(
                ORGANIZATION_ID, USER_ID, Resource.SATELLITE, Action.LIST, ORBIT_ID
            )

        assert error.value.status_code == 403
        mocks.orbits_repository.get_orbit_member_role.assert_awaited_once_with(
            ORBIT_ID, USER_ID
        )

    async def test_check_permissions_passes_when_orbit_role_allows_action(
        self, mocks: CollaboratorMocks[PermissionsHandler]
    ) -> None:
        mocks.user_repository.get_organization_member_role.return_value = (
            OrgRole.MEMBER.value
        )
        mocks.orbits_repository.get_orbit_simple.side_effect = _scoped_orbit_lookup(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.orbits_repository.get_orbit_member_role.return_value = (
            OrbitRole.MEMBER.value
        )

        await mocks.handler.check_permissions(
            ORGANIZATION_ID, USER_ID, Resource.SATELLITE, Action.LIST, ORBIT_ID
        )

        mocks.orbits_repository.get_orbit_member_role.assert_awaited_once_with(
            ORBIT_ID, USER_ID
        )

    async def test_check_permissions_skips_orbit_role_when_org_admin(
        self, mocks: CollaboratorMocks[PermissionsHandler]
    ) -> None:
        mocks.user_repository.get_organization_member_role.return_value = (
            OrgRole.ADMIN.value
        )
        mocks.orbits_repository.get_orbit_simple.side_effect = _scoped_orbit_lookup(
            ORBIT_ID, ORGANIZATION_ID
        )

        await mocks.handler.check_permissions(
            ORGANIZATION_ID, USER_ID, Resource.SATELLITE, Action.LIST, ORBIT_ID
        )

        mocks.user_repository.get_organization_member_role.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID
        )
        mocks.orbits_repository.get_orbit_member_role.assert_not_awaited()

    async def test_check_permissions_checks_orbit_role_when_org_member(
        self, mocks: CollaboratorMocks[PermissionsHandler]
    ) -> None:
        mocks.user_repository.get_organization_member_role.return_value = (
            OrbitRole.MEMBER.value
        )
        mocks.orbits_repository.get_orbit_simple.side_effect = _scoped_orbit_lookup(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.orbits_repository.get_orbit_member_role.return_value = (
            OrbitRole.MEMBER.value
        )

        await mocks.handler.check_permissions(
            ORGANIZATION_ID, USER_ID, Resource.SATELLITE, Action.LIST, ORBIT_ID
        )

        mocks.user_repository.get_organization_member_role.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID
        )
        mocks.orbits_repository.get_orbit_member_role.assert_awaited_once_with(
            ORBIT_ID, USER_ID
        )

    async def test_check_permissions_raises_not_found_when_orbit_in_other_organization(
        self, mocks: CollaboratorMocks[PermissionsHandler]
    ) -> None:
        mocks.user_repository.get_organization_member_role.return_value = (
            OrgRole.OWNER.value
        )
        mocks.orbits_repository.get_orbit_simple.side_effect = _scoped_orbit_lookup(
            OTHER_ORBIT_ID, OTHER_ORGANIZATION_ID
        )

        with pytest.raises(NotFoundError) as error:
            await mocks.handler.check_permissions(
                ORGANIZATION_ID,
                USER_ID,
                Resource.ORBIT_SECRET,
                Action.READ,
                OTHER_ORBIT_ID,
            )

        assert (error.value.status_code, error.value.message) == ORBIT_NOT_FOUND
        mocks.orbits_repository.get_orbit_simple.assert_awaited_once_with(
            OTHER_ORBIT_ID, ORGANIZATION_ID
        )
        mocks.orbits_repository.get_orbit_member_role.assert_not_awaited()

    async def test_check_permissions_raises_same_not_found_when_orbit_missing(
        self, mocks: CollaboratorMocks[PermissionsHandler]
    ) -> None:
        mocks.user_repository.get_organization_member_role.return_value = (
            OrgRole.OWNER.value
        )
        mocks.orbits_repository.get_orbit_simple.side_effect = _scoped_orbit_lookup(
            ORBIT_ID, ORGANIZATION_ID
        )

        with pytest.raises(NotFoundError) as error:
            await mocks.handler.check_permissions(
                ORGANIZATION_ID,
                USER_ID,
                Resource.ORBIT_SECRET,
                Action.READ,
                OTHER_ORBIT_ID,
            )

        assert (error.value.status_code, error.value.message) == ORBIT_NOT_FOUND

    async def test_check_permissions_hides_orbit_existence_when_not_org_member(
        self, mocks: CollaboratorMocks[PermissionsHandler]
    ) -> None:
        mocks.user_repository.get_organization_member_role.return_value = None
        mocks.orbits_repository.get_orbit_simple.side_effect = _scoped_orbit_lookup(
            OTHER_ORBIT_ID, OTHER_ORGANIZATION_ID
        )

        with pytest.raises(InsufficientPermissionsError) as error:
            await mocks.handler.check_permissions(
                OTHER_ORGANIZATION_ID,
                USER_ID,
                Resource.ORBIT_SECRET,
                Action.READ,
                OTHER_ORBIT_ID,
            )

        assert error.value.status_code == 403
        mocks.orbits_repository.get_orbit_simple.assert_not_awaited()

    async def test_check_permissions_raises_forbidden_when_no_orbit_role(
        self, mocks: CollaboratorMocks[PermissionsHandler]
    ) -> None:
        mocks.user_repository.get_organization_member_role.return_value = (
            OrgRole.MEMBER.value
        )
        mocks.orbits_repository.get_orbit_simple.side_effect = _scoped_orbit_lookup(
            OTHER_ORBIT_ID, OTHER_ORGANIZATION_ID
        )
        mocks.orbits_repository.get_orbit_member_role.return_value = None

        with pytest.raises(InsufficientPermissionsError) as error:
            await mocks.handler.check_permissions(
                OTHER_ORGANIZATION_ID,
                USER_ID,
                Resource.ORBIT_SECRET,
                Action.READ,
                OTHER_ORBIT_ID,
            )

        assert error.value.status_code == 403
        mocks.orbits_repository.get_orbit_member_role.assert_awaited_once_with(
            OTHER_ORBIT_ID, USER_ID
        )

    async def test_check_permissions_passes_when_orbit_in_own_organization(
        self, mocks: CollaboratorMocks[PermissionsHandler]
    ) -> None:
        mocks.user_repository.get_organization_member_role.return_value = (
            OrgRole.OWNER.value
        )
        mocks.orbits_repository.get_orbit_simple.side_effect = _scoped_orbit_lookup(
            ORBIT_ID, ORGANIZATION_ID
        )

        await mocks.handler.check_permissions(
            ORGANIZATION_ID, USER_ID, Resource.ORBIT_SECRET, Action.READ, ORBIT_ID
        )

        mocks.orbits_repository.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.orbits_repository.get_orbit_member_role.assert_not_awaited()

    async def test_check_permissions_skips_orbit_lookup_when_no_orbit_given(
        self, mocks: CollaboratorMocks[PermissionsHandler]
    ) -> None:
        mocks.user_repository.get_organization_member_role.return_value = (
            OrgRole.OWNER.value
        )

        await mocks.handler.check_permissions(
            ORGANIZATION_ID, USER_ID, Resource.ORBIT, Action.CREATE
        )

        mocks.orbits_repository.get_orbit_simple.assert_not_awaited()


LIVE_SESSION_ACTIONS = {
    Action.LIST,
    Action.READ,
    Action.CREATE,
    Action.UPDATE,
    Action.DELETE,
}


@pytest.mark.parametrize("org_role", [OrgRole.OWNER, OrgRole.ADMIN])
def test_org_roles_that_work_in_orbits_have_live_sessions(
    mocks: CollaboratorMocks[PermissionsHandler], org_role: OrgRole
) -> None:
    for action in LIVE_SESSION_ACTIONS:
        assert mocks.handler.has_organization_permission(
            org_role, Resource.LIVE_SESSION, action
        )


@pytest.mark.parametrize("orbit_role", [OrbitRole.ADMIN, OrbitRole.MEMBER])
def test_every_orbit_role_has_live_sessions(
    mocks: CollaboratorMocks[PermissionsHandler], orbit_role: OrbitRole
) -> None:
    for action in LIVE_SESSION_ACTIONS:
        assert mocks.handler.has_orbit_permission(
            orbit_role, Resource.LIVE_SESSION, action
        )


def test_org_member_role_alone_has_no_live_sessions(
    mocks: CollaboratorMocks[PermissionsHandler],
) -> None:
    assert not mocks.handler.has_organization_permission(
        OrgRole.MEMBER, Resource.LIVE_SESSION, Action.CREATE
    )


@pytest.mark.parametrize(
    ("org_role", "orbit_role"),
    [
        (OrgRole.OWNER, None),
        (OrgRole.ADMIN, None),
        (None, OrbitRole.ADMIN),
        (OrgRole.MEMBER, OrbitRole.MEMBER),
    ],
)
def test_orbit_permissions_list_live_sessions(
    mocks: CollaboratorMocks[PermissionsHandler],
    org_role: OrgRole | None,
    orbit_role: OrbitRole | None,
) -> None:
    permissions = mocks.handler.get_orbit_permissions_by_role(org_role, orbit_role)

    assert set(permissions[Resource.LIVE_SESSION.value]) == {
        action.value for action in LIVE_SESSION_ACTIONS
    }
