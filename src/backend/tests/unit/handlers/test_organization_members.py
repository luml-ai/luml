from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest
from luml.handlers.organizations import OrganizationHandler
from luml.schemas.organization import (
    OrganizationMember,
    OrganizationMemberCreate,
    OrgRole,
    UpdateOrganizationMember,
)
from luml.schemas.permissions import Action, Resource

handler = OrganizationHandler()


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.organizations.UserRepository.get_organization_members",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_organization_members_data(
    mock_get_organization_members: AsyncMock,
    mock_check_permissions: AsyncMock,
    member_data: OrganizationMember,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = member_data.organization_id

    expected = [member_data]
    mock_get_organization_members.return_value = expected

    actual = await handler.get_organization_members_data(user_id, organization_id)

    assert actual == expected
    mock_get_organization_members.assert_awaited_once()
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ORGANIZATION_USER, Action.LIST
    )


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.organizations.UserRepository.update_organization_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_organization_member_by_id(
    mock_update_organization_member: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_organization_member_by_id: AsyncMock,
    member_data: OrganizationMember,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")

    mock_update_organization_member.return_value = member_data
    mock_get_organization_member_by_id.return_value = member_data
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    update_member = UpdateOrganizationMember(role=OrgRole.ADMIN)
    actual = await handler.update_organization_member_by_id(
        user_id, member_data.organization_id, member_data.id, update_member
    )

    assert actual == member_data
    mock_update_organization_member.assert_awaited_once()


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.organizations.UserRepository.delete_organization_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_organization_member_by_id(
    mock_delete_organization_member: AsyncMock,
    mock_check_permissions: AsyncMock,
    mock_get_organization_member_by_id: AsyncMock,
    member_data: OrganizationMember,
) -> None:
    member_data_new = member_data.model_copy()
    member_data_new.role = OrgRole.MEMBER

    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = member_data_new.organization_id

    mock_delete_organization_member.return_value = None
    mock_get_organization_member_by_id.return_value = member_data_new

    await handler.delete_organization_member_by_id(
        user_id, organization_id, member_data_new.id
    )
    mock_delete_organization_member.assert_awaited_once_with(member_data_new.id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ORGANIZATION_USER, Action.DELETE
    )


@patch(
    "luml.handlers.organizations.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.organizations.UserRepository.get_organization_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.organizations.UserRepository.create_organization_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_add_organization_member(
    mock_create_organization_member: AsyncMock,
    mock_get_organization_details: AsyncMock,
    mock_check_permissions: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    member_data: OrganizationMember,
) -> None:
    user_id = member_data.user.id
    user_to_create_member_for = UUID("0199c419-b7c1-71d6-8382-5697010cee46")
    organization_id = member_data.organization_id

    member_create = OrganizationMemberCreate(
        user_id=user_to_create_member_for,
        organization_id=organization_id,
        role=OrgRole.MEMBER,
    )

    mock_create_organization_member.return_value = member_data
    mock_get_organization_details.return_value = Mock(members_limit=50, total_members=0)
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    actual = await handler.add_organization_member(
        user_id, member_create.organization_id, member_create
    )

    assert actual == member_data
    mock_create_organization_member.assert_awaited_once_with(
        OrganizationMemberCreate(
            user_id=user_to_create_member_for,
            organization_id=member_create.organization_id,
            role=member_create.role,
        )
    )
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ORGANIZATION_USER, Action.CREATE
    )
