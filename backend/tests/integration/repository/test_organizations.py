import datetime
import random
import uuid

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.organization import Organization, OrganizationCreateIn
from dataforce_studio.schemas.user import CreateUser

organization_data = {
    "id": random.randint(2000, 10000),
    "name": "test organization name",
    "logo": None,
    "created_at": datetime.datetime.now(),
    "updated_at": datetime.datetime.now(),
}


@pytest.mark.asyncio
async def test_create_organization(
    create_database_and_apply_migrations: str, test_user: dict
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)
    organization = Organization.model_validate(organization_data)

    new_user = test_user.copy()
    new_user["email"] = f"testcreateorganization_{uuid.uuid4()}@example.com"
    user = await repo.create_user(CreateUser(**new_user))

    created_organization = await repo.create_organization(
        user.id, OrganizationCreateIn(name=organization.name, logo=organization.logo)
    )

    assert created_organization.id
    assert created_organization.name == organization_data["name"]
    assert created_organization.logo == organization_data["logo"]
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_user_organizations(create_organization_with_members: dict) -> None:
    data = create_organization_with_members
    repo, _members, user_owner = (
        data["repo"],
        data["members"],
        data["user_owner"],
    )

    organizations = await repo.get_user_organizations(user_owner.id)

    assert organizations
    assert hasattr(organizations[0], "id")
    assert hasattr(organizations[0], "name")
    assert hasattr(organizations[0], "logo")
    assert hasattr(organizations[0], "role")


@pytest.mark.asyncio
async def test_get_organization_details(create_organization_with_members: dict) -> None:
    data = create_organization_with_members
    repo, org = data["repo"], data["organization"]

    organization = await repo.get_organization_details(org.id)

    assert organization
    assert hasattr(organization, "id")
    assert hasattr(organization, "name")
    assert hasattr(organization, "logo")
    assert isinstance(organization.members, list)
    assert isinstance(organization.invites, list)
