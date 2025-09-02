import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.organization import Organization, OrganizationCreateIn
from dataforce_studio.schemas.user import CreateUser
from tests.conftest import OrganizationWithMembersFixtureData


@pytest.mark.asyncio
async def test_create_organization(
    create_database_and_apply_migrations: str,
    test_user_create: CreateUser,
    test_org: Organization,
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)
    organization = test_org

    user = await repo.create_user(test_user_create)

    created_organization = await repo.create_organization(
        user.id, OrganizationCreateIn(name=organization.name, logo=organization.logo)
    )

    assert created_organization.id
    assert created_organization.name == test_org.name
    assert created_organization.logo == test_org.logo
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_user_organizations(
    create_organization_with_members: OrganizationWithMembersFixtureData,
) -> None:
    data = create_organization_with_members
    repo = UserRepository(data.engine)
    _members, user = (
        data.members,
        data.user,
    )

    organizations = await repo.get_user_organizations(user.id)

    assert organizations
    assert hasattr(organizations[0], "id")
    assert hasattr(organizations[0], "name")
    assert hasattr(organizations[0], "logo")
    assert hasattr(organizations[0], "role")


@pytest.mark.asyncio
async def test_get_organization_details(
    create_organization_with_members: OrganizationWithMembersFixtureData,
) -> None:
    data = create_organization_with_members
    repo = UserRepository(data.engine)
    org = data.organization

    organization = await repo.get_organization_details(org.id)

    assert organization
    assert hasattr(organization, "id")
    assert hasattr(organization, "name")
    assert hasattr(organization, "logo")
    assert isinstance(organization.members, list)
    assert isinstance(organization.invites, list)
