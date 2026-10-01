from datetime import datetime
from unittest.mock import Mock

import pytest
from luml.handlers.organizations import OrganizationHandler
from luml.infra.exceptions import ApplicationError, InsufficientPermissionsError
from luml.models import OrganizationInviteOrm
from luml.schemas.organization import (
    CreateOrganizationInvite,
    CreateOrganizationInviteIn,
    OrganizationInvite,
    OrganizationMemberCreate,
    OrgRole,
    UserInvite,
)
from luml.schemas.permissions import Action, Resource
from luml.schemas.user import UserOut
from luml.settings import config

from tests.support.ids import INVITE_ID, ORGANIZATION_ID, USER_ID
from tests.support.mocks import CollaboratorMocks


class TestOrganizationInvites:
    @pytest.mark.parametrize(
        ("inviter_role", "invite_role"),
        [
            (OrgRole.OWNER, OrgRole.ADMIN),
            (OrgRole.ADMIN, OrgRole.MEMBER),
        ],
    )
    async def test_send_invite_creates_invite_and_sends_email(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        new_invite: CreateOrganizationInvite,
        user_out: UserOut,
        inviter_role: OrgRole,
        invite_role: OrgRole,
    ) -> None:
        invite_in = CreateOrganizationInviteIn(
            email=new_invite.email,
            role=invite_role,
        )
        created_invite = OrganizationInvite(
            id=INVITE_ID,
            email=new_invite.email,
            role=invite_role,
            organization_id=new_invite.organization_id,
            created_at=datetime.now(),
        )

        mocks.invites_repository.get_organization_invite_by_email.return_value = None
        mocks.user_repository.get_organization_member_by_email.return_value = None
        mocks.user_repository.get_public_user_by_id.return_value = user_out
        mocks.invites_repository.create_organization_invite.return_value = (
            created_invite
        )
        mocks.invites_repository.get_invite.return_value = created_invite
        mocks.user_repository.get_organization_member_role.return_value = inviter_role
        mocks.user_repository.get_organization_details.return_value = Mock(
            members_limit=50, total_members=0
        )

        result = await mocks.handler.send_invite(
            user_out.id, new_invite.organization_id, invite_in
        )

        assert result == created_invite

        mocks.email_handler.send_organization_invite_email.assert_called_once_with(
            created_invite.email,
            "",
            "",
            f"{config.APP_EMAIL_URL.rstrip('/')}/invitations",
        )
        mocks.invites_repository.create_organization_invite.assert_awaited_once_with(
            CreateOrganizationInvite(
                email=new_invite.email,
                role=invite_role,
                organization_id=new_invite.organization_id,
                invited_by=user_out.id,
            )
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            new_invite.organization_id,
            user_out.id,
            Resource.ORGANIZATION_INVITE,
            Action.CREATE,
        )

    async def test_send_invite_raises_when_admin_invites_admin(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        new_invite: CreateOrganizationInvite,
    ) -> None:
        invite_in = CreateOrganizationInviteIn(
            email=new_invite.email,
            role=OrgRole.ADMIN,
        )
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.ADMIN

        with pytest.raises(
            InsufficientPermissionsError,
            match="Only Organization Owner can invite new admins.",
        ):
            await mocks.handler.send_invite(
                new_invite.invited_by, new_invite.organization_id, invite_in
            )

        mocks.invites_repository.create_organization_invite.assert_not_awaited()
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            new_invite.organization_id,
            new_invite.invited_by,
            Resource.ORGANIZATION_INVITE,
            Action.CREATE,
        )

    async def test_send_invite_raises_when_user_invites_themselves(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        new_invite: CreateOrganizationInvite,
        user_out: UserOut,
    ) -> None:
        invite_in = CreateOrganizationInviteIn(
            email=user_out.email,
            role=new_invite.role,
        )

        mocks.user_repository.get_public_user_by_id.return_value = user_out
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.OWNER

        with pytest.raises(ApplicationError, match="You can't invite yourself"):
            await mocks.handler.send_invite(
                user_out.id, new_invite.organization_id, invite_in
            )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            new_invite.organization_id,
            user_out.id,
            Resource.ORGANIZATION_INVITE,
            Action.CREATE,
        )

    async def test_cancel_invite_deletes_invite(
        self, mocks: CollaboratorMocks[OrganizationHandler]
    ) -> None:
        mocks.invites_repository.delete_organization_invite.return_value = None

        await mocks.handler.cancel_invite(USER_ID, ORGANIZATION_ID, INVITE_ID)
        mocks.invites_repository.delete_organization_invite.assert_awaited_once_with(
            ORGANIZATION_ID, INVITE_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ORGANIZATION_INVITE, Action.DELETE
        )

    async def test_accept_invite_creates_member_and_deletes_user_invites(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        new_invite: CreateOrganizationInvite,
    ) -> None:
        stored_invite = OrganizationInviteOrm(**new_invite.model_dump())

        mocks.invites_repository.get_invite.return_value = stored_invite
        mocks.user_repository.get_user_organizations_limit.return_value = 5
        mocks.user_repository.get_user_organizations_membership_count.return_value = 0
        mocks.user_repository.get_organization_details.return_value = Mock(
            members_limit=50, total_members=0
        )

        await mocks.handler.accept_invite(
            stored_invite.id, USER_ID, stored_invite.email
        )
        mocks.invites_repository.get_invite.assert_awaited_once_with(stored_invite.id)
        mocks.user_repository.get_organization_details.assert_awaited_once_with(
            stored_invite.organization_id
        )
        mocks.user_repository.create_organization_member.assert_awaited_once_with(
            OrganizationMemberCreate(
                user_id=USER_ID,
                organization_id=stored_invite.organization_id,
                role=OrgRole(stored_invite.role),
            )
        )
        mocks.invites_repository.delete_organization_invites_for_user.assert_awaited_once_with(
            stored_invite.organization_id, stored_invite.email
        )

    async def test_reject_invite_deletes_invite(
        self, mocks: CollaboratorMocks[OrganizationHandler]
    ) -> None:
        mocks.invites_repository.delete_organization_invite.return_value = None
        email = "test@example.com"
        mocks.invites_repository.get_invite.return_value = Mock(
            email=email, organization_id=ORGANIZATION_ID
        )

        await mocks.handler.reject_invite(INVITE_ID, email)
        mocks.invites_repository.delete_organization_invite.assert_awaited_once_with(
            ORGANIZATION_ID, INVITE_ID
        )

    async def test_get_organization_invites_returns_organization_invites(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        invite: OrganizationInvite,
    ) -> None:
        expected = [invite]

        mocks.invites_repository.get_invites_by_organization_id.return_value = expected

        actual = await mocks.handler.get_organization_invites(USER_ID, ORGANIZATION_ID)

        assert actual == expected
        mocks.invites_repository.get_invites_by_organization_id.assert_awaited_once()
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ORGANIZATION_INVITE, Action.LIST
        )

    async def test_get_user_invites_returns_invites_for_email(
        self,
        mocks: CollaboratorMocks[OrganizationHandler],
        user_invite: UserInvite,
    ) -> None:
        expected = [user_invite]
        mocks.invites_repository.get_invites_by_user_email.return_value = expected

        actual = await mocks.handler.get_user_invites(user_invite.email)

        assert actual == expected
        mocks.invites_repository.get_invites_by_user_email.assert_awaited_once()
