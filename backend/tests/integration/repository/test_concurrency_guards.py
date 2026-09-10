"""Rules that hold under concurrent writers (see SPEC.md, concurrency audit).

Each test either races two repository calls on separate connections or holds
a row lock in a raw session while a repository call is in flight, and asserts
that exactly one writer wins and the loser gets the documented error.
"""

import asyncio
import time
import uuid
from collections.abc import Awaitable
from typing import Any
from uuid import UUID

import pytest
from alembic import command
from luml.infra.exceptions import (
    ApplicationError,
    ArtifactBeingDeletedError,
    ArtifactDeployedError,
    ArtifactStatusMismatchError,
    ArtifactTrackedError,
    CollectionDeleteError,
    CollectionNotFoundError,
    OrganizationDeleteError,
    OrganizationInviteAlreadyExistsError,
    OrganizationLimitReachedError,
)
from luml.models import (
    ArtifactOrm,
    CollectionOrm,
    DeploymentOrm,
    OrganizationOrm,
    TokenBlackListOrm,
)
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.collections import CollectionRepository
from luml.repositories.deployments import DeploymentRepository
from luml.repositories.invites import InviteRepository
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
from luml.schemas.orbit import OrbitCreateIn
from luml.schemas.organization import (
    CreateOrganizationInvite,
    OrganizationCreateIn,
    OrganizationMemberCreate,
    OrgRole,
)
from luml.schemas.satellite import SatelliteCreate
from luml.schemas.tracks import (
    StageCreate,
    TrackCreate,
    TrackEntryCreate,
    TrackEntryUpdate,
)
from luml.schemas.user import CreateUser
from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from utils.db import cfg as alembic_cfg

from tests.conftest import (
    CollectionFixtureData,
    OrganizationFixtureData,
    SatelliteFixtureData,
)


async def _race(*calls: Awaitable[Any]) -> list[Any]:
    return list(await asyncio.gather(*calls, return_exceptions=True))


def _split(results: list[Any], error: type[BaseException]) -> tuple[list, list]:
    winners = [r for r in results if not isinstance(r, BaseException)]
    losers = [r for r in results if isinstance(r, error)]
    unexpected = [r for r in results if isinstance(r, BaseException)]
    unexpected = [r for r in unexpected if not isinstance(r, error)]
    assert not unexpected, unexpected
    return winners, losers


async def _set_limit(engine: AsyncEngine, organization_id: UUID, **limits: int) -> None:
    async with AsyncSession(engine) as session:
        await session.execute(
            update(OrganizationOrm)
            .where(OrganizationOrm.id == organization_id)
            .values(**limits)
        )
        await session.commit()


def _artifact(template: ArtifactCreate, collection_id: UUID) -> ArtifactCreate:
    data = template.model_copy()
    data.collection_id = collection_id
    data.unique_identifier = uuid.uuid4().hex
    data.bucket_location = f"objects/{data.unique_identifier}"
    return data


async def _artifacts(
    repo: ArtifactRepository, template: ArtifactCreate, collection_id: UUID, count: int
) -> list[Artifact]:
    return [
        await repo.create_artifact(_artifact(template, collection_id))
        for _ in range(count)
    ]


