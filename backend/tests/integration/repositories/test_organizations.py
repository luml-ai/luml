import pytest
from luml.repositories.users import UserRepository
from luml.schemas.organization import Organization, OrganizationCreateIn
from luml.schemas.user import CreateUser
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.seeds import OrganizationWithMembersFixtureData


@pytest.fixture
def repository(engine: AsyncEngine) -> UserRepository:
    return UserRepository(engine)


class TestOrganizationRepository:
    async def test_create_organization_returns_created_organization(
        self,
        repository: UserRepository,
        new_user: CreateUser,
        organization: Organization,
    ) -> None:
        created_user = await repository.create_user(new_user)

        created_organization = await repository.create_organization(
            created_user.id,
            OrganizationCreateIn(name=organization.name, logo=organization.logo),
        )

        assert created_organization.id
        assert created_organization.name == organization.name
        assert created_organization.logo == organization.logo

    async def test_get_user_organizations_returns_organizations_with_role(
        self,
        repository: UserRepository,
        seeded_organization_with_members: OrganizationWithMembersFixtureData,
    ) -> None:
        organizations = await repository.get_user_organizations(
            seeded_organization_with_members.user.id
        )

        assert organizations
        assert hasattr(organizations[0], "id")
        assert hasattr(organizations[0], "name")
        assert hasattr(organizations[0], "logo")
        assert hasattr(organizations[0], "role")

    async def test_get_organization_details_returns_members_and_invites(
        self,
        repository: UserRepository,
        seeded_organization_with_members: OrganizationWithMembersFixtureData,
    ) -> None:
        fetched_organization = await repository.get_organization_details(
            seeded_organization_with_members.organization.id
        )

        assert fetched_organization
        assert hasattr(fetched_organization, "id")
        assert hasattr(fetched_organization, "name")
        assert hasattr(fetched_organization, "logo")
        assert isinstance(fetched_organization.members, list)
        assert isinstance(fetched_organization.invites, list)
