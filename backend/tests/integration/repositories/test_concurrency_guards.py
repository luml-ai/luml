import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any
from uuid import UUID

import pytest
from luml.infra.exceptions import (
    ApplicationError,
    ArtifactBeingDeletedError,
    ArtifactDeployedError,
    ArtifactNotFoundError,
    ArtifactStatusMismatchError,
    ArtifactTrackedError,
    CollectionDeleteError,
    CollectionNotFoundError,
    NotFoundError,
    OrbitSecretInUseError,
    OrganizationDeleteError,
    OrganizationInviteAlreadyExistsError,
    OrganizationLimitReachedError,
)
from luml.models import (
    ArtifactOrm,
    CollectionOrm,
    DeploymentOrm,
    OrbitSecretOrm,
    OrganizationOrm,
    TokenBlackListOrm,
    TrackOrm,
)
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.collections import CollectionRepository
from luml.repositories.deployments import DeploymentRepository
from luml.repositories.invites import InviteRepository
from luml.repositories.lineage import LineageRepository
from luml.repositories.orbit_secrets import OrbitSecretRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.satellites import SatelliteRepository
from luml.repositories.token_blacklist import TokenBlackListRepository
from luml.repositories.tracks import (
    TrackEntryRepository,
    TrackRepository,
    TrackStageRepository,
)
from luml.repositories.users import UserRepository
from luml.schemas.artifacts import (
    Artifact,
    ArtifactCreate,
    ArtifactStatus,
    ArtifactType,
)
from luml.schemas.deployment import DeploymentCreate, DeploymentStatus
from luml.schemas.orbit import OrbitCreateIn, OrbitDetails
from luml.schemas.orbit_secret import OrbitSecretCreate
from luml.schemas.organization import (
    CreateOrganizationInvite,
    OrganizationCreateIn,
    OrganizationMember,
    OrganizationMemberCreate,
    OrgRole,
)
from luml.schemas.satellite import Satellite, SatelliteCreate
from luml.schemas.tracks import (
    StageCreate,
    StageUpsertIn,
    TrackCreate,
    TrackEntryCreate,
    TrackEntryUpdate,
)
from luml.schemas.user import CreateUser, User
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
)

from tests.support.builders import create_artifact
from tests.support.seeds import (
    CollectionFixtureData,
    OrganizationFixtureData,
    SatelliteFixtureData,
)


async def _race(*calls: Awaitable[Any]) -> list[Any]:
    return list(await asyncio.gather(*calls, return_exceptions=True))


def _split(
    results: list[Any], error: type[BaseException]
) -> tuple[list[Any], list[BaseException]]:
    winners = [r for r in results if not isinstance(r, BaseException)]
    losers = [r for r in results if isinstance(r, error)]
    unexpected = [r for r in results if isinstance(r, BaseException)]
    unexpected = [r for r in unexpected if not isinstance(r, error)]
    assert not unexpected, unexpected
    return winners, losers


async def _wait_for_lock_waiters(session: AsyncSession, count: int) -> None:
    deadline = time.monotonic() + 10
    while True:
        await session.execute(text("SELECT pg_stat_clear_snapshot()"))
        waiting = await session.scalar(
            text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE datname = current_database() "
                "AND pid <> pg_backend_pid() AND wait_event_type = 'Lock'"
            )
        )
        if waiting >= count:
            return
        assert time.monotonic() < deadline, (
            f"expected {count} backends waiting on a lock, saw {waiting}"
        )
        await asyncio.sleep(0.02)


async def _blacklist_expiry(engine: AsyncEngine, token: str) -> list[int]:
    async with AsyncSession(engine) as session:
        return list(
            await session.scalars(
                select(TokenBlackListOrm.expire_at).where(
                    TokenBlackListOrm.token == token
                )
            )
        )


async def _set_limit(engine: AsyncEngine, organization_id: UUID, **limits: int) -> None:
    async with AsyncSession(engine) as session:
        await session.execute(
            update(OrganizationOrm)
            .where(OrganizationOrm.id == organization_id)
            .values(**limits)
        )
        await session.commit()


async def _artifacts(
    engine: AsyncEngine, template: ArtifactCreate, collection_id: UUID, count: int
) -> list[Artifact]:
    return [
        await create_artifact(
            engine, template, collection_id, name=template.name, status=template.status
        )
        for _ in range(count)
    ]