class TestConcurrencyGuards:
    # ---------------------------------------------------------------- deletion
    @pytest.mark.asyncio
    async def test_request_deletion_moves_unreferenced_artifact(
        self, create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
    ) -> None:
        data = create_collection
        repo = ArtifactRepository(data.engine)
        artifact = await repo.create_artifact(
            _artifact(test_artifact, data.collection.id)
        )

        moved = await repo.request_deletion(artifact.id, data.collection.id)

        assert moved is not None
        assert moved.status == ArtifactStatus.PENDING_DELETION
        stored = await repo.get_artifact(artifact.id)
        assert stored is not None
        assert stored.status == ArtifactStatus.PENDING_DELETION
        assert await repo.request_deletion(uuid.uuid4(), data.collection.id) is None
        assert await repo.request_deletion(artifact.id, uuid.uuid4()) is None

    @pytest.mark.asyncio
    async def test_request_deletion_reports_deployments_then_tracks(
        self, create_satellite: SatelliteFixtureData
    ) -> None:
        data = create_satellite
        repo = ArtifactRepository(data.engine)
        deployments = DeploymentRepository(data.engine)
        deployment, _ = await deployments.create_deployment(
            DeploymentCreate(
                name="held",
                orbit_id=data.orbit.id,
                satellite_id=data.satellite.id,
                artifact_id=data.model.id,
                status=DeploymentStatus.PENDING,
            )
        )

        with pytest.raises(ArtifactDeployedError, match="used in deployments"):
            await repo.request_deletion(data.model.id, data.model.collection_id)

        await deployments.delete_deployment(deployment.id, data.orbit.id)
        track = await TrackRepository(data.engine).create_track(
            TrackCreate(
                orbit_id=data.orbit.id, name="t", artifact_type=ArtifactType.MODEL
            )
        )
        await TrackEntryRepository(data.engine).create_entry(
            TrackEntryCreate(
                track_id=track.id, artifact_id=data.model.id, added_by=data.user.id
            )
        )

        with pytest.raises(ArtifactTrackedError, match="referenced by one or more"):
            await repo.request_deletion(data.model.id, data.model.collection_id)
        stored = await repo.get_artifact(data.model.id)
        assert stored is not None
        assert stored.status == data.model.status

    # ------------------------------------------------------------------ stages
    @pytest.mark.asyncio
    async def test_stage_holds_at_most_one_entry(
        self, create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
    ) -> None:
        data = create_collection
        artifacts = await _artifacts(
            ArtifactRepository(data.engine), test_artifact, data.collection.id, 2
        )
        track = await TrackRepository(data.engine).create_track(
            TrackCreate(
                orbit_id=data.orbit.id, name="t", artifact_type=ArtifactType.MODEL
            )
        )
        stage = await TrackStageRepository(data.engine).create_stage(
            StageCreate(track_id=track.id, name="Production")
        )
        entries = TrackEntryRepository(data.engine)
        first, second = [
            await entries.create_entry(
                TrackEntryCreate(
                    track_id=track.id, artifact_id=a.id, added_by=data.user.id
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

    @pytest.mark.asyncio
    async def test_forced_reassignments_race_to_one_holder(
        self, create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
    ) -> None:
        data = create_collection
        artifacts = await _artifacts(
            ArtifactRepository(data.engine), test_artifact, data.collection.id, 3
        )
        track = await TrackRepository(data.engine).create_track(
            TrackCreate(
                orbit_id=data.orbit.id, name="t", artifact_type=ArtifactType.MODEL
            )
        )
        stage = await TrackStageRepository(data.engine).create_stage(
            StageCreate(track_id=track.id, name="Production")
        )
        entries = TrackEntryRepository(data.engine)
        holder, b, c = [
            await entries.create_entry(
                TrackEntryCreate(
                    track_id=track.id, artifact_id=a.id, added_by=data.user.id
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

    @pytest.mark.asyncio
    async def test_stage_deletion_refuses_assigned_stage_unless_unassigning(
        self, create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
    ) -> None:
        data = create_collection
        (artifact,) = await _artifacts(
            ArtifactRepository(data.engine), test_artifact, data.collection.id, 1
        )
        track = await TrackRepository(data.engine).create_track(
            TrackCreate(
                orbit_id=data.orbit.id, name="t", artifact_type=ArtifactType.MODEL
            )
        )
        stages = TrackStageRepository(data.engine)
        stage = await stages.create_stage(StageCreate(track_id=track.id, name="Prod"))
        entries = TrackEntryRepository(data.engine)
        entry = await entries.create_entry(
            TrackEntryCreate(
                track_id=track.id,
                artifact_id=artifact.id,
                added_by=data.user.id,
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

    # ---------------------------------------------------------- refresh tokens
    @pytest.mark.asyncio
    async def test_blacklisting_a_token_twice_reports_the_second_attempt(
        self, create_database_and_apply_migrations: str
    ) -> None:
        from sqlalchemy.ext.asyncio import create_async_engine

        repo = TokenBlackListRepository(
            create_async_engine(create_database_and_apply_migrations)
        )
        token = f"refresh-{uuid.uuid4()}"
        expire = int(time.time()) + 60

        results = await _race(
            repo.add_token(token, expire), repo.add_token(token, expire)
        )

        assert sorted(results) == [False, True]
        assert await repo.add_token(token, expire) is False
        assert await repo.is_token_blacklisted(token) is True

    # ---------------------------------------------------------- collections
    @pytest.mark.asyncio
    async def test_collection_deletion_refuses_artifacts_and_reports_missing(
        self, create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
    ) -> None:
        data = create_collection
        collections = CollectionRepository(data.engine)
        await ArtifactRepository(data.engine).create_artifact(
            _artifact(test_artifact, data.collection.id)
        )

        with pytest.raises(CollectionDeleteError, match="has artifacts"):
            await collections.delete_collection(data.collection.id, data.orbit.id)
        assert await collections.get_collection(data.collection.id) is not None
        assert await collections.delete_collection(uuid.uuid4(), data.orbit.id) is False

    @pytest.mark.asyncio
    async def test_upload_waits_for_collection_deletion_and_then_fails(
        self, create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
    ) -> None:
        data = create_collection
        artifacts = ArtifactRepository(data.engine)

        async with AsyncSession(data.engine) as session:
            collection = (
                await session.execute(
                    select(CollectionOrm)
                    .where(CollectionOrm.id == data.collection.id)
                    .with_for_update()
                )
            ).scalar_one()
            upload = asyncio.create_task(
                artifacts.create_artifact(_artifact(test_artifact, data.collection.id))
            )
            await asyncio.sleep(0.5)
            assert not upload.done(), "the upload must wait on the collection row"
            await session.delete(collection)
            await session.commit()

        with pytest.raises(CollectionNotFoundError):
            await upload
        assert (
            await CollectionRepository(data.engine).get_collection(data.collection.id)
            is None
        )

    # ---------------------------------------------------------------- quotas
    @pytest.mark.asyncio
    async def test_artifact_quota_holds_under_concurrency(
        self, create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
    ) -> None:
        data = create_collection
        repo = ArtifactRepository(data.engine)
        await _set_limit(data.engine, data.organization.id, artifacts_limit=1)

        results = await _race(
            repo.create_artifact(_artifact(test_artifact, data.collection.id)),
            repo.create_artifact(_artifact(test_artifact, data.collection.id)),
        )

        winners, losers = _split(results, OrganizationLimitReachedError)
        assert len(winners) == 1
        assert len(losers) == 1
        assert "maximum number of artifacts" in str(losers[0])
        assert await repo.get_collection_artifacts_count(data.collection.id) == 1

    @pytest.mark.asyncio
    async def test_orbit_quota_holds_under_concurrency(
        self, create_organization_with_user: OrganizationFixtureData
    ) -> None:
        data = create_organization_with_user
        repo = OrbitRepository(data.engine)
        await _set_limit(data.engine, data.organization.id, orbits_limit=1)
        make = lambda name: repo.create_orbit(  # noqa: E731
            data.organization.id,
            OrbitCreateIn(name=name, bucket_secret_id=data.bucket_secret.id),
        )

        winners, losers = _split(
            await _race(make("first"), make("second")), OrganizationLimitReachedError
        )

        assert len(winners) == 1
        assert len(losers) == 1
        assert "maximum number of orbits" in str(losers[0])

    @pytest.mark.asyncio
    async def test_satellite_quota_holds_under_concurrency(
        self, create_collection: CollectionFixtureData
    ) -> None:
        data = create_collection
        repo = SatelliteRepository(data.engine)
        await _set_limit(data.engine, data.organization.id, satellites_limit=1)
        make = lambda name: repo.create_satellite(  # noqa: E731
            SatelliteCreate(
                orbit_id=data.orbit.id, api_key_hash=str(uuid.uuid4()), name=name
            )
        )

        winners, losers = _split(
            await _race(make("first"), make("second")), OrganizationLimitReachedError
        )

        assert len(winners) == 1
        assert len(losers) == 1
        assert "maximum number of satellites" in str(losers[0])

    @pytest.mark.asyncio
    async def test_member_quotas_hold_under_concurrency(
        self,
        create_organization_with_user: OrganizationFixtureData,
        test_user_create: CreateUser,
    ) -> None:
        data = create_organization_with_user
        repo = UserRepository(data.engine)
        joiners = [
            await repo.create_user(
                test_user_create.model_copy(
                    update={"email": f"joiner-{index}-{uuid.uuid4().hex}@example.com"}
                )
            )
            for index in range(2)
        ]
        assert all(joiners)
        await _set_limit(data.engine, data.organization.id, members_limit=2)
        make = lambda user: repo.create_organization_member(  # noqa: E731
            OrganizationMemberCreate(
                user_id=user.id,
                organization_id=data.organization.id,
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

        # The per-user limit is checked the same way when it is requested.
        current = await repo.get_user_organizations_membership_count(data.user.id)
        with pytest.raises(
            OrganizationLimitReachedError, match="limit of organizations"
        ):
            await repo.create_organization(
                data.user.id,
                OrganizationCreateIn(name="second"),
                membership_limit=current,
            )
        second = await repo.create_organization(
            data.user.id,
            OrganizationCreateIn(name="second"),
            membership_limit=current + 1,
        )
        assert await repo.get_organization_member(second.id, data.user.id) is not None

    # ---------------------------------------------------------------- invites
    @pytest.mark.asyncio
    async def test_duplicate_invite_is_refused(
        self, create_organization_with_user: OrganizationFixtureData
    ) -> None:
        data = create_organization_with_user
        repo = InviteRepository(data.engine)
        invite = CreateOrganizationInvite(
            email="new@example.com",
            role=OrgRole.MEMBER,
            organization_id=data.organization.id,
            invited_by=data.user.id,
        )

        winners, losers = _split(
            await _race(
                repo.create_organization_invite(invite),
                repo.create_organization_invite(invite),
            ),
            OrganizationInviteAlreadyExistsError,
        )

        assert len(winners) == 1
        assert len(losers) == 1
        assert len(await repo.get_invites_by_organization_id(data.organization.id)) == 1

    # ---------------------------------------------------------- organizations
    @pytest.mark.asyncio
    async def test_organization_deletion_refuses_members_and_reports_missing(
        self,
        create_organization_with_user: OrganizationFixtureData,
        test_user_create: CreateUser,
    ) -> None:
        data = create_organization_with_user
        repo = UserRepository(data.engine)
        joiner = await repo.create_user(
            test_user_create.model_copy(
                update={"email": f"joiner-{uuid.uuid4().hex}@example.com"}
            )
        )
        assert joiner is not None
        member = await repo.create_organization_member(
            OrganizationMemberCreate(
                user_id=joiner.id,
                organization_id=data.organization.id,
                role=OrgRole.MEMBER,
            )
        )

        with pytest.raises(OrganizationDeleteError, match="has members"):
            await repo.delete_organization(data.organization.id)
        assert await repo.get_organization_details(data.organization.id) is not None

        await repo.delete_organization_member(member.id)
        assert await repo.delete_organization(uuid.uuid4()) is False
        assert await repo.delete_organization(data.organization.id) is True
        assert await repo.get_organization_details(data.organization.id) is None

    # ------------------------------------------- references vs. deletion
    @pytest.mark.asyncio
    async def test_references_wait_for_the_deletion_request_and_are_refused(
        self, create_satellite: SatelliteFixtureData
    ) -> None:
        data = create_satellite
        deployments = DeploymentRepository(data.engine)
        entries = TrackEntryRepository(data.engine)
        track = await TrackRepository(data.engine).create_track(
            TrackCreate(
                orbit_id=data.orbit.id, name="t", artifact_type=ArtifactType.MODEL
            )
        )

        async with AsyncSession(data.engine) as session:
            artifact = (
                await session.execute(
                    select(ArtifactOrm)
                    .where(ArtifactOrm.id == data.model.id)
                    .with_for_update()
                )
            ).scalar_one()
            deploy = asyncio.create_task(
                deployments.create_deployment(
                    DeploymentCreate(
                        name="late",
                        orbit_id=data.orbit.id,
                        satellite_id=data.satellite.id,
                        artifact_id=data.model.id,
                        status=DeploymentStatus.PENDING,
                    )
                )
            )
            link = asyncio.create_task(
                entries.create_entry(
                    TrackEntryCreate(
                        track_id=track.id,
                        artifact_id=data.model.id,
                        added_by=data.user.id,
                    )
                )
            )
            await asyncio.sleep(0.5)
            assert not deploy.done(), "the deployment must wait on the artifact row"
            assert not link.done(), "the track link must wait on the artifact row"
            artifact.status = ArtifactStatus.PENDING_DELETION.value
            await session.commit()

        with pytest.raises(ArtifactStatusMismatchError, match="pending_deletion"):
            await deploy
        with pytest.raises(ArtifactBeingDeletedError):
            await link
        async with AsyncSession(data.engine) as session:
            late_deployments = await session.scalar(
                select(func.count())
                .select_from(DeploymentOrm)
                .where(DeploymentOrm.artifact_id == data.model.id)
            )
        assert late_deployments == 0
        assert await entries.has_entries_for_artifact(data.model.id) is False

    @pytest.mark.asyncio
    async def test_forced_stage_deletion_never_leaves_a_dangling_assignment(
        self, create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
    ) -> None:
        data = create_collection
        artifacts = await _artifacts(
            ArtifactRepository(data.engine), test_artifact, data.collection.id, 3
        )
        track = await TrackRepository(data.engine).create_track(
            TrackCreate(
                orbit_id=data.orbit.id, name="t", artifact_type=ArtifactType.MODEL
            )
        )
        stages = TrackStageRepository(data.engine)
        entries = TrackEntryRepository(data.engine)

        for artifact in artifacts:
            stage = await stages.create_stage(
                StageCreate(track_id=track.id, name=f"stage-{artifact.id}")
            )
            entry = await entries.create_entry(
                TrackEntryCreate(
                    track_id=track.id, artifact_id=artifact.id, added_by=data.user.id
                )
            )

            deletion, assignment = await _race(
                stages.delete_stage(stage.id, unassign=True),
                entries.update_entry(entry.id, TrackEntryUpdate(stage_id=stage.id)),
            )

            # The forced deletion always wins: it either cleared the assignment
            # that got in first, or the assignment found the stage gone (422).
            assert deletion is None
            assert not isinstance(assignment, BaseException) or (
                isinstance(assignment, ApplicationError)
                and assignment.status_code == 422
            ), assignment
            assert await stages.get_stage(stage.id) is None
            stored = await entries.get_entry(entry.id)
            assert stored is not None
            assert stored.stage_id is None

    # ------------------------------------------------ per-user membership cap
    @pytest.mark.asyncio
    async def test_direct_member_addition_respects_the_user_cap(
        self,
        create_organization_with_user: OrganizationFixtureData,
        test_user_create: CreateUser,
    ) -> None:
        data = create_organization_with_user
        repo = UserRepository(data.engine)
        joiner = await repo.create_user(
            test_user_create.model_copy(
                update={"email": f"joiner-{uuid.uuid4().hex}@example.com"}
            )
        )
        assert joiner is not None
        second = await repo.create_organization(
            data.user.id, OrganizationCreateIn(name="second"), membership_limit=10
        )
        await _set_limit(data.engine, second.id, members_limit=10)
        already = await repo.get_user_organizations_membership_count(joiner.id)
        make = lambda organization_id, limit: repo.create_organization_member(  # noqa: E731
            OrganizationMemberCreate(
                user_id=joiner.id, organization_id=organization_id, role=OrgRole.MEMBER
            ),
            membership_limit=limit,
        )

        # At the cap the direct addition is refused like an invite acceptance.
        with pytest.raises(
            OrganizationLimitReachedError, match="limit of organizations"
        ):
            await make(data.organization.id, already)

        # One slot left, two organizations at once: exactly one addition wins.
        winners, losers = _split(
            await _race(
                make(data.organization.id, already + 1),
                make(second.id, already + 1),
            ),
            OrganizationLimitReachedError,
        )
        assert len(winners) == 1
        assert len(losers) == 1
        assert await repo.get_user_organizations_membership_count(joiner.id) == (
            already + 1
        )

    # ------------------------------------------------------- blacklist expiry
    @pytest.mark.asyncio
    async def test_blacklisting_keeps_the_longest_expiry(
        self, create_database_and_apply_migrations: str
    ) -> None:
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(create_database_and_apply_migrations)
        repo = TokenBlackListRepository(engine)
        token = f"refresh-{uuid.uuid4()}"
        base = int(time.time()) + 3600

        assert await repo.add_token(token, base) is True
        assert await repo.add_token(token, base + 600) is False
        assert await repo.add_token(token, base - 600) is False

        async with AsyncSession(engine) as session:
            expire_at = await session.scalar(
                select(TokenBlackListOrm.expire_at).where(
                    TokenBlackListOrm.token == token
                )
            )
        assert expire_at == base + 600

    @pytest.mark.asyncio
    async def test_migration_keeps_the_longest_blacklist_expiry(
        self, create_database_and_apply_migrations: str
    ) -> None:
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(create_database_and_apply_migrations)

        async def alembic(action: str, revision: str) -> None:
            def run(connection: Connection) -> None:
                alembic_cfg.attributes["connection"] = connection
                getattr(command, action)(alembic_cfg, revision)

            async with engine.begin() as connection:
                await connection.run_sync(run)

        token = f"refresh-{uuid.uuid4()}"
        await alembic("downgrade", "038")
        async with AsyncSession(engine) as session:
            await session.execute(
                insert(TokenBlackListOrm),
                [
                    {"id": uuid.uuid4(), "token": token, "expire_at": 100},
                    {"id": uuid.uuid4(), "token": token, "expire_at": 300},
                    {"id": uuid.uuid4(), "token": token, "expire_at": 200},
                ],
            )
            await session.commit()

        await alembic("upgrade", "head")

        async with AsyncSession(engine) as session:
            rows = list(
                await session.scalars(
                    select(TokenBlackListOrm.expire_at).where(
                        TokenBlackListOrm.token == token
                    )
                )
            )
        assert rows == [300]
