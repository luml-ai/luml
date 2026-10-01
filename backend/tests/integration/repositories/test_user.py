import uuid
from dataclasses import dataclass

import pytest
from luml.models import OrganizationOrm
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.tracks import TrackEntryRepository, TrackRepository
from luml.repositories.users import UserRepository
from luml.schemas.artifacts import ArtifactCreate, ArtifactStatus
from luml.schemas.tracks import TrackCreate, TrackEntryCreate
from luml.schemas.user import (
    AuthProvider,
    CreateUser,
    CurrentUserOut,
    UpdateUser,
    User,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from tests.support.seeds import CollectionFixtureData

TRACK_ENTRY_AUTHOR = "Track Author"


@dataclass
class UserFixtureData:
    engine: AsyncEngine
    repo: UserRepository
    user: User


@pytest.fixture
async def seeded_user(engine: AsyncEngine, new_user: CreateUser) -> UserFixtureData:
    repo = UserRepository(engine)

    user = await repo.create_user(new_user)

    return UserFixtureData(engine=engine, repo=repo, user=user)


@pytest.fixture
async def get_created_user(seeded_user: UserFixtureData) -> UserFixtureData:
    return seeded_user


@pytest.fixture
def repository(engine: AsyncEngine) -> UserRepository:
    return UserRepository(engine)


class TestUserRepository:
    async def test_create_user_creates_personal_organization_with_member(
        self, repository: UserRepository
    ) -> None:
        user_create = CreateUser(
            email=f"test_{uuid.uuid4()}@example.com",
            full_name="Test User",
            disabled=False,
            email_verified=True,
            auth_method=AuthProvider.EMAIL,
            photo=None,
            hashed_password="hashed_password",
        )

        created_user = await repository.create_user(user_create)
        fetched_user = await repository.get_user(user_create.email)
        assert fetched_user
        fetched_org = (await repository.get_user_organizations(fetched_user.id))[0]
        assert fetched_org
        fetched_org_member = (await repository.get_organization_users(fetched_org.id))[
            0
        ]

        assert fetched_org.name == "Test's organization"
        assert fetched_org_member
        assert fetched_org_member.organization_id == fetched_org.id
        assert created_user == fetched_user

    async def test_delete_signup_removes_user_and_organization(
        self, repository: UserRepository, engine: AsyncEngine
    ) -> None:
        signup, other = (
            CreateUser(
                email=f"test_{uuid.uuid4()}@example.com",
                full_name=full_name,
                disabled=False,
                email_verified=False,
                auth_method=AuthProvider.EMAIL,
                photo=None,
                hashed_password="hashed_password",
            )
            for full_name in ("Signup User", "Other User")
        )
        signup_user = await repository.create_user(signup)
        other_user = await repository.create_user(other)
        signup_org = (await repository.get_user_organizations(signup_user.id))[0]
        other_org = (await repository.get_user_organizations(other_user.id))[0]

        await repository.delete_signup(signup_user.id)

        assert await repository.get_user(signup.email) is None
        assert await repository.get_organization_users(signup_org.id) == []
        async with AsyncSession(engine) as session:
            remaining = set(
                await session.scalars(
                    select(OrganizationOrm.id).where(
                        OrganizationOrm.id.in_([signup_org.id, other_org.id])
                    )
                )
            )
        assert remaining == {other_org.id}
        assert await repository.get_user(other.email) is not None

    async def test_get_user_returns_user(
        self, repository: UserRepository, seeded_user: UserFixtureData
    ) -> None:
        fetched_user = await repository.get_user(seeded_user.user.email)

        assert fetched_user
        assert isinstance(fetched_user, User)

    async def test_get_current_user_returns_user_without_password_hash(
        self, repository: UserRepository, seeded_user: UserFixtureData
    ) -> None:
        fetched_user = await repository.get_current_user(seeded_user.user.email)

        assert fetched_user
        assert isinstance(fetched_user, CurrentUserOut)
        assert fetched_user.auth_method == seeded_user.user.auth_method
        assert fetched_user.id
        assert fetched_user.email
        assert hasattr(fetched_user, "full_name")
        assert hasattr(fetched_user, "disabled")
        assert hasattr(fetched_user, "photo")
        assert not hasattr(fetched_user, "hashed_password")

    async def test_delete_user_removes_user(
        self, repository: UserRepository, seeded_user: UserFixtureData
    ) -> None:
        await repository.delete_user(seeded_user.user.email)
        fetch_deleted_user = await repository.get_user(seeded_user.user.email)

        assert fetch_deleted_user is None

    async def test_delete_user_keeps_track_entry_added_by_user(
        self,
        repository: UserRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        entry_repository = TrackEntryRepository(engine)

        artifact = await ArtifactRepository(engine).create_artifact(
            new_artifact.model_copy(
                update={
                    "collection_id": seeded_collection.collection.id,
                    "status": ArtifactStatus.UPLOADED,
                }
            )
        )
        track = await TrackRepository(engine).create_track(
            TrackCreate(
                orbit_id=seeded_collection.orbit.id,
                name="account-deletion-track",
                artifact_type=artifact.type,
            )
        )
        entry = await entry_repository.create_entry(
            TrackEntryCreate(
                track_id=track.id,
                artifact_id=artifact.id,
                added_by=TRACK_ENTRY_AUTHOR,
            )
        )

        await repository.delete_user(seeded_collection.user.email)

        assert await repository.get_user(seeded_collection.user.email) is None
        persisted_entry = await entry_repository.get_entry(entry.id)
        assert persisted_entry is not None
        assert persisted_entry.added_by == TRACK_ENTRY_AUTHOR

    async def test_update_user_marks_email_verified(
        self, repository: UserRepository, seeded_user: UserFixtureData
    ) -> None:
        user_update_data = UpdateUser(email=seeded_user.user.email, email_verified=True)

        await repository.update_user(user_update_data)
        fetched_user = await repository.get_user(user_update_data.email)

        assert fetched_user
        assert fetched_user.email == user_update_data.email
        assert fetched_user.email_verified == user_update_data.email_verified

    async def test_update_user_returns_false_when_user_not_found(
        self, repository: UserRepository, seeded_user: UserFixtureData
    ) -> None:
        user_update_data = {"email": "test@example.com", "email_verified": True}

        updated_user = await repository.update_user(
            UpdateUser.model_validate(user_update_data)
        )

        assert updated_user is False