async def _delete_artifact(
    engine: AsyncEngine, orbit_id: UUID, artifact_id: UUID
) -> None:
    lineage = LineageRepository(engine)
    artifacts = ArtifactRepository(engine)
    async with lineage.transaction() as session:
        await lineage.lock_orbit(orbit_id, session)
        await lineage.refresh_node_copy(artifact_id, session)
        await artifacts.delete_artifact(artifact_id, session)
        await lineage.delete_unreachable_deleted_nodes(orbit_id, session)


class TestConcurrencyGuards:
    async def test_request_deletion_marks_unreferenced_artifact_pending_deletion(
        self,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        artifact_repository = ArtifactRepository(engine)
        artifact = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name=new_artifact.name,
            status=new_artifact.status,
        )

        moved = await artifact_repository.request_deletion(
            artifact.id, seeded_collection.collection.id
        )

        assert moved is not None
        assert moved.status == ArtifactStatus.PENDING_DELETION
        stored = await artifact_repository.get_artifact(artifact.id)
        assert stored is not None
        assert stored.status == ArtifactStatus.PENDING_DELETION
        assert (
            await artifact_repository.request_deletion(
                uuid.uuid4(), seeded_collection.collection.id
            )
            is None
        )
        assert (
            await artifact_repository.request_deletion(artifact.id, uuid.uuid4())
            is None
        )

    async def test_request_deletion_raises_for_deployments_then_tracks(
        self, engine: AsyncEngine, seeded_satellite: SatelliteFixtureData
    ) -> None:
        artifact_repository = ArtifactRepository(engine)
        deployment_repository = DeploymentRepository(engine)
        deployment, _ = await deployment_repository.create_deployment(
            DeploymentCreate(
                name="held",
                orbit_id=seeded_satellite.orbit.id,
                satellite_id=seeded_satellite.satellite.id,
                artifact_id=seeded_satellite.model.id,
                status=DeploymentStatus.PENDING,
            )
        )

        with pytest.raises(ArtifactDeployedError, match="used in deployments"):
            await artifact_repository.request_deletion(
                seeded_satellite.model.id, seeded_satellite.model.collection_id
            )

        await deployment_repository.delete_deployment(
            deployment.id, seeded_satellite.orbit.id
        )
        track = await TrackRepository(engine).create_track(
            TrackCreate(
                orbit_id=seeded_satellite.orbit.id,
                name="t",
                artifact_type=ArtifactType.MODEL,
            )
        )
        await TrackEntryRepository(engine).create_entry(
            TrackEntryCreate(
                track_id=track.id,
                artifact_id=seeded_satellite.model.id,
                added_by=seeded_satellite.user.email,
            )
        )

        with pytest.raises(ArtifactTrackedError, match="referenced by one or more"):
            await artifact_repository.request_deletion(
                seeded_satellite.model.id, seeded_satellite.model.collection_id
            )
        stored = await artifact_repository.get_artifact(seeded_satellite.model.id)
        assert stored is not None
        assert stored.status == seeded_satellite.model.status

    async def test_update_entry_keeps_one_stage_holder_when_assignments_race(
        self,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        artifacts = await _artifacts(
            engine, new_artifact, seeded_collection.collection.id, 2
        )
        track = await TrackRepository(engine).create_track(
            TrackCreate(
                orbit_id=seeded_collection.orbit.id,
                name="t",
                artifact_type=ArtifactType.MODEL,
            )
        )
        stage = await TrackStageRepository(engine).create_stage(
            StageCreate(track_id=track.id, name="Production")
        )
        entries = TrackEntryRepository(engine)
        first, second = [
            await entries.create_entry(
                TrackEntryCreate(
                    track_id=track.id,
                    artifact_id=a.id,
                    added_by=seeded_collection.user.email,
                )
            )
            for a in artifacts
        ]

        results = await _race(
            entries.update_entry(first.id, TrackEntryUpdate(stage_id=stage.id)),
            entries.update_entry(second.id, TrackEntryUpdate(stage_id=stage.id)),
        )

        winners, losers = _split(results, IntegrityError)
        assert len(winners) == 1
        assert len(losers) == 1
        holder = await entries.get_entry_by_stage(track.id, stage.id)
        assert holder is not None
        assert holder.id == winners[0].id

    async def test_update_entry_keeps_one_stage_holder_when_forced_reassignments_race(
        self,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        artifacts = await _artifacts(
            engine, new_artifact, seeded_collection.collection.id, 3
        )
        track = await TrackRepository(engine).create_track(
            TrackCreate(
                orbit_id=seeded_collection.orbit.id,
                name="t",
                artifact_type=ArtifactType.MODEL,
            )
        )
        stage = await TrackStageRepository(engine).create_stage(
            StageCreate(track_id=track.id, name="Production")
        )
        entries = TrackEntryRepository(engine)
        holder, b, c = [
            await entries.create_entry(
                TrackEntryCreate(
                    track_id=track.id,
                    artifact_id=a.id,
                    added_by=seeded_collection.user.email,
                )
            )
            for a in artifacts
        ]
        await entries.update_entry(holder.id, TrackEntryUpdate(stage_id=stage.id))

        results = await _race(
            entries.update_entry(b.id, TrackEntryUpdate(stage_id=stage.id), force=True),
            entries.update_entry(c.id, TrackEntryUpdate(stage_id=stage.id), force=True),
        )

        winners, losers = _split(results, IntegrityError)
        assert len(winners) == 1
        assert len(losers) == 1
        current = await entries.get_entry_by_stage(track.id, stage.id)
        assert current is not None
        assert current.id == winners[0].id
        previous = await entries.get_entry(holder.id)
        assert previous is not None
        assert previous.stage_id is None

    async def test_delete_stage_raises_when_assigned_unless_unassigning(
        self,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        (artifact,) = await _artifacts(
            engine, new_artifact, seeded_collection.collection.id, 1
        )
        track = await TrackRepository(engine).create_track(
            TrackCreate(
                orbit_id=seeded_collection.orbit.id,
                name="t",
                artifact_type=ArtifactType.MODEL,
            )
        )
        stages = TrackStageRepository(engine)
        stage = await stages.create_stage(StageCreate(track_id=track.id, name="Prod"))
        entries = TrackEntryRepository(engine)
        entry = await entries.create_entry(
            TrackEntryCreate(
                track_id=track.id,
                artifact_id=artifact.id,
                added_by=seeded_collection.user.email,
                stage_id=stage.id,
            )
        )

        with pytest.raises(ApplicationError, match="currently assigned") as refused:
            await stages.delete_stage(stage.id)
        assert refused.value.status_code == 409
        assert await stages.get_stage(stage.id) is not None

        await stages.delete_stage(stage.id, unassign=True)

        assert await stages.get_stage(stage.id) is None
        stored = await entries.get_entry(entry.id)
        assert stored is not None
        assert stored.stage_id is None

    async def test_sync_stages_keeps_one_stage_set_when_replacements_race(
        self, engine: AsyncEngine, seeded_collection: CollectionFixtureData
    ) -> None:
        track = await TrackRepository(engine).create_track(
            TrackCreate(
                orbit_id=seeded_collection.orbit.id,
                name="t",
                artifact_type=ArtifactType.MODEL,
            )
        )
        stages = TrackStageRepository(engine)
        left = [StageUpsertIn(name="dev"), StageUpsertIn(name="staging")]
        right = [StageUpsertIn(name="qa"), StageUpsertIn(name="prod")]

        async with AsyncSession(engine) as session:
            await session.execute(
                select(TrackOrm.id).where(TrackOrm.id == track.id).with_for_update()
            )
            first = asyncio.create_task(stages.sync_stages(track.id, left))
            second = asyncio.create_task(stages.sync_stages(track.id, right))
            await _wait_for_lock_waiters(session, 2)
            await session.commit()

        assert await _race(first, second) == [None, None]
        names = {stage.name for stage in await stages.list_stages(track.id)}
        assert names in ({"dev", "staging"}, {"qa", "prod"})

        with pytest.raises(ApplicationError, match="Track not found"):
            await stages.sync_stages(uuid.uuid4(), left)

    async def test_add_token_returns_false_for_second_concurrent_attempt(
        self, engine: AsyncEngine
    ) -> None:
        blacklist_repository = TokenBlackListRepository(engine)
        token = f"refresh-{uuid.uuid4()}"
        expire = int(time.time()) + 60

        results = await _race(
            blacklist_repository.add_token(token, expire),
            blacklist_repository.add_token(token, expire),
        )

        assert sorted(results) == [False, True]
        assert await blacklist_repository.add_token(token, expire) is False
        assert await blacklist_repository.is_token_blacklisted(token) is True

    async def test_add_token_propagates_integrity_error_other_than_duplicate(
        self, engine: AsyncEngine
    ) -> None:
        blacklist_repository = TokenBlackListRepository(engine)
        token = f"refresh-{uuid.uuid4()}"

        with pytest.raises(IntegrityError):
            await blacklist_repository.add_token(token, None)  # type: ignore[arg-type]
        assert await blacklist_repository.is_token_blacklisted(token) is False

    async def test_delete_collection_raises_when_artifacts_exist_or_returns_false(
        self,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        collection_repository = CollectionRepository(engine)
        await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name=new_artifact.name,
            status=new_artifact.status,
        )

        with pytest.raises(CollectionDeleteError, match="has artifacts"):
            await collection_repository.delete_collection(
                seeded_collection.collection.id, seeded_collection.orbit.id
            )
        assert (
            await collection_repository.get_collection(seeded_collection.collection.id)
            is not None
        )
        assert (
            await collection_repository.delete_collection(
                uuid.uuid4(), seeded_collection.orbit.id
            )
            is False
        )

    async def test_create_artifact_raises_when_collection_deleted_while_waiting(
        self,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        async with AsyncSession(engine) as session:
            collection = (
                await session.execute(
                    select(CollectionOrm)
                    .where(CollectionOrm.id == seeded_collection.collection.id)
                    .with_for_update()
                )
            ).scalar_one()
            upload = asyncio.create_task(
                create_artifact(
                    engine,
                    new_artifact,
                    seeded_collection.collection.id,
                    name=new_artifact.name,
                    status=new_artifact.status,
                )
            )
            await _wait_for_lock_waiters(session, 1)
            assert not upload.done(), "the upload must wait on the collection row"
            await session.delete(collection)
            await session.commit()

        with pytest.raises(CollectionNotFoundError):
            await upload
        assert (
            await CollectionRepository(engine).get_collection(
                seeded_collection.collection.id
            )
            is None
        )

    async def test_create_artifact_enforces_quota_when_creations_race(
        self,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        await _set_limit(engine, seeded_collection.organization.id, artifacts_limit=1)

        results = await _race(
            create_artifact(
                engine,
                new_artifact,
                seeded_collection.collection.id,
                name=new_artifact.name,
                status=new_artifact.status,
            ),
            create_artifact(
                engine,
                new_artifact,
                seeded_collection.collection.id,
                name=new_artifact.name,
                status=new_artifact.status,
            ),
        )

        winners, losers = _split(results, OrganizationLimitReachedError)
        assert len(winners) == 1
        assert len(losers) == 1
        assert "maximum number of artifacts" in str(losers[0])
        assert (
            await ArtifactRepository(engine).get_collection_artifacts_count(
                seeded_collection.collection.id
            )
            == 1
        )

    async def test_create_orbit_enforces_quota_when_creations_race(
        self, engine: AsyncEngine, seeded_organization: OrganizationFixtureData
    ) -> None:
        orbit_repository = OrbitRepository(engine)
        await _set_limit(engine, seeded_organization.organization.id, orbits_limit=1)

        async def make(name: str) -> OrbitDetails | None:
            return await orbit_repository.create_orbit(
                seeded_organization.organization.id,
                OrbitCreateIn(
                    name=name, bucket_secret_id=seeded_organization.bucket_secret.id
                ),
            )

        winners, losers = _split(
            await _race(make("first"), make("second")), OrganizationLimitReachedError
        )

        assert len(winners) == 1
        assert len(losers) == 1
        assert "maximum number of orbits" in str(losers[0])

    async def test_create_satellite_enforces_quota_when_creations_race(
        self, engine: AsyncEngine, seeded_collection: CollectionFixtureData
    ) -> None:
        satellite_repository = SatelliteRepository(engine)
        await _set_limit(engine, seeded_collection.organization.id, satellites_limit=1)

        async def make(name: str) -> Satellite:
            return await satellite_repository.create_satellite(
                SatelliteCreate(
                    orbit_id=seeded_collection.orbit.id,
                    api_key_hash=str(uuid.uuid4()),
                    name=name,
                )
            )

        winners, losers = _split(
            await _race(make("first"), make("second")), OrganizationLimitReachedError
        )

        assert len(winners) == 1
        assert len(losers) == 1
        assert "maximum number of satellites" in str(losers[0])

    async def test_create_organization_member_enforces_quotas_when_additions_race(
        self,
        engine: AsyncEngine,
        seeded_organization: OrganizationFixtureData,
        new_user: CreateUser,
    ) -> None:
        user_repository = UserRepository(engine)
        joiners = [
            await user_repository.create_user(
                new_user.model_copy(
                    update={"email": f"joiner-{index}-{uuid.uuid4().hex}@example.com"}
                )
            )
            for index in range(2)
        ]
        assert all(joiners)
        await _set_limit(engine, seeded_organization.organization.id, members_limit=2)

        async def make(joiner: User) -> OrganizationMember:
            return await user_repository.create_organization_member(
                OrganizationMemberCreate(
                    user_id=joiner.id,
                    organization_id=seeded_organization.organization.id,
                    role=OrgRole.MEMBER,
                )
            )

        winners, losers = _split(
            await _race(make(joiners[0]), make(joiners[1])),
            OrganizationLimitReachedError,
        )

        assert len(winners) == 1
        assert len(losers) == 1
        assert "maximum number of users" in str(losers[0])

        current = await user_repository.get_user_organizations_membership_count(
            seeded_organization.user.id
        )
        with pytest.raises(
            OrganizationLimitReachedError, match="limit of organizations"
        ):
            await user_repository.create_organization(
                seeded_organization.user.id,
                OrganizationCreateIn(name="second"),
                membership_limit=current,
            )
        second = await user_repository.create_organization(
            seeded_organization.user.id,
            OrganizationCreateIn(name="second"),
            membership_limit=current + 1,
        )
        assert (
            await user_repository.get_organization_member(
                second.id, seeded_organization.user.id
            )
            is not None
        )

    async def test_create_organization_invite_raises_when_duplicate_invites_race(
        self, engine: AsyncEngine, seeded_organization: OrganizationFixtureData
    ) -> None:
        invite_repository = InviteRepository(engine)
        invite = CreateOrganizationInvite(
            email="new@example.com",
            role=OrgRole.MEMBER,
            organization_id=seeded_organization.organization.id,
            invited_by=seeded_organization.user.id,
        )

        winners, losers = _split(
            await _race(
                invite_repository.create_organization_invite(invite),
                invite_repository.create_organization_invite(invite),
            ),
            OrganizationInviteAlreadyExistsError,
        )

        assert len(winners) == 1
        assert len(losers) == 1
        assert (
            len(
                await invite_repository.get_invites_by_organization_id(
                    seeded_organization.organization.id
                )
            )
            == 1
        )

    async def test_delete_organization_raises_when_members_exist_or_returns_false(
        self,
        engine: AsyncEngine,
        seeded_organization: OrganizationFixtureData,
        new_user: CreateUser,
    ) -> None:
        user_repository = UserRepository(engine)
        joiner = await user_repository.create_user(
            new_user.model_copy(
                update={"email": f"joiner-{uuid.uuid4().hex}@example.com"}
            )
        )
        assert joiner is not None
        member = await user_repository.create_organization_member(
            OrganizationMemberCreate(
                user_id=joiner.id,
                organization_id=seeded_organization.organization.id,
                role=OrgRole.MEMBER,
            )
        )

        with pytest.raises(OrganizationDeleteError, match="has members"):
            await user_repository.delete_organization(
                seeded_organization.organization.id
            )
        assert (
            await user_repository.get_organization_details(
                seeded_organization.organization.id
            )
            is not None
        )

        await user_repository.delete_organization_member(
            seeded_organization.organization.id, member.id
        )
        assert await user_repository.delete_organization(uuid.uuid4()) is False
        assert (
            await user_repository.delete_organization(
                seeded_organization.organization.id
            )
            is True
        )
        assert (
            await user_repository.get_organization_details(
                seeded_organization.organization.id
            )
            is None
        )

    @pytest.mark.parametrize("first", ["deletion", "deployment"])
    async def test_delete_orbit_secret_serializes_with_new_binding(
        self,
        engine: AsyncEngine,
        seeded_satellite: SatelliteFixtureData,
        first: str,
    ) -> None:
        orbit_id = seeded_satellite.orbit.id
        secrets = OrbitSecretRepository(engine)
        deployments = DeploymentRepository(engine)
        secret = await secrets.create_orbit_secret(
            OrbitSecretCreate(name="token", value="secret", orbit_id=orbit_id)
        )
        writers: dict[str, Callable[[], Coroutine[Any, Any, Any]]] = {
            "deletion": lambda: secrets.delete_orbit_secret(secret.id, orbit_id),
            "deployment": lambda: deployments.create_deployment(
                DeploymentCreate(
                    name="late",
                    orbit_id=orbit_id,
                    satellite_id=seeded_satellite.satellite.id,
                    artifact_id=seeded_satellite.model.id,
                    status=DeploymentStatus.PENDING,
                    dynamic_attributes_secrets={"token": str(secret.id)},
                )
            ),
        }
        second = "deployment" if first == "deletion" else "deletion"

        async with AsyncSession(engine) as session:
            await session.execute(
                select(OrbitSecretOrm.id)
                .where(OrbitSecretOrm.id == secret.id)
                .with_for_update()
            )
            tasks = {first: asyncio.create_task(writers[first]())}
            await _wait_for_lock_waiters(session, 1)
            tasks[second] = asyncio.create_task(writers[second]())
            await _wait_for_lock_waiters(session, 2)
            assert not tasks[first].done()
            assert not tasks[second].done()
            await session.commit()

        results = {
            name: (await asyncio.gather(task, return_exceptions=True))[0]
            for name, task in tasks.items()
        }
        stored = await secrets.get_orbit_secret(secret.id, orbit_id)
        bound = await deployments.list_deployments(orbit_id)

        if first == "deletion":
            assert results["deletion"] is True
            assert isinstance(results["deployment"], NotFoundError)
            assert stored is None
            assert bound == []
        else:
            assert not isinstance(results["deployment"], BaseException), results
            assert isinstance(results["deletion"], OrbitSecretInUseError)
            assert stored is not None
            assert [deployment.name for deployment in bound] == ["late"]

    @pytest.mark.parametrize("reference", ["deployment", "entry"])
    @pytest.mark.parametrize("first", ["deletion", "reference"])
    async def test_request_deletion_serializes_with_new_reference(
        self,
        engine: AsyncEngine,
        seeded_satellite: SatelliteFixtureData,
        first: str,
        reference: str,
    ) -> None:
        artifacts = ArtifactRepository(engine)
        deployments = DeploymentRepository(engine)
        entries = TrackEntryRepository(engine)
        track = await TrackRepository(engine).create_track(
            TrackCreate(
                orbit_id=seeded_satellite.orbit.id,
                name="t",
                artifact_type=ArtifactType.MODEL,
            )
        )
        make_reference: dict[str, Callable[[], Coroutine[Any, Any, Any]]] = {
            "deployment": lambda: deployments.create_deployment(
                DeploymentCreate(
                    name="late",
                    orbit_id=seeded_satellite.orbit.id,
                    satellite_id=seeded_satellite.satellite.id,
                    artifact_id=seeded_satellite.model.id,
                    status=DeploymentStatus.PENDING,
                )
            ),
            "entry": lambda: entries.create_entry(
                TrackEntryCreate(
                    track_id=track.id,
                    artifact_id=seeded_satellite.model.id,
                    added_by=seeded_satellite.user.email,
                )
            ),
        }
        writers: dict[str, Callable[[], Coroutine[Any, Any, Any]]] = {
            "deletion": lambda: artifacts.request_deletion(
                seeded_satellite.model.id, seeded_satellite.model.collection_id
            ),
            "reference": make_reference[reference],
        }
        second = "reference" if first == "deletion" else "deletion"

        async with AsyncSession(engine) as session:
            await session.execute(
                select(ArtifactOrm.id)
                .where(ArtifactOrm.id == seeded_satellite.model.id)
                .with_for_update()
            )
            tasks = {first: asyncio.create_task(writers[first]())}
            await _wait_for_lock_waiters(session, 1)
            tasks[second] = asyncio.create_task(writers[second]())
            await _wait_for_lock_waiters(session, 2)
            assert not tasks[first].done()
            assert not tasks[second].done()
            await session.commit()

        results = {
            name: (await asyncio.gather(task, return_exceptions=True))[0]
            for name, task in tasks.items()
        }
        stored = await artifacts.get_artifact(seeded_satellite.model.id)
        assert stored is not None
        async with AsyncSession(engine) as session:
            deployment_count = await session.scalar(
                select(func.count())
                .select_from(DeploymentOrm)
                .where(DeploymentOrm.artifact_id == seeded_satellite.model.id)
            )
        linked = await entries.has_entries_for_artifact(seeded_satellite.model.id)

        if first == "deletion":
            moved = results["deletion"]
            assert isinstance(moved, Artifact)
            assert moved.status == ArtifactStatus.PENDING_DELETION
            refused = results["reference"]
            if reference == "deployment":
                assert isinstance(refused, ArtifactStatusMismatchError)
                assert "pending_deletion" in str(refused)
            else:
                assert isinstance(refused, ArtifactBeingDeletedError)
            assert stored.status == ArtifactStatus.PENDING_DELETION
            assert deployment_count == 0
            assert linked is False
        else:
            assert not isinstance(results["reference"], BaseException), results
            refused = results["deletion"]
            if reference == "deployment":
                assert isinstance(refused, ArtifactDeployedError)
                assert deployment_count == 1
            else:
                assert isinstance(refused, ArtifactTrackedError)
                assert linked is True
            assert stored.status == seeded_satellite.model.status

    @pytest.mark.parametrize("reference", ["deployment", "entry"])
    @pytest.mark.parametrize("first", ["deletion", "reference"])
    async def test_delete_artifact_serializes_with_new_reference(
        self,
        engine: AsyncEngine,
        seeded_satellite: SatelliteFixtureData,
        first: str,
        reference: str,
    ) -> None:
        artifacts = ArtifactRepository(engine)
        deployments = DeploymentRepository(engine)
        entries = TrackEntryRepository(engine)
        track = await TrackRepository(engine).create_track(
            TrackCreate(
                orbit_id=seeded_satellite.orbit.id,
                name="t",
                artifact_type=ArtifactType.MODEL,
            )
        )
        make_reference: dict[str, Callable[[], Coroutine[Any, Any, Any]]] = {
            "deployment": lambda: deployments.create_deployment(
                DeploymentCreate(
                    name="late",
                    orbit_id=seeded_satellite.orbit.id,
                    satellite_id=seeded_satellite.satellite.id,
                    artifact_id=seeded_satellite.model.id,
                    status=DeploymentStatus.PENDING,
                )
            ),
            "entry": lambda: entries.create_entry(
                TrackEntryCreate(
                    track_id=track.id,
                    artifact_id=seeded_satellite.model.id,
                    added_by=seeded_satellite.user.email,
                )
            ),
        }
        writers: dict[str, Callable[[], Coroutine[Any, Any, Any]]] = {
            "deletion": lambda: _delete_artifact(
                engine, seeded_satellite.orbit.id, seeded_satellite.model.id
            ),
            "reference": make_reference[reference],
        }
        second = "reference" if first == "deletion" else "deletion"

        async with AsyncSession(engine) as session:
            await session.execute(
                select(ArtifactOrm.id)
                .where(ArtifactOrm.id == seeded_satellite.model.id)
                .with_for_update()
            )
            tasks = {first: asyncio.create_task(writers[first]())}
            await _wait_for_lock_waiters(session, 1)
            tasks[second] = asyncio.create_task(writers[second]())
            await _wait_for_lock_waiters(session, 2)
            assert not tasks[first].done()
            assert not tasks[second].done()
            await session.commit()

        results = {
            name: (await asyncio.gather(task, return_exceptions=True))[0]
            for name, task in tasks.items()
        }
        stored = await artifacts.get_artifact(seeded_satellite.model.id)
        async with AsyncSession(engine) as session:
            deployment_count = await session.scalar(
                select(func.count())
                .select_from(DeploymentOrm)
                .where(DeploymentOrm.artifact_id == seeded_satellite.model.id)
            )
        linked = await entries.has_entries_for_artifact(seeded_satellite.model.id)

        if first == "deletion":
            assert results["deletion"] is None
            assert stored is None
            assert isinstance(results["reference"], ArtifactNotFoundError)
            assert deployment_count == 0
            assert linked is False
        else:
            assert not isinstance(results["reference"], BaseException), results
            refused = results["deletion"]
            if reference == "deployment":
                assert isinstance(refused, ArtifactDeployedError)
                assert deployment_count == 1
            else:
                assert isinstance(refused, ArtifactTrackedError)
                assert linked is True
            assert stored is not None
            assert stored.status == seeded_satellite.model.status

    async def test_delete_stage_leaves_no_dangling_assignment_when_racing_assignment(
        self,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        artifacts = await _artifacts(
            engine, new_artifact, seeded_collection.collection.id, 3
        )
        track = await TrackRepository(engine).create_track(
            TrackCreate(
                orbit_id=seeded_collection.orbit.id,
                name="t",
                artifact_type=ArtifactType.MODEL,
            )
        )
        stages = TrackStageRepository(engine)
        entries = TrackEntryRepository(engine)

        for artifact in artifacts:
            stage = await stages.create_stage(
                StageCreate(track_id=track.id, name=f"stage-{artifact.id}")
            )
            entry = await entries.create_entry(
                TrackEntryCreate(
                    track_id=track.id,
                    artifact_id=artifact.id,
                    added_by=seeded_collection.user.email,
                )
            )

            deletion, assignment = await _race(
                stages.delete_stage(stage.id, unassign=True),
                entries.update_entry(entry.id, TrackEntryUpdate(stage_id=stage.id)),
            )

            assert deletion is None
            assert not isinstance(assignment, BaseException) or (
                isinstance(assignment, ApplicationError)
                and assignment.status_code == 422
            ), assignment
            assert await stages.get_stage(stage.id) is None
            stored = await entries.get_entry(entry.id)
            assert stored is not None
            assert stored.stage_id is None

    async def test_create_organization_member_enforces_membership_limit_in_race(
        self,
        engine: AsyncEngine,
        seeded_organization: OrganizationFixtureData,
        new_user: CreateUser,
    ) -> None:
        user_repository = UserRepository(engine)
        joiner = await user_repository.create_user(
            new_user.model_copy(
                update={"email": f"joiner-{uuid.uuid4().hex}@example.com"}
            )
        )
        assert joiner is not None
        second = await user_repository.create_organization(
            seeded_organization.user.id,
            OrganizationCreateIn(name="second"),
            membership_limit=10,
        )
        await _set_limit(engine, second.id, members_limit=10)
        already = await user_repository.get_user_organizations_membership_count(
            joiner.id
        )

        async def make(organization_id: UUID, limit: int) -> OrganizationMember:
            return await user_repository.create_organization_member(
                OrganizationMemberCreate(
                    user_id=joiner.id,
                    organization_id=organization_id,
                    role=OrgRole.MEMBER,
                ),
                membership_limit=limit,
            )

        with pytest.raises(
            OrganizationLimitReachedError, match="limit of organizations"
        ):
            await make(seeded_organization.organization.id, already)

        winners, losers = _split(
            await _race(
                make(seeded_organization.organization.id, already + 1),
                make(second.id, already + 1),
            ),
            OrganizationLimitReachedError,
        )
        assert len(winners) == 1
        assert len(losers) == 1
        assert await user_repository.get_user_organizations_membership_count(
            joiner.id
        ) == (already + 1)

    async def test_add_token_keeps_longest_expiry(self, engine: AsyncEngine) -> None:
        blacklist_repository = TokenBlackListRepository(engine)
        token = f"refresh-{uuid.uuid4()}"
        base = int(time.time()) + 3600

        assert await blacklist_repository.add_token(token, base) is True
        assert await blacklist_repository.add_token(token, base + 600) is False
        assert await blacklist_repository.add_token(token, base - 600) is False

        assert await _blacklist_expiry(engine, token) == [base + 600]
