import asyncio
import uuid
from unittest.mock import patch

import pytest
from luml.infra.exceptions import AccountDeleteError
from luml.models import (
    ArtifactOrm,
    BucketSecretOrm,
    CollectionOrm,
    DeploymentOrm,
    OrbitMembersOrm,
    OrbitOrm,
    OrganizationMemberOrm,
    OrganizationOrm,
    SatelliteOrm,
    TrackArtifactOrm,
    TrackOrm,
    UserOrm,
)
from luml.repositories.bucket_secrets import BucketSecretRepository
from luml.repositories.tracks import TrackEntryRepository, TrackRepository
from luml.repositories.users import UserRepository
from luml.schemas.bucket_secrets import S3BucketSecretCreate
from luml.schemas.organization import (
    OrganizationMemberCreate,
    OrgRole,
)
from luml.schemas.tracks import TrackCreate, TrackEntryCreate
from luml.schemas.user import CreateUser
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from tests.support.seeds import SatelliteFixtureData


async def test_delete_account_removes_last_member_organizations_and_all_data(
    engine: AsyncEngine, seeded_satellite: SatelliteFixtureData
) -> None:
    data = seeded_satellite
    repository = UserRepository(engine)
    await BucketSecretRepository(engine).create_bucket_secret(
        S3BucketSecretCreate(
            organization_id=data.organization.id,
            endpoint="s3",
            bucket_name="encrypted-credentials",
            region="us-east-1",
            access_key="test-access-key",
            secret_key="test-secret-key",
        )
    )
    track = await TrackRepository(engine).create_track(
        TrackCreate(
            orbit_id=data.orbit.id,
            name="personal-track",
            artifact_type=data.model.type,
        )
    )
    await TrackEntryRepository(engine).create_entry(
        TrackEntryCreate(
            track_id=track.id, artifact_id=data.model.id, added_by="Deleted User"
        )
    )
    async with AsyncSession(engine) as session, session.begin():
        session.add(
            DeploymentOrm(
                orbit_id=data.orbit.id,
                satellite_id=data.satellite.id,
                artifact_id=data.model.id,
                name="personal-deployment",
            )
        )

    await repository.delete_user(data.user.email)

    async with AsyncSession(engine) as session:
        for model in (
            UserOrm,
            OrganizationOrm,
            OrganizationMemberOrm,
            OrbitMembersOrm,
            OrbitOrm,
            CollectionOrm,
            ArtifactOrm,
            TrackOrm,
            TrackArtifactOrm,
            SatelliteOrm,
            DeploymentOrm,
            BucketSecretOrm,
        ):
            assert await session.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.parametrize("role", [OrgRole.OWNER, OrgRole.ADMIN, OrgRole.MEMBER])
async def test_delete_account_preserves_shared_organization_with_another_owner(
    engine: AsyncEngine, new_user: CreateUser, role: OrgRole
) -> None:
    repository = UserRepository(engine)
    owner = await repository.create_user(new_user)
    departing = await repository.create_user(
        new_user.model_copy(update={"email": f"departing_{uuid.uuid4()}@example.com"})
    )
    organization = (await repository.get_user_organizations(owner.id))[0]
    if role == OrgRole.OWNER:
        await repository.create_owner(departing.id, organization.id)
    else:
        await repository.create_organization_member(
            OrganizationMemberCreate(
                user_id=departing.id, organization_id=organization.id, role=role
            )
        )

    await repository.delete_user(departing.email)

    assert await repository.get_user(departing.email) is None
    members = await repository.get_organization_members(organization.id)
    assert [(member.user.id, member.role) for member in members] == [
        (owner.id, OrgRole.OWNER)
    ]
    assert len(await repository.get_user_organizations(owner.id)) == 1


@pytest.mark.parametrize("successor_role", [OrgRole.MEMBER, OrgRole.ADMIN])
async def test_delete_account_transfers_shared_ownership(
    engine: AsyncEngine, new_user: CreateUser, successor_role: OrgRole
) -> None:
    repository = UserRepository(engine)
    owner = await repository.create_user(new_user)
    successor = await repository.create_user(
        new_user.model_copy(update={"email": f"successor_{uuid.uuid4()}@example.com"})
    )
    organization = (await repository.get_user_organizations(owner.id))[0]
    await repository.create_organization_member(
        OrganizationMemberCreate(
            user_id=successor.id,
            organization_id=organization.id,
            role=successor_role,
        )
    )

    await repository.delete_user(owner.email)

    assert await repository.get_user(owner.email) is None
    members = await repository.get_organization_members(organization.id)
    assert [(member.user.id, member.role) for member in members] == [
        (successor.id, OrgRole.OWNER)
    ]


