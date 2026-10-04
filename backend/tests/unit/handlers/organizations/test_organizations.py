from unittest.mock import Mock

import pytest
from luml.handlers.organizations import OrganizationHandler
from luml.infra.exceptions import (
    InsufficientPermissionsError,
    NotFoundError,
    OrganizationDeleteError,
    OrganizationLimitReachedError,
)
from luml.models import OrganizationOrm
from luml.schemas.organization import (
    Organization,
    OrganizationCreateIn,
    OrganizationDetails,
    OrganizationSwitcher,
    OrganizationUpdate,
    OrgRole,
)
from luml.schemas.permissions import Action, Resource
from pydantic import ValidationError

from tests.support.ids import ORGANIZATION_ID, USER_ID
from tests.support.mocks import CollaboratorMocks


class TestOrganizations:
    async def test_check_org_members_limit_raises_when_members_exceed_limit(
        self, mocks: CollaboratorMocks[OrganizationHandler]
    ) -> None:
        mocks.user_repository.get_organization_details.return_value = Mock(
            members_limit=50, total_members=200
        )

        with pytest.raises(OrganizationLimitReachedError):
            await mocks.handler._check_org_members_limit(
                organization_id=ORGANIZATION_ID
            )

        mocks.user_repository.get_organization_details.assert_awaited_once()

    async def test_get_user_organizations_returns_user_organizations(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        organization: Organization,
    ) -> None:
        expected = [
            OrganizationSwitcher(
                id=organization.id,
                name=organization.name,
                logo=organization.logo,
                created_at=organization.created_at,
                updated_at=organization.updated_at,
                role=OrgRole.MEMBER,
            )
        ]
        mocks.user_repository.get_user_organizations.return_value = expected

        actual = await mocks.handler.get_user_organizations(USER_ID)

        assert actual == expected
        mocks.user_repository.get_user_organizations.assert_awaited_once_with(USER_ID)

    async def test_get_organization_returns_organization_details(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        organization_details: OrganizationDetails,
    ) -> None:
        expected = organization_details

        mocks.user_repository.get_organization_member_role.return_value = OrgRole.OWNER
        mocks.user_repository.get_organization_details.return_value = expected

        actual = await mocks.handler.get_organization(USER_ID, ORGANIZATION_ID)

        assert actual
        mocks.user_repository.get_organization_details.assert_awaited_once_with(
            ORGANIZATION_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ORGANIZATION, Action.READ
        )

    async def test_get_organization_raises_not_found_when_organization_is_missing(
        self, mocks: CollaboratorMocks[OrganizationHandler]
    ) -> None:
        mocks.user_repository.get_organization_details.return_value = None

        with pytest.raises(
            NotFoundError,
            match="Organization not found",
        ):
            await mocks.handler.get_organization(USER_ID, ORGANIZATION_ID)

        mocks.user_repository.get_organization_details.assert_awaited_once_with(
            ORGANIZATION_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ORGANIZATION, Action.READ
        )

    async def test_create_organization_returns_created_organization(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        organization: Organization,
    ) -> None:
        org_to_create = OrganizationCreateIn(
            name=organization.name, logo=organization.logo
        )
        expected = organization

        mocks.user_repository.get_user_organizations_limit.return_value = 5
        mocks.user_repository.get_user_organizations_membership_count.return_value = 0
        mocks.user_repository.create_organization.return_value = OrganizationOrm(
            id=organization.id,
            name=organization.name,
            logo=organization.logo,
            created_at=organization.created_at,
            updated_at=organization.updated_at,
        )

        actual = await mocks.handler.create_organization(USER_ID, org_to_create)

        assert actual
        assert actual == expected
        mocks.user_repository.create_organization.assert_awaited_once_with(
            USER_ID, org_to_create
        )

    async def test_update_organization_returns_updated_details(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        organization_details: OrganizationDetails,
    ) -> None:
        expected = organization_details
        organization_id = organization_details.id

        mocks.user_repository.get_organization_details.return_value = expected
        mocks.user_repository.update_organization.return_value = expected

        update_org = OrganizationUpdate(name=expected.name, logo=expected.logo)
        actual = await mocks.handler.update_organization(
            USER_ID, expected.id, update_org
        )

        assert actual == expected
        mocks.user_repository.update_organization.assert_awaited_once()
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            organization_id,
            USER_ID,
            Resource.ORGANIZATION,
            Action.UPDATE,
        )

    async def test_update_organization_raises_not_found_when_update_matches_nothing(
        self, mocks: CollaboratorMocks[OrganizationHandler]
    ) -> None:
        organization_to_update = OrganizationUpdate(name="test", logo=None)

        mocks.user_repository.update_organization.return_value = None

        with pytest.raises(
            NotFoundError,
            match="Organization not found",
        ):
            await mocks.handler.update_organization(
                USER_ID, ORGANIZATION_ID, organization_to_update
            )

        mocks.user_repository.update_organization.assert_awaited_once_with(
            ORGANIZATION_ID, organization_to_update
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ORGANIZATION, Action.UPDATE
        )

    async def test_delete_organization_deletes_organization(
        self, mocks: CollaboratorMocks[OrganizationHandler]
    ) -> None:
        mocks.user_repository.delete_organization.return_value = True

        await mocks.handler.delete_organization(USER_ID, ORGANIZATION_ID)

        mocks.user_repository.delete_organization.assert_awaited_once_with(
            ORGANIZATION_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ORGANIZATION, Action.DELETE
        )

    async def test_delete_organization_raises_not_found_when_organization_is_missing(
        self, mocks: CollaboratorMocks[OrganizationHandler]
    ) -> None:
        mocks.user_repository.delete_organization.return_value = False

        with pytest.raises(NotFoundError, match="Organization not found"):
            await mocks.handler.delete_organization(USER_ID, ORGANIZATION_ID)

    async def test_delete_organization_propagates_error_when_organization_has_members(
        self, mocks: CollaboratorMocks[OrganizationHandler]
    ) -> None:
        mocks.user_repository.delete_organization.side_effect = OrganizationDeleteError(
            "Organization has members and cant be deleted"
        )

        with pytest.raises(OrganizationDeleteError, match="has members"):
            await mocks.handler.delete_organization(USER_ID, ORGANIZATION_ID)

    async def test_leave_from_organization_deletes_membership(
        self, mocks: CollaboratorMocks[OrganizationHandler]
    ) -> None:
        mocks.user_repository.delete_organization_member_by_user_id.return_value = None

        await mocks.handler.leave_from_organization(USER_ID, ORGANIZATION_ID)

        mocks.user_repository.delete_organization_member_by_user_id.assert_awaited_once_with(
            USER_ID, ORGANIZATION_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.ORGANIZATION,
            Action.LEAVE,
        )

    async def test_leave_from_organization_raises_when_permission_refused(
        self, mocks: CollaboratorMocks[OrganizationHandler]
    ) -> None:
        mocks.permissions_handler.check_permissions.side_effect = (
            InsufficientPermissionsError
        )

        with pytest.raises(InsufficientPermissionsError):
            await mocks.handler.leave_from_organization(USER_ID, ORGANIZATION_ID)

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ORGANIZATION, Action.LEAVE
        )
        mocks.user_repository.delete_organization_member_by_user_id.assert_not_awaited()

    def test_organization_create_in_rejects_name_longer_than_limit(self) -> None:
        long_name = "a" * 101
        with pytest.raises(ValidationError) as excinfo:
            OrganizationCreateIn(name=long_name)

        assert "String should have at most" in str(excinfo.value)

    @pytest.mark.parametrize(
        ("user_limit", "memberships", "allowed"),
        [(5, 4, True), (5, 5, False), (8, 6, True), (1, 1, False)],
    )
    async def test_create_organization_enforces_user_specific_limit(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        user_limit: int,
        memberships: int,
        allowed: bool,
        organization: Organization,
    ) -> None:
        mocks.user_repository.get_user_organizations_limit.return_value = user_limit
        mocks.user_repository.get_user_organizations_membership_count.return_value = (
            memberships
        )
        mocks.user_repository.create_organization.return_value = OrganizationOrm(
            id=organization.id,
            name=organization.name,
            created_at=organization.created_at,
        )
        org_to_create = OrganizationCreateIn(name=organization.name)

        if allowed:
            await mocks.handler.create_organization(USER_ID, org_to_create)
            mocks.user_repository.create_organization.assert_awaited_once()
        else:
            with pytest.raises(OrganizationLimitReachedError):
                await mocks.handler.create_organization(USER_ID, org_to_create)
            mocks.user_repository.create_organization.assert_not_awaited()
