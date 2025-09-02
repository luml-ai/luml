from unittest.mock import AsyncMock, Mock, patch

import pytest

from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.schemas.organization import (
    OrganizationMember,
    OrganizationMemberCreate,
    OrgRole,
    UpdateOrganizationMember,
)

handler = OrganizationHandler()


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.UserRepository.get_organization_members",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_organization_members_data(
    mock_get_organization_members: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    member_data: OrganizationMember,
) -> None:
    user_id = 1

    expected = [member_data]
    mock_get_organization_members.return_value = expected
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    actual = await handler.get_organization_members_data(
        user_id, member_data.organization_id
    )

    assert actual == expected
    mock_get_organization_members.assert_awaited_once()


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_by_id",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.UserRepository.update_organization_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_organization_member_by_id(
    mock_update_organization_member: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_organization_member_by_id: AsyncMock,
    member_data: OrganizationMember,
) -> None:
    user_id = 8765

    mock_update_organization_member.return_value = member_data
    mock_get_organization_member_by_id.return_value = member_data
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    update_member = UpdateOrganizationMember(role=member_data.role)
    actual = await handler.update_organization_member_by_id(
        user_id, member_data.organization_id, member_data.id, update_member
    )

    assert actual == member_data
    mock_update_organization_member.assert_awaited_once()


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_by_id",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.UserRepository.delete_organization_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_organization_member_by_id(
    mock_delete_organization_member: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_organization_member_by_id: AsyncMock,
    member_data: OrganizationMember,
) -> None:
    user_id = 346

    mock_delete_organization_member.return_value = None
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_organization_member_by_id.return_value = member_data

    await handler.delete_organization_member_by_id(
        user_id, member_data.organization_id, member_data.id
    )
    mock_delete_organization_member.assert_awaited_once_with(member_data.id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.UserRepository.get_organization_details",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.UserRepository.create_organization_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_add_organization_member(
    mock_create_organization_member: AsyncMock,
    mock_get_organization_details: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    member_data: OrganizationMember,
) -> None:
    member_create = OrganizationMemberCreate(
        user_id=member_data.user.id,
        organization_id=member_data.organization_id,
        role=member_data.role,
    )

    mock_create_organization_member.return_value = member_data
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_organization_details.return_value = Mock(members_limit=50, total_members=0)

    actual = await handler.add_organization_member(
        member_create.user_id, member_create.organization_id, member_create
    )

    assert actual == member_data
    mock_create_organization_member.assert_awaited_once_with(
        OrganizationMemberCreate(
            user_id=member_create.user_id,
            organization_id=member_create.organization_id,
            role=member_create.role,
        )
    )
