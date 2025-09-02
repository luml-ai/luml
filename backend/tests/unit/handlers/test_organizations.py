from unittest.mock import AsyncMock, Mock, patch

import pytest

from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.infra.exceptions import (
    InsufficientPermissionsError,
    NotFoundError,
    OrganizationLimitReachedError,
)
from dataforce_studio.models import OrganizationOrm
from dataforce_studio.schemas.organization import (
    Organization,
    OrganizationCreateIn,
    OrganizationDetails,
    OrganizationSwitcher,
    OrganizationUpdate,
    OrgRole,
)

handler = OrganizationHandler()


@patch(
    "dataforce_studio.handlers.organizations.UserRepository.get_organization_details",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_org_members_limit_raises(
    mock_get_organization_details: AsyncMock,
) -> None:
    mock_get_organization_details.return_value = Mock(
        members_limit=50, total_members=200
    )

    with pytest.raises(OrganizationLimitReachedError):
        await handler._check_org_members_limit(organization_id=1)

    mock_get_organization_details.assert_awaited_once()


@patch(
    "dataforce_studio.handlers.organizations.UserRepository.get_user_organizations",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_user_organizations(
    mock_get_user_organizations: AsyncMock, test_org: Organization
) -> None:
    user_id = 1
    expected = [
        OrganizationSwitcher(
            id=test_org.id,
            name=test_org.name,
            logo=test_org.logo,
            created_at=test_org.created_at,
            updated_at=test_org.updated_at,
            role=OrgRole.MEMBER,
        )
    ]
    mock_get_user_organizations.return_value = expected

    actual = await handler.get_user_organizations(user_id)

    assert actual == expected
    mock_get_user_organizations.assert_awaited_once_with(user_id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.UserRepository.get_organization_details",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_organization(
    mock_get_organization_details: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    test_org_details: OrganizationDetails,
) -> None:
    user_id = 1
    organization_id = 1
    expected = test_org_details

    mock_get_organization_details.return_value = expected
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    actual = await handler.get_organization(user_id, organization_id)

    assert actual
    mock_get_organization_details.assert_awaited_once_with(organization_id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.UserRepository.get_organization_details",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_organization_not_found(
    mock_get_organization_details: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = 1
    organization_id = 1
    mock_get_organization_details.return_value = None
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    with pytest.raises(
        NotFoundError,
        match="Organization not found",
    ):
        await handler.get_organization(user_id, organization_id)

    mock_get_organization_details.assert_awaited_once_with(organization_id)


@patch(
    "dataforce_studio.handlers.organizations.UserRepository.get_user_organizations_membership_count",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.UserRepository.create_organization",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_organization(
    mock_create_organization: AsyncMock,
    mock_get_user_organizations_membership_count: AsyncMock,
    test_org: Organization,
) -> None:
    user_id = 1
    org_to_create = OrganizationCreateIn(name=test_org.name, logo=test_org.logo)
    expected = test_org

    mock_get_user_organizations_membership_count.return_value = 0
    mock_create_organization.return_value = OrganizationOrm(
        id=test_org.id,
        name=test_org.name,
        logo=test_org.logo,
        created_at=test_org.created_at,
        updated_at=test_org.updated_at,
    )

    actual = await handler.create_organization(user_id, org_to_create)

    assert actual
    assert actual == expected
    mock_create_organization.assert_awaited_once_with(user_id, org_to_create)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.UserRepository.update_organization",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.UserRepository.get_organization_details",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_organization(
    mock_get_organization_details: AsyncMock,
    mock_update_organization: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    test_org_details: OrganizationDetails,
) -> None:
    expected = test_org_details
    user_id = 1

    mock_get_organization_details.return_value = expected
    mock_update_organization.return_value = expected
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    update_org = OrganizationUpdate(name=expected.name, logo=expected.logo)
    actual = await handler.update_organization(user_id, expected.id, update_org)

    assert actual == expected
    mock_update_organization.assert_awaited_once()


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.UserRepository.update_organization",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_organization_not_found(
    mock_update_organization: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = 1
    organization_id = 1
    organization_to_update = OrganizationUpdate(name="test", logo=None)

    mock_update_organization.return_value = None
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    with pytest.raises(
        NotFoundError,
        match="Organization not found",
    ):
        await handler.update_organization(
            user_id, organization_id, organization_to_update
        )

    mock_update_organization.assert_awaited_once_with(
        organization_id, organization_to_update
    )


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.UserRepository.delete_organization",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.UserRepository.get_organization_details",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_organization(
    mock_get_organization_details: AsyncMock,
    mock_delete_organization: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    test_org_details: OrganizationDetails,
) -> None:
    user_id = 1
    organization_id = 1

    mock_delete_organization.return_value = None
    mock_get_organization_details.return_value = test_org_details
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    await handler.delete_organization(user_id, organization_id)

    mock_delete_organization.assert_awaited_once_with(organization_id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.UserRepository.delete_organization_member_by_user_id",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_leave_from_organization(
    mock_delete_organization_member_by_user_id: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = 1
    organization_id = 1

    mock_delete_organization_member_by_user_id.return_value = None
    mock_get_organization_member_role.return_value = OrgRole.MEMBER

    await handler.leave_from_organization(user_id, organization_id)

    mock_delete_organization_member_by_user_id.assert_awaited_once_with(
        user_id, organization_id
    )


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.UserRepository.delete_organization_member_by_user_id",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_leave_from_organization_owner(
    mock_delete_organization_member_by_user_id: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = 1
    organization_id = 1

    mock_delete_organization_member_by_user_id.return_value = None
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    with pytest.raises(InsufficientPermissionsError):
        await handler.leave_from_organization(user_id, organization_id)
