from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest
from luml.handlers.organizations import OrganizationHandler
from luml.infra.exceptions import InsufficientPermissionsError
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

    member_to_update = member_data.model_copy()
    member_to_update.role = OrgRole.MEMBER

    mock_update_organization_member.return_value = member_data
    mock_get_organization_member_by_id.return_value = member_to_update
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    update_member = UpdateOrganizationMember(role=OrgRole.ADMIN)
    actual = await handler.update_organization_member_by_id(
        user_id, member_to_update.organization_id, member_to_update.id, update_member
    )

    assert actual == member_data
    mock_update_organization_member.assert_awaited_once()


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
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
    mock_get_organization_member_role: AsyncMock,
    mock_get_organization_member_by_id: AsyncMock,
    member_data: OrganizationMember,
) -> None:
    member_data_new = member_data.model_copy()
    member_data_new.role = OrgRole.MEMBER

    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = member_data_new.organization_id

    mock_delete_organization_member.return_value = None
    mock_get_organization_member_by_id.return_value = member_data_new
    mock_get_organization_member_role.return_value = OrgRole.ADMIN

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
async def test_add_organization_member_uses_path_organization_id(
    mock_create_organization_member: AsyncMock,
    mock_get_organization_details: AsyncMock,
    mock_check_permissions: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    member_data: OrganizationMember,
) -> None:
    user_id = member_data.user.id
    user_to_create_member_for = UUID("0199c419-b7c1-71d6-8382-5697010cee46")
    organization_id = member_data.organization_id
    body_organization_id = UUID("0199c43e-8b7b-7ae8-a84b-3ec65bb63a17")

    member_create = OrganizationMemberCreate(
        user_id=user_to_create_member_for,
        organization_id=body_organization_id,
        role=OrgRole.MEMBER,
    )

    mock_create_organization_member.return_value = member_data
    mock_get_organization_details.return_value = Mock(members_limit=50, total_members=0)
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    actual = await handler.add_organization_member(
        user_id, organization_id, member_create
    )

    assert actual == member_data
    mock_create_organization_member.assert_awaited_once_with(
        OrganizationMemberCreate(
            user_id=user_to_create_member_for,
            organization_id=organization_id,
            role=member_create.role,
        )
    )
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ORGANIZATION_USER, Action.CREATE
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
async def test_admin_can_not_assign_new_admin(
    mock_update_organization_member: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_organization_member_by_id: AsyncMock,
    member_data: OrganizationMember,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")

    member_to_update = member_data.model_copy()
    member_to_update.role = OrgRole.MEMBER

    mock_get_organization_member_by_id.return_value = member_to_update
    mock_get_organization_member_role.return_value = OrgRole.ADMIN

    with pytest.raises(
        InsufficientPermissionsError,
        match="Only Organization Owner can assign new admins.",
    ):
        await handler.update_organization_member_by_id(
            user_id,
            member_to_update.organization_id,
            member_to_update.id,
            UpdateOrganizationMember(role=OrgRole.ADMIN),
        )

    mock_update_organization_member.assert_not_awaited()


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
async def test_admin_can_not_demote_another_admin(
    mock_update_organization_member: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_organization_member_by_id: AsyncMock,
    member_data: OrganizationMember,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")

    member_to_update = member_data.model_copy()
    member_to_update.role = OrgRole.ADMIN

    mock_get_organization_member_by_id.return_value = member_to_update
    mock_get_organization_member_role.return_value = OrgRole.ADMIN

    with pytest.raises(
        InsufficientPermissionsError,
        match="Only Organization Owner can change admin roles.",
    ):
        await handler.update_organization_member_by_id(
            user_id,
            member_to_update.organization_id,
            member_to_update.id,
            UpdateOrganizationMember(role=OrgRole.MEMBER),
        )

    mock_update_organization_member.assert_not_awaited()


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
async def test_owner_role_can_not_be_changed(
    mock_update_organization_member: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_organization_member_by_id: AsyncMock,
    member_data: OrganizationMember,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")

    mock_get_organization_member_by_id.return_value = member_data
    mock_get_organization_member_role.return_value = OrgRole.ADMIN

    with pytest.raises(
        InsufficientPermissionsError,
        match="Organization Owner role can not be changed.",
    ):
        await handler.update_organization_member_by_id(
            user_id,
            member_data.organization_id,
            member_data.id,
            UpdateOrganizationMember(role=OrgRole.MEMBER),
        )

    mock_update_organization_member.assert_not_awaited()


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
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
async def test_admin_can_not_remove_another_admin(
    mock_delete_organization_member: AsyncMock,
    mock_check_permissions: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_organization_member_by_id: AsyncMock,
    member_data: OrganizationMember,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")

    member_to_delete = member_data.model_copy()
    member_to_delete.role = OrgRole.ADMIN

    mock_get_organization_member_by_id.return_value = member_to_delete
    mock_get_organization_member_role.return_value = OrgRole.ADMIN

    with pytest.raises(
        InsufficientPermissionsError,
        match="Only Organization Owner can remove admins.",
    ):
        await handler.delete_organization_member_by_id(
            user_id, member_to_delete.organization_id, member_to_delete.id
        )

    mock_delete_organization_member.assert_not_awaited()


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
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
async def test_owner_can_remove_admin(
    mock_delete_organization_member: AsyncMock,
    mock_check_permissions: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_organization_member_by_id: AsyncMock,
    member_data: OrganizationMember,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")

    member_to_delete = member_data.model_copy()
    member_to_delete.role = OrgRole.ADMIN

    mock_delete_organization_member.return_value = None
    mock_get_organization_member_by_id.return_value = member_to_delete
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    await handler.delete_organization_member_by_id(
        user_id, member_to_delete.organization_id, member_to_delete.id
    )

    mock_delete_organization_member.assert_awaited_once_with(member_to_delete.id)
