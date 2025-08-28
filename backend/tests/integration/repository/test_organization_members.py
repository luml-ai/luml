import uuid

import pytest

from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.organization import (
    OrganizationMemberCreate,
    OrgRole,
    UpdateOrganizationMember,
)
from dataforce_studio.schemas.user import CreateUser
from tests.conftest import FixtureData

organization_data = {"name": "test organization", "logo": None}

organization_member_data = {
    "user_id": "test organization",
    "organization_id": None,
    "role": None,
}


@pytest.mark.asyncio
async def test_create_organization_member(
    create_organization_with_user: FixtureData, test_user: CreateUser
) -> None:
    data = create_organization_with_user
    repo = UserRepository(data.engine)
    created_organization = data.organization
    test_user.email = f"{uuid.uuid4()}@gmail.com"
    user = await repo.create_user(test_user)
    created_member = await repo.create_organization_member(
        OrganizationMemberCreate(
            user_id=user.id,
            organization_id=created_organization.id,
            role=OrgRole.MEMBER,
        )
    )

    assert created_member.id
    assert created_member.organization_id == created_organization.id
    assert created_member.user.id == user.id
    assert created_member.role == OrgRole.MEMBER


@pytest.mark.asyncio
async def test_update_organization_member(
    create_organization_with_user: FixtureData,
) -> None:
    data = create_organization_with_user
    repo = UserRepository(data.engine)
    member = data.member

    updated_member = await repo.update_organization_member(
        member.id, UpdateOrganizationMember(role=OrgRole.ADMIN)
    )

    assert updated_member.id == member.id
    assert updated_member.role == OrgRole.ADMIN


@pytest.mark.asyncio
async def test_delete_organization_member(
    create_organization_with_user: FixtureData,
) -> None:
    data = create_organization_with_user
    repo = UserRepository(data.engine)
    created_organization, member = (
        data.organization,
        data.member,
    )

    deleted_member = await repo.delete_organization_member(member.id)
    org_members_count = await repo.get_organization_members_count(
        created_organization.id
    )

    assert deleted_member is None
    assert org_members_count == 0 or org_members_count is None


@pytest.mark.asyncio
async def test_get_organization_members_count(
    create_organization_with_members: FixtureData,
) -> None:
    data = create_organization_with_members
    repo = UserRepository(data.engine)
    organization, members = (data.organization, data.members)

    count = await repo.get_organization_members_count(organization.id)

    assert len(members) == count


@pytest.mark.asyncio
async def test_get_organization_members(
    create_organization_with_members: FixtureData,
) -> None:
    data = create_organization_with_members
    repo = UserRepository(data.engine)
    organization, members = (data.organization, data.members)

    db_members = await repo.get_organization_members(organization.id)

    assert db_members
    assert len(members) == len(db_members)
    assert db_members[0].id
    assert db_members[0].organization_id == organization.id
    assert db_members[0].user.id
