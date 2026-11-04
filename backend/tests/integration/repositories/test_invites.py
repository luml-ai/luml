import uuid

import pytest
from luml.models import OrganizationOrm
from luml.repositories.invites import InviteRepository
from luml.repositories.users import UserRepository
from luml.schemas.organization import (
    CreateOrganizationInvite,
    OrganizationCreateIn,
    OrgRole,
)
from luml.schemas.user import User
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.seeds import OrganizationFixtureData


def get_invite_obj(
    organization: OrganizationOrm, user: User
) -> CreateOrganizationInvite:
    return CreateOrganizationInvite(
        email=f"test_{uuid.uuid4()}@example.com",
        role=OrgRole.MEMBER,
        organization_id=organization.id,
        invited_by=user.id,
    )


@pytest.fixture
def repository(engine: AsyncEngine) -> InviteRepository:
    return InviteRepository(engine)


class TestInviteRepository:
    async def test_create_organization_invite_returns_created_invite(
        self,
        repository: InviteRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        invite_create = get_invite_obj(
            seeded_organization.organization, seeded_organization.user
        )

        created_invite = await repository.create_organization_invite(invite_create)

        assert created_invite.email == invite_create.email
        assert created_invite.organization_id == invite_create.organization_id

    async def test_delete_organization_invite_removes_invite(
        self,
        repository: InviteRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        invite_create = get_invite_obj(
            seeded_organization.organization, seeded_organization.user
        )

        created_invite = await repository.create_organization_invite(invite_create)
        assert created_invite

        await repository.delete_organization_invite(
            seeded_organization.organization.id, created_invite.id
        )

        result = await repository.get_invite(created_invite.id)
        assert result is None

    async def test_delete_organization_invite_keeps_invite_when_organization_differs(
        self,
        repository: InviteRepository,
        engine: AsyncEngine,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        other_organization = await UserRepository(engine).create_organization(
            seeded_organization.user.id, OrganizationCreateIn(name="other org")
        )

        created_invite = await repository.create_organization_invite(
            get_invite_obj(seeded_organization.organization, seeded_organization.user)
        )

        await repository.delete_organization_invite(
            other_organization.id, created_invite.id
        )

        assert await repository.get_invite(created_invite.id) is not None

    async def test_get_invite_returns_invite_with_inviting_user(
        self,
        repository: InviteRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        created_invite = await repository.create_organization_invite(
            get_invite_obj(seeded_organization.organization, seeded_organization.user)
        )
        assert created_invite
        fetched_invite = await repository.get_invite(created_invite.id)

        assert fetched_invite
        assert fetched_invite.id == created_invite.id
        assert fetched_invite.email == created_invite.email
        assert fetched_invite.invited_by_user
        assert fetched_invite.invited_by_user.id == seeded_organization.user.id
        assert fetched_invite.organization_id == created_invite.organization_id

    async def test_get_invites_by_organization_id_returns_all_invites(
        self,
        repository: InviteRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        for _ in range(4):
            await repository.create_organization_invite(
                get_invite_obj(
                    seeded_organization.organization, seeded_organization.user
                )
            )

        invites = await repository.get_invites_by_organization_id(
            seeded_organization.organization.id
        )

        assert invites
        assert isinstance(invites, list)
        assert len(invites) == 4
        assert invites[0].organization_id == seeded_organization.organization.id

    async def test_delete_all_organization_invites_removes_all_invites(
        self,
        repository: InviteRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        for _ in range(4):
            await repository.create_organization_invite(
                get_invite_obj(
                    seeded_organization.organization, seeded_organization.user
                )
            )

        await repository.delete_all_organization_invites(
            seeded_organization.organization.id
        )

        invites = await repository.get_invites_by_organization_id(
            seeded_organization.organization.id
        )

        assert len(invites) == 0

    async def test_email_matching_and_deletion_ignore_case_and_keep_scope(
        self,
        repository: InviteRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        data = seeded_organization
        other_org = await UserRepository(data.engine).create_organization(
            data.user.id, OrganizationCreateIn(name="other organization")
        )
        invite_ids = []
        for organization_id, email in [
            (data.organization.id, "John_x@example.com"),
            (data.organization.id, "JOHN_X@example.com"),
            (data.organization.id, "johnax@example.com"),
            (other_org.id, "John_x@example.com"),
        ]:
            created = await repository.create_organization_invite(
                CreateOrganizationInvite(
                    organization_id=organization_id,
                    email=email,
                    role=OrgRole.MEMBER,
                    invited_by=data.user.id,
                )
            )
            invite_ids.append(created.id)

        listed = await repository.get_invites_by_user_email("john_x@example.com")
        assert {invite.id for invite in listed} == {
            invite_ids[0],
            invite_ids[1],
            invite_ids[3],
        }
        existing = await repository.get_organization_invite_by_email(
            data.organization.id, "john_x@example.com"
        )
        assert existing is not None
        assert existing.id in invite_ids[:2]

        await repository.delete_organization_invites_for_user(
            data.organization.id, "john_x@example.com"
        )

        assert await repository.get_invite(invite_ids[0]) is None
        assert await repository.get_invite(invite_ids[1]) is None
        assert await repository.get_invite(invite_ids[2]) is not None
        assert await repository.get_invite(invite_ids[3]) is not None