async def test_delete_account_rolls_back_cleanup_and_transfer_on_failure(
    engine: AsyncEngine, new_user: CreateUser
) -> None:
    repository = UserRepository(engine)
    user = await repository.create_user(new_user)
    organization = (await repository.get_user_organizations(user.id))[0]
    successor = await repository.create_user(
        new_user.model_copy(update={"email": f"successor_{uuid.uuid4()}@example.com"})
    )
    shared = (await repository.get_user_organizations(successor.id))[0]
    await repository.create_owner(user.id, shared.id)
    async with AsyncSession(engine) as session, session.begin():
        member = await session.scalar(
            select(OrganizationMemberOrm).where(
                OrganizationMemberOrm.user_id == successor.id,
                OrganizationMemberOrm.organization_id == shared.id,
            )
        )
        assert member is not None
        member.role = OrgRole.MEMBER

    with (
        patch("luml.repositories.users.delete", side_effect=RuntimeError("failed")),
        pytest.raises(RuntimeError, match="failed"),
    ):
        await repository.delete_user(user.email)

    assert await repository.get_user(user.email) is not None
    assert {org.id for org in await repository.get_user_organizations(user.id)} == {
        organization.id,
        shared.id,
    }
    assert (
        await repository.get_organization_member_role(shared.id, successor.id)
        == OrgRole.MEMBER
    )


@pytest.mark.parametrize("later_role", [OrgRole.MEMBER, OrgRole.ADMIN])
async def test_delete_account_prefers_admin_then_oldest_member(
    engine: AsyncEngine, new_user: CreateUser, later_role: OrgRole
) -> None:
    repository = UserRepository(engine)
    owner = await repository.create_user(new_user)
    organization = (await repository.get_user_organizations(owner.id))[0]
    members = []
    for role in (OrgRole.MEMBER, later_role):
        user = await repository.create_user(
            new_user.model_copy(update={"email": f"member_{uuid.uuid4()}@example.com"})
        )
        members.append(
            await repository.create_organization_member(
                OrganizationMemberCreate(
                    user_id=user.id, organization_id=organization.id, role=role
                )
            )
        )

    await repository.delete_user(owner.email)

    expected = members[1] if later_role == OrgRole.ADMIN else members[0]
    remaining = await repository.get_organization_members(organization.id)
    assert [member.id for member in remaining if member.role == OrgRole.OWNER] == [
        expected.id
    ]


async def test_delete_account_refuses_new_membership_during_cleanup(
    engine: AsyncEngine, new_user: CreateUser
) -> None:
    repository = UserRepository(engine)
    user = await repository.create_user(new_user)
    original = (await repository.get_user_organizations(user.id))[0]
    async with AsyncSession(engine) as session, session.begin():
        await session.scalar(
            select(UserOrm.id).where(UserOrm.id == user.id).with_for_update()
        )
        task = asyncio.create_task(repository.delete_user(user.email))
        try:
            async with asyncio.timeout(10):
                while not await session.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE datname = current_database() "
                        "AND pid <> pg_backend_pid() AND wait_event_type = 'Lock'"
                    )
                ):
                    await session.execute(text("SELECT pg_stat_clear_snapshot()"))
                    await asyncio.sleep(0.02)
            added = OrganizationOrm(name="concurrent organization")
            session.add(added)
            await session.flush()
            added_id = added.id
            session.add(
                OrganizationMemberOrm(
                    organization_id=added.id, user_id=user.id, role=OrgRole.OWNER
                )
            )
            await session.commit()
            with pytest.raises(AccountDeleteError, match="retry"):
                await task
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    assert await repository.get_user(user.email) is not None
    assert {org.id for org in await repository.get_user_organizations(user.id)} == {
        original.id,
        added_id,
    }


async def test_delete_missing_account_is_a_noop(engine: AsyncEngine) -> None:
    await UserRepository(engine).delete_user("missing@example.com")


async def test_concurrent_owner_account_deletions_keep_an_owner(
    engine: AsyncEngine, new_user: CreateUser
) -> None:
    repository = UserRepository(engine)
    owner = await repository.create_user(new_user)
    other = await repository.create_user(
        new_user.model_copy(update={"email": f"other_{uuid.uuid4()}@example.com"})
    )
    organization = (await repository.get_user_organizations(owner.id))[0]
    await repository.create_owner(other.id, organization.id)

    async with asyncio.timeout(10):
        results = await asyncio.gather(
            repository.delete_user(owner.email),
            repository.delete_user(other.email),
            return_exceptions=True,
        )

    assert all(result is None for result in results), results
    async with AsyncSession(engine) as session:
        assert await session.get(OrganizationOrm, organization.id) is None
        assert await session.scalar(select(func.count()).select_from(UserOrm)) == 0
