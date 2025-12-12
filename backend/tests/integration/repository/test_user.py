import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import pytest
import pytest_asyncio
from luml.repositories.users import UserRepository
from luml.schemas.user import (
    AuthProvider,
    CreateUser,
    UpdateUser,
    User,
    UserOut,
)
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


@dataclass
class UserFixtureData:
    engine: AsyncEngine
    repo: UserRepository
    user: User


@pytest_asyncio.fixture(scope="function")
async def get_created_user(
    create_database_and_apply_migrations: str, test_user_create: CreateUser
) -> AsyncGenerator[UserFixtureData]:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)

    user = await repo.create_user(test_user_create)

    yield UserFixtureData(engine=engine, repo=repo, user=user)


@pytest.mark.asyncio
async def test_create_user_and_organization(
    create_database_and_apply_migrations: str,
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)
    user = CreateUser(
        email=f"test_{uuid.uuid4()}@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password="hashed_password",
    )

    created_user = await repo.create_user(user)
    fetched_user = await repo.get_user(user.email)
    assert fetched_user
    fetched_org = (await repo.get_user_organizations(fetched_user.id))[0]
    assert fetched_org
    fetched_org_member = (await repo.get_organization_users(fetched_org.id))[0]

    assert fetched_org.name == "Test's organization"
    assert fetched_org_member
    assert fetched_org_member.organization_id == fetched_org.id
    assert created_user == fetched_user


@pytest.mark.asyncio
async def test_get_user(get_created_user: UserFixtureData) -> None:
    data = get_created_user
    repo, user = data.repo, data.user

    fetched_user = await repo.get_user(user.email)

    assert fetched_user
    assert isinstance(fetched_user, User)


@pytest.mark.asyncio
async def test_get_public_user(get_created_user: UserFixtureData) -> None:
    data = get_created_user
    repo, user = data.repo, data.user

    fetched_user = await repo.get_public_user(user.email)

    assert fetched_user
    assert isinstance(fetched_user, UserOut)
    assert fetched_user.id
    assert fetched_user.email
    assert hasattr(fetched_user, "full_name")
    assert hasattr(fetched_user, "disabled")
    assert hasattr(fetched_user, "photo")
    assert not hasattr(fetched_user, "hashed_password")


@pytest.mark.asyncio
async def test_delete_user(get_created_user: UserFixtureData) -> None:
    data = get_created_user
    repo, user = data.repo, data.user

    await repo.delete_user(user.email)
    fetch_deleted_user = await repo.get_user(user.email)

    assert fetch_deleted_user is None


@pytest.mark.asyncio
async def test_update_user(get_created_user: UserFixtureData) -> None:
    data = get_created_user
    repo, user = data.repo, data.user

    user_update_data = UpdateUser(email=user.email, email_verified=True)

    await repo.update_user(user_update_data)
    fetched_user = await repo.get_user(user_update_data.email)

    assert fetched_user
    assert fetched_user.email == user_update_data.email
    assert fetched_user.email_verified == user_update_data.email_verified


@pytest.mark.asyncio
async def test_update_user_not_found(get_created_user: UserFixtureData) -> None:
    repo = get_created_user.repo
    user_update_data = {"email": "test@example.com", "email_verified": True}

    updated_user = await repo.update_user(UpdateUser.model_validate(user_update_data))

    assert updated_user is False
