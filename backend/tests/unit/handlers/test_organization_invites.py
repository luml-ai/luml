from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import UUID

import pytest
from luml.handlers.organizations import OrganizationHandler
from luml.infra.exceptions import ApplicationError
from luml.models import OrganizationInviteOrm
from luml.schemas.organization import (
    CreateOrganizationInvite,
    CreateOrganizationInviteIn,
    OrganizationInvite,
    OrganizationMemberCreate,
    OrgRole,
    UserInvite,
)
from luml.schemas.user import CreateUser, UserOut

handler = OrganizationHandler()


@patch(
    "luml.handlers.organizations.InviteRepository.get_organization_invite_by_email",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.organizations.UserRepository.get_organization_member_by_email",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.organizations.UserRepository.get_public_user_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.organizations.InviteRepository.get_invite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.organizations.UserRepository.get_organization_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.organizations.EmailHandler.send_organization_invite_email",
    new_callable=MagicMock,
)
@patch(
    "luml.handlers.organizations.UserRepository.get_organization_members_count",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.organizations.InviteRepository.create_organization_invite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_send_invite(
    mock_create_organization_invite: AsyncMock,
    mock_get_organization_members_count: AsyncMock,
    mock_send_organization_invite_email: MagicMock,
    mock_get_organization_details: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_invite: AsyncMock,
    mock_get_public_user_by_id: AsyncMock,
    mock_get_organization_member_by_email: AsyncMock,
    mock_get_organization_invite_by_email: AsyncMock,
    invite_data: CreateOrganizationInvite,
    test_user_out: UserOut,
) -> None:
    invite_id = UUID("0199c416-6117-7a3d-a91c-9b4037837882")

    invite = CreateOrganizationInviteIn(
        email=invite_data.email,
        role=invite_data.role,
        organization_id=invite_data.organization_id,
    )
    mocked_invite = OrganizationInvite(
        id=invite_id,
        email=invite_data.email,
        role=invite_data.role,
        organization_id=invite_data.organization_id,
        created_at=datetime.now(),
    )

    mock_get_organization_invite_by_email.return_value = None
    mock_get_organization_member_by_email.return_value = None
    mock_get_organization_members_count.return_value = 0
    mock_get_public_user_by_id.return_value = test_user_out
    mock_create_organization_invite.return_value = mocked_invite
    mock_get_invite.return_value = mocked_invite
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_organization_details.return_value = Mock(members_limit=50, total_members=0)

    result = await handler.send_invite(test_user_out.id, invite)

    assert result == mocked_invite

    mock_send_organization_invite_email.assert_called_once()
    mock_create_organization_invite.assert_awaited_once()


@patch(
    "luml.handlers.organizations.UserRepository.get_public_user_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_send_invite_to_yourself(
    mock_get_organization_member_role: AsyncMock,
    mock_get_public_user_by_id: AsyncMock,
    test_user_create: CreateUser,
    invite_data: CreateOrganizationInvite,
    test_user_out: UserOut,
) -> None:
    invite = CreateOrganizationInviteIn(
        email=test_user_out.email,
        role=invite_data.role,
        organization_id=invite_data.organization_id,
    )

    mock_get_public_user_by_id.return_value = test_user_out
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    with pytest.raises(ApplicationError, match="You can't invite yourself"):
        await handler.send_invite(test_user_out.id, invite)


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.organizations.InviteRepository.delete_organization_invite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_cancel_invite(
    mock_delete_organization_invite: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    invite_id = UUID("0199c416-6117-7a3d-a91c-9b4037837882")

    mock_delete_organization_invite.return_value = None
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    await handler.cancel_invite(user_id, organization_id, invite_id)
    mock_delete_organization_invite.assert_awaited_once_with(invite_id)


@patch(
    "luml.handlers.organizations.UserRepository.get_user_organizations_membership_count",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.organizations.UserRepository.get_organization_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.organizations.UserRepository.get_organization_members_count",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.organizations.UserRepository.create_organization_member",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.organizations.InviteRepository.get_invite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.organizations.InviteRepository.delete_organization_invites_for_user",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_accept_invite(
    mock_delete_organization_invites_for_user: AsyncMock,
    mock_get_invite: AsyncMock,
    mock_create_organization_member: AsyncMock,
    mock_get_organization_members_count: AsyncMock,
    mock_get_organization_details: AsyncMock,
    mock_get_user_organizations_membership_count: AsyncMock,
    invite_accept_data: CreateOrganizationInvite,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    invite = OrganizationInviteOrm(**invite_accept_data.model_dump())

    mock_get_invite.return_value = invite
    mock_get_organization_members_count.return_value = 0
    mock_get_user_organizations_membership_count.return_value = 0
    mock_get_organization_details.return_value = Mock(members_limit=50, total_members=0)

    await handler.accept_invite(invite.id, user_id)
    mock_get_invite.assert_awaited_once_with(invite.id)
    mock_get_organization_details.assert_awaited_once_with(invite.organization_id)
    mock_create_organization_member.assert_awaited_once_with(
        OrganizationMemberCreate(
            user_id=user_id,
            organization_id=invite.organization_id,
            role=OrgRole(invite.role),
        )
    )
    mock_delete_organization_invites_for_user.assert_awaited_once_with(
        invite.organization_id, invite.email
    )


@patch(
    "luml.handlers.organizations.InviteRepository.delete_organization_invite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_reject_invite(
    mock_delete_organization_invite: AsyncMock,
) -> None:
    invite_id = UUID("0199c416-6117-7a3d-a91c-9b4037837882")
    mock_delete_organization_invite.return_value = None

    await handler.reject_invite(invite_id)
    mock_delete_organization_invite.assert_awaited_once_with(invite_id)


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.organizations.InviteRepository.get_invites_by_organization_id",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_organization_invites(
    mock_get_organization_invites: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    invite_get_data: OrganizationInvite,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    expected = [invite_get_data]

    mock_get_organization_invites.return_value = expected
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    actual = await handler.get_organization_invites(user_id, organization_id)

    assert actual == expected
    mock_get_organization_invites.assert_awaited_once()


@patch(
    "luml.handlers.organizations.InviteRepository.get_invites_by_user_email",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_user_invites(
    mock_get_user_invites: AsyncMock,
    invite_user_get_data: UserInvite,
) -> None:
    expected = [invite_user_get_data]
    mock_get_user_invites.return_value = expected

    actual = await handler.get_user_invites(invite_user_get_data.email)

    assert actual == expected
    mock_get_user_invites.assert_awaited_once()
