from uuid import uuid7

import pytest
from luml.handlers.organizations import OrganizationHandler
from luml.infra.exceptions import (
    InsufficientPermissionsError,
    OrganizationMemberNotFoundError,
)
from luml.schemas.organization import (
    OrganizationMember,
    OrgRole,
    UpdateOrganizationMember,
)
from luml.schemas.permissions import Action, Resource

from tests.support.ids import USER_ID
from tests.support.mocks import CollaboratorMocks


class TestOrganizationMembers:
    async def test_get_organization_members_data_returns_members(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        organization_member: OrganizationMember,
    ) -> None:
        organization_id = organization_member.organization_id

        expected = [organization_member]
        mocks.user_repository.get_organization_members.return_value = expected

        actual = await mocks.handler.get_organization_members_data(
            USER_ID, organization_id
        )

        assert actual == expected
        mocks.user_repository.get_organization_members.assert_awaited_once()
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            organization_id, USER_ID, Resource.ORGANIZATION_USER, Action.LIST
        )

    async def test_update_organization_member_by_id_returns_updated_member(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        organization_member: OrganizationMember,
    ) -> None:
        member_to_update = organization_member.model_copy()
        member_to_update.role = OrgRole.MEMBER

        mocks.user_repository.update_organization_member.return_value = (
            organization_member
        )
        mocks.user_repository.get_organization_member_by_id.return_value = (
            member_to_update
        )
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.OWNER

        update_member = UpdateOrganizationMember(role=OrgRole.ADMIN)
        actual = await mocks.handler.update_organization_member_by_id(
            USER_ID,
            member_to_update.organization_id,
            member_to_update.id,
            update_member,
        )

        assert actual == organization_member
        mocks.user_repository.get_organization_member_by_id.assert_awaited_once_with(
            member_to_update.organization_id, member_to_update.id
        )
        mocks.user_repository.update_organization_member.assert_awaited_once_with(
            member_to_update.organization_id, member_to_update.id, update_member
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            member_to_update.organization_id,
            USER_ID,
            Resource.ORGANIZATION_USER,
            Action.CREATE,
        )

    async def test_delete_organization_member_by_id_deletes_member(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        organization_member: OrganizationMember,
    ) -> None:
        member_to_delete = organization_member.model_copy()
        member_to_delete.role = OrgRole.MEMBER

        organization_id = member_to_delete.organization_id

        mocks.user_repository.delete_organization_member.return_value = None
        mocks.user_repository.get_organization_member_by_id.return_value = (
            member_to_delete
        )
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.ADMIN

        await mocks.handler.delete_organization_member_by_id(
            USER_ID, organization_id, member_to_delete.id
        )
        mocks.user_repository.delete_organization_member.assert_awaited_once_with(
            organization_id, member_to_delete.id
        )
        mocks.user_repository.get_organization_member_by_id.assert_awaited_once_with(
            organization_id, member_to_delete.id
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            organization_id, USER_ID, Resource.ORGANIZATION_USER, Action.DELETE
        )

    async def test_update_organization_member_by_id_raises_when_admin_assigns_admin(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        organization_member: OrganizationMember,
    ) -> None:
        member_to_update = organization_member.model_copy()
        member_to_update.role = OrgRole.MEMBER

        mocks.user_repository.get_organization_member_by_id.return_value = (
            member_to_update
        )
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.ADMIN

        with pytest.raises(
            InsufficientPermissionsError,
            match="Only Organization Owner can assign new admins.",
        ):
            await mocks.handler.update_organization_member_by_id(
                USER_ID,
                member_to_update.organization_id,
                member_to_update.id,
                UpdateOrganizationMember(role=OrgRole.ADMIN),
            )

        mocks.user_repository.update_organization_member.assert_not_awaited()
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            member_to_update.organization_id,
            USER_ID,
            Resource.ORGANIZATION_USER,
            Action.CREATE,
        )

    async def test_update_organization_member_by_id_raises_when_admin_demotes_admin(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        organization_member: OrganizationMember,
    ) -> None:
        member_to_update = organization_member.model_copy()
        member_to_update.role = OrgRole.ADMIN

        mocks.user_repository.get_organization_member_by_id.return_value = (
            member_to_update
        )
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.ADMIN

        with pytest.raises(
            InsufficientPermissionsError,
            match="Only Organization Owner can change admin roles.",
        ):
            await mocks.handler.update_organization_member_by_id(
                USER_ID,
                member_to_update.organization_id,
                member_to_update.id,
                UpdateOrganizationMember(role=OrgRole.MEMBER),
            )

        mocks.user_repository.update_organization_member.assert_not_awaited()
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            member_to_update.organization_id,
            USER_ID,
            Resource.ORGANIZATION_USER,
            Action.CREATE,
        )

    async def test_update_organization_member_by_id_raises_when_target_is_owner(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        organization_member: OrganizationMember,
    ) -> None:
        mocks.user_repository.get_organization_member_by_id.return_value = (
            organization_member
        )
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.ADMIN

        with pytest.raises(
            InsufficientPermissionsError,
            match="Organization Owner role can not be changed.",
        ):
            await mocks.handler.update_organization_member_by_id(
                USER_ID,
                organization_member.organization_id,
                organization_member.id,
                UpdateOrganizationMember(role=OrgRole.MEMBER),
            )

        mocks.user_repository.update_organization_member.assert_not_awaited()
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            organization_member.organization_id,
            USER_ID,
            Resource.ORGANIZATION_USER,
            Action.CREATE,
        )

    async def test_delete_organization_member_by_id_raises_when_admin_removes_admin(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        organization_member: OrganizationMember,
    ) -> None:
        member_to_delete = organization_member.model_copy()
        member_to_delete.role = OrgRole.ADMIN

        mocks.user_repository.get_organization_member_by_id.return_value = (
            member_to_delete
        )
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.ADMIN

        with pytest.raises(
            InsufficientPermissionsError,
            match="Only Organization Owner can remove admins.",
        ):
            await mocks.handler.delete_organization_member_by_id(
                USER_ID, member_to_delete.organization_id, member_to_delete.id
            )

        mocks.user_repository.delete_organization_member.assert_not_awaited()

    async def test_delete_organization_member_by_id_deletes_admin_when_caller_is_owner(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        organization_member: OrganizationMember,
    ) -> None:
        member_to_delete = organization_member.model_copy()
        member_to_delete.role = OrgRole.ADMIN

        mocks.user_repository.delete_organization_member.return_value = None
        mocks.user_repository.get_organization_member_by_id.return_value = (
            member_to_delete
        )
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.OWNER

        await mocks.handler.delete_organization_member_by_id(
            USER_ID, member_to_delete.organization_id, member_to_delete.id
        )

        mocks.user_repository.delete_organization_member.assert_awaited_once_with(
            member_to_delete.organization_id, member_to_delete.id
        )

    async def test_transfer_organization_ownership_returns_new_owner(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        organization_member: OrganizationMember,
    ) -> None:
        successor = organization_member.model_copy(update={"role": OrgRole.MEMBER})
        new_owner = organization_member.model_copy(update={"role": OrgRole.OWNER})
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.OWNER
        mocks.user_repository.get_organization_member_by_id.return_value = successor
        mocks.user_repository.transfer_organization_ownership.return_value = new_owner

        actual = await mocks.handler.transfer_organization_ownership(
            USER_ID, successor.organization_id, successor.id
        )

        assert actual == new_owner
        mocks.user_repository.transfer_organization_ownership.assert_awaited_once_with(
            successor.organization_id, USER_ID, successor.id
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            successor.organization_id,
            USER_ID,
            Resource.ORGANIZATION_USER,
            Action.UPDATE,
        )

    @pytest.mark.parametrize("caller_role", [OrgRole.ADMIN, OrgRole.MEMBER])
    async def test_transfer_organization_ownership_raises_when_caller_is_not_owner(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        organization_member: OrganizationMember,
        caller_role: OrgRole,
    ) -> None:
        mocks.user_repository.get_organization_member_role.return_value = caller_role

        with pytest.raises(
            InsufficientPermissionsError,
            match="Only Organization Owner can transfer ownership.",
        ):
            await mocks.handler.transfer_organization_ownership(
                USER_ID, organization_member.organization_id, organization_member.id
            )

        mocks.user_repository.transfer_organization_ownership.assert_not_awaited()

    async def test_transfer_organization_ownership_raises_when_member_missing(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
    ) -> None:
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.OWNER
        mocks.user_repository.get_organization_member_by_id.return_value = None

        with pytest.raises(OrganizationMemberNotFoundError):
            await mocks.handler.transfer_organization_ownership(
                USER_ID, uuid7(), uuid7()
            )

        mocks.user_repository.transfer_organization_ownership.assert_not_awaited()

    async def test_transfer_organization_ownership_raises_when_target_is_self(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        organization_member: OrganizationMember,
    ) -> None:
        user = organization_member.user.model_copy(update={"id": USER_ID})
        member = organization_member.model_copy(
            update={"role": OrgRole.OWNER, "user": user}
        )
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.OWNER
        mocks.user_repository.get_organization_member_by_id.return_value = member

        with pytest.raises(
            InsufficientPermissionsError,
            match="You can not transfer ownership to yourself.",
        ):
            await mocks.handler.transfer_organization_ownership(
                USER_ID, member.organization_id, member.id
            )

        mocks.user_repository.transfer_organization_ownership.assert_not_awaited()

    async def test_transfer_organization_ownership_raises_when_target_is_owner(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        organization_member: OrganizationMember,
    ) -> None:
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.OWNER
        mocks.user_repository.get_organization_member_by_id.return_value = (
            organization_member
        )

        with pytest.raises(
            InsufficientPermissionsError,
            match="Member is already an Organization Owner.",
        ):
            await mocks.handler.transfer_organization_ownership(
                USER_ID, organization_member.organization_id, organization_member.id
            )

        mocks.user_repository.transfer_organization_ownership.assert_not_awaited()

    async def test_transfer_organization_ownership_raises_when_transfer_refused(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        organization_member: OrganizationMember,
    ) -> None:
        successor = organization_member.model_copy(update={"role": OrgRole.MEMBER})
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.OWNER
        mocks.user_repository.get_organization_member_by_id.return_value = successor
        mocks.user_repository.transfer_organization_ownership.return_value = None

        with pytest.raises(InsufficientPermissionsError, match="try again"):
            await mocks.handler.transfer_organization_ownership(
                USER_ID, successor.organization_id, successor.id
            )
