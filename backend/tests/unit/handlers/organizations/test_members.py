from unittest.mock import Mock

import pytest
from luml.handlers.organizations import OrganizationHandler
from luml.infra.exceptions import InsufficientPermissionsError
from luml.schemas.organization import (
    OrganizationMember,
    OrganizationMemberCreate,
    OrganizationMemberCreateIn,
    OrgRole,
    UpdateOrganizationMember,
)
from luml.schemas.permissions import Action, Resource

from tests.support.ids import MEMBER_ID, USER_ID
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
        mocks.user_repository.update_organization_member.assert_awaited_once()
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
            member_to_delete.id
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            organization_id, USER_ID, Resource.ORGANIZATION_USER, Action.DELETE
        )

    async def test_add_organization_member_creates_member_in_path_organization(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        organization_member: OrganizationMember,
    ) -> None:
        user_id = organization_member.user.id
        organization_id = organization_member.organization_id

        member_create = OrganizationMemberCreateIn(
            user_id=MEMBER_ID,
            role=OrgRole.MEMBER,
        )

        mocks.user_repository.create_organization_member.return_value = (
            organization_member
        )
        mocks.user_repository.get_organization_details.return_value = Mock(
            members_limit=50, total_members=0
        )
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.OWNER

        actual = await mocks.handler.add_organization_member(
            user_id, organization_id, member_create
        )

        assert actual == organization_member
        mocks.user_repository.create_organization_member.assert_awaited_once_with(
            OrganizationMemberCreate(
                user_id=MEMBER_ID,
                organization_id=organization_id,
                role=member_create.role,
            )
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            organization_id, user_id, Resource.ORGANIZATION_USER, Action.CREATE
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
            member_to_delete.id
        )
