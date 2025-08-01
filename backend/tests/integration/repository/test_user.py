import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.user import (
    AuthProvider,
    CreateUser,
    UpdateUser,
    User,
    UserOut,
)


@pytest_asyncio.fixture(scope="function")
async def get_created_user(
    create_database_and_apply_migrations: str, test_user: dict
) -> dict:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)

    user = await repo.create_user(CreateUser(**test_user))

    return {
        "engine": engine,
        "repo": repo,
        "user": user,
    }


@pytest.mark.asyncio
async def test_create_user_and_organization(
    create_database_and_apply_migrations: str,
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)
    user = CreateUser(
        email=f"test_create_user_org_{uuid.uuid4()}@email.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password="hashed_password",
    )

    created_user = await repo.create_user(user)
    fetched_user = await repo.get_user(user.email)
    fetched_org = (await repo.get_user_organizations(fetched_user.id))[0]
    fetched_org_member = (await repo.get_organization_users(fetched_org.id))[0]

    assert fetched_org.name == "Test's organization"
    # assert fetched_org_member.user_id == fetched_user.id
    assert fetched_org_member.organization_id == fetched_org.id
    assert created_user == fetched_user


@pytest.mark.asyncio
async def test_get_user(get_created_user: dict) -> None:
    data = get_created_user
    repo, user = data["repo"], data["user"]

    fetched_user = await repo.get_user(user.email)

    assert fetched_user
    assert isinstance(fetched_user, User)


@pytest.mark.asyncio
async def test_get_public_user(get_created_user: dict) -> None:
    data = get_created_user
    repo, user = data["repo"], data["user"]

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
async def test_delete_user(get_created_user: dict) -> None:
    data = get_created_user
    repo, user = data["repo"], data["user"]

    deleted_user = await repo.delete_user(user.email)
    fetch_deleted_user = await repo.get_user(user.email)

    assert deleted_user is None
    assert fetch_deleted_user is None


@pytest.mark.asyncio
async def test_update_user(get_created_user: dict) -> None:
    repo = get_created_user["repo"]
    original_user = get_created_user["user"]

    user_update_data = UpdateUser(email=original_user.email, email_verified=True)

    await repo.update_user(user_update_data)
    fetched_user = await repo.get_user(user_update_data.email)

    assert fetched_user.email == user_update_data.email
    assert fetched_user.email_verified == user_update_data.email_verified


@pytest.mark.asyncio
async def test_update_user_not_found(get_created_user: dict) -> None:
    data = get_created_user
    repo = data["repo"]
    user_update_data = {"email": "user_not_found@example.com", "email_verified": True}

    updated_user = await repo.update_user(UpdateUser.model_validate(user_update_data))

    assert updated_user is False
