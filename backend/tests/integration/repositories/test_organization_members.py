import uuid

import pytest
from luml.repositories.users import UserRepository
from luml.schemas.organization import (
    OrganizationCreateIn,
    OrganizationMemberCreate,
    OrgRole,
    UpdateOrganizationMember,
)
from luml.schemas.user import CreateUser
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.seeds import (
    OrganizationFixtureData,
    OrganizationWithMembersFixtureData,
)


@pytest.fixture
def repository(engine: AsyncEngine) -> UserRepository:
    return UserRepository(engine)


class TestOrganizationMemberRepository:
    async def test_create_organization_member_returns_member_with_user(
        self,
        repository: UserRepository,
        seeded_organization: OrganizationFixtureData,
        new_user: CreateUser,
    ) -> None:
        new_user.email = f"test_{uuid.uuid4()}@example.com"
        created_user = await repository.create_user(new_user)
        created_member = await repository.create_organization_member(
            OrganizationMemberCreate(
                user_id=created_user.id,
                organization_id=seeded_organization.organization.id,
                role=OrgRole.MEMBER,
            )
        )

        assert created_member.id
        assert created_member.organization_id == seeded_organization.organization.id
        assert created_member.user.id == created_user.id
        assert created_member.role == OrgRole.MEMBER

    async def test_update_organization_member_changes_role(
        self,
        repository: UserRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        updated_member = await repository.update_organization_member(
            seeded_organization.organization.id,
            seeded_organization.member.id,
            UpdateOrganizationMember(role=OrgRole.ADMIN),
        )

        assert updated_member
        assert updated_member.id == seeded_organization.member.id
        assert updated_member.role == OrgRole.ADMIN

    async def test_delete_organization_member_removes_member(
        self,
        repository: UserRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        await repository.delete_organization_member(
            seeded_organization.organization.id, seeded_organization.member.id
        )
        fetched_member = await repository.get_organization_member_by_id(
            seeded_organization.organization.id, seeded_organization.member.id
        )

        assert fetched_member is None

    async def test_foreign_organization_cannot_read_update_or_delete_member(
        self,
        repository: UserRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        data = seeded_organization
        other_org = await repository.create_organization(
            data.user.id, OrganizationCreateIn(name="other organization")
        )

        assert (
            await repository.get_organization_member_by_id(other_org.id, data.member.id)
            is None
        )
        assert (
            await repository.update_organization_member(
                other_org.id,
                data.member.id,
                UpdateOrganizationMember(role=OrgRole.MEMBER),
            )
            is None
        )
        await repository.delete_organization_member(other_org.id, data.member.id)

        unchanged = await repository.get_organization_member_by_id(
            data.organization.id, data.member.id
        )
        assert unchanged is not None
        assert unchanged.id == data.member.id
        assert unchanged.role == OrgRole.OWNER

    async def test_get_organization_members_count_returns_number_of_members(
        self,
        repository: UserRepository,
        seeded_organization_with_members: OrganizationWithMembersFixtureData,
    ) -> None:
        count = await repository.get_organization_members_count(
            seeded_organization_with_members.organization.id
        )

        assert len(seeded_organization_with_members.members) == count

    async def test_get_organization_members_returns_members_ordered_by_role(
        self,
        repository: UserRepository,
        seeded_organization_with_members: OrganizationWithMembersFixtureData,
    ) -> None:
        await repository.update_organization_member(
            seeded_organization_with_members.organization.id,
            seeded_organization_with_members.member.id,
            UpdateOrganizationMember(role=OrgRole.MEMBER),
        )
        await repository.update_organization_member(
            seeded_organization_with_members.organization.id,
            seeded_organization_with_members.members[-2].id,
            UpdateOrganizationMember(role=OrgRole.ADMIN),
        )
        await repository.delete_organization_member(
            seeded_organization_with_members.organization.id,
            seeded_organization_with_members.members[-1].id,
        )
        await repository.create_owner(
            seeded_organization_with_members.members[-1].user.id,
            seeded_organization_with_members.organization.id,
        )

        db_members = await repository.get_organization_members(
            seeded_organization_with_members.organization.id
        )

        assert db_members
        assert len(seeded_organization_with_members.members) == len(db_members)
        assert db_members[0].id
        assert (
            db_members[0].organization_id
            == seeded_organization_with_members.organization.id
        )
        assert db_members[0].user.id
        assert [member.role for member in db_members] == [
            OrgRole.OWNER,
            OrgRole.ADMIN,
            *([OrgRole.MEMBER] * (len(seeded_organization_with_members.members) - 2)),
        ]
