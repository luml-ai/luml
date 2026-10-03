import asyncio
import uuid

import pytest
from luml.infra.exceptions import (
    ArtifactStatusMismatchError,
    DatabaseConstraintError,
)
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.collections import CollectionRepository
from luml.repositories.deployments import DeploymentRepository
from luml.repositories.satellites import SatelliteRepository
from luml.repositories.tracks import TrackEntryRepository, TrackRepository
from luml.schemas.artifacts import (
    ArtifactCreate,
    ArtifactStatus,
    ArtifactType,
)
from luml.schemas.collections import CollectionCreate
from luml.schemas.deployment import DeploymentCreate, DeploymentStatus
from luml.schemas.satellite import Satellite, SatelliteCreate
from luml.schemas.tracks import TrackCreate, TrackEntryCreate
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.builders import create_artifact
from tests.support.seeds import CollectionFixtureData


async def _create_satellite(
    data: CollectionFixtureData, *, name: str = "satellite"
) -> Satellite:
    return await SatelliteRepository(data.engine).create_satellite(
        SatelliteCreate(
            orbit_id=data.orbit.id,
            api_key_hash=str(uuid.uuid4()),
            name=name,
        )
    )


class TestArtifactRepositoryBatchDeletion:
    async def test_request_batch_deletion_accepts_artifacts_in_every_status(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        artifacts = [
            await create_artifact(
                engine,
                new_artifact,
                seeded_collection.collection.id,
                name=artifact_status.value,
                status=artifact_status,
            )
            for artifact_status in ArtifactStatus
        ]

        records = await repository.request_batch_deletion(
            seeded_collection.collection.id,
            [artifact.id for artifact in artifacts],
        )

        assert [record.artifact.id for record in records] == [
            artifact.id for artifact in artifacts
        ]
        assert all(
            record.artifact.status == ArtifactStatus.PENDING_DELETION
            for record in records
        )
        for artifact in artifacts:
            persisted = await repository.get_artifact(artifact.id)
            assert persisted is not None
            assert persisted.status == ArtifactStatus.PENDING_DELETION

    async def test_request_batch_deletion_ignores_artifacts_outside_collection(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        other_collection = await CollectionRepository(engine).create_collection(
            CollectionCreate(
                orbit_id=seeded_collection.orbit.id,
                description="description",
                name="other",
                type=seeded_collection.collection.type,
            )
        )
        foreign_artifact = await create_artifact(
            engine, new_artifact, other_collection.id, name="foreign"
        )

        records = await repository.request_batch_deletion(
            seeded_collection.collection.id,
            [foreign_artifact.id, uuid.uuid4()],
        )

        assert records == []
        persisted = await repository.get_artifact(foreign_artifact.id)
        assert persisted is not None
        assert persisted.status == ArtifactStatus.UPLOADED

    async def test_request_batch_deletion_moves_only_unreferenced_artifacts(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        deployment_repository = DeploymentRepository(engine)
        track_repository = TrackRepository(engine)
        entry_repository = TrackEntryRepository(engine)
        satellite = await _create_satellite(seeded_collection)
        eligible = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="eligible",
            status=ArtifactStatus.UPLOAD_FAILED,
        )
        failed_deployment_artifact = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="failed deployment artifact",
        )
        active_deployment_artifact = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="active deployment artifact",
        )
        tracked_artifact = await create_artifact(
            engine, new_artifact, seeded_collection.collection.id, name="tracked"
        )
        failed_deployment, _ = await deployment_repository.create_deployment(
            DeploymentCreate(
                name="failed deployment",
                orbit_id=seeded_collection.orbit.id,
                satellite_id=satellite.id,
                artifact_id=failed_deployment_artifact.id,
                status=DeploymentStatus.FAILED,
            )
        )
        active_deployment, _ = await deployment_repository.create_deployment(
            DeploymentCreate(
                name="active deployment",
                orbit_id=seeded_collection.orbit.id,
                satellite_id=satellite.id,
                artifact_id=active_deployment_artifact.id,
                status=DeploymentStatus.ACTIVE,
            )
        )
        tracks = [
            await track_repository.create_track(
                TrackCreate(
                    name=name,
                    artifact_type=ArtifactType.MODEL,
                    orbit_id=seeded_collection.orbit.id,
                )
            )
            for name in ("release", "latest")
        ]
        for track in tracks:
            await entry_repository.create_entry(
                TrackEntryCreate(
                    track_id=track.id,
                    artifact_id=tracked_artifact.id,
                    added_by=seeded_collection.user.email,
                )
            )

        records = await repository.request_batch_deletion(
            seeded_collection.collection.id,
            [
                eligible.id,
                failed_deployment_artifact.id,
                active_deployment_artifact.id,
                tracked_artifact.id,
            ],
        )
        records_by_id = {record.artifact.id: record for record in records}

        assert records_by_id[eligible.id].artifact.status == (
            ArtifactStatus.PENDING_DELETION
        )
        assert records_by_id[eligible.id].deployments == []
        assert records_by_id[eligible.id].tracks == []
        assert records_by_id[failed_deployment_artifact.id].deployments[0].id == (
            failed_deployment.id
        )
        assert (
            records_by_id[failed_deployment_artifact.id].deployments[0].status
            == DeploymentStatus.FAILED
        )
        assert records_by_id[active_deployment_artifact.id].deployments[0].id == (
            active_deployment.id
        )
        assert (
            records_by_id[active_deployment_artifact.id].deployments[0].status
            == DeploymentStatus.ACTIVE
        )
        assert {track.id for track in records_by_id[tracked_artifact.id].tracks} == {
            track.id for track in tracks
        }
        assert {track.name for track in records_by_id[tracked_artifact.id].tracks} == {
            "release",
            "latest",
        }
        failed_artifact = await repository.get_artifact(failed_deployment_artifact.id)
        active_artifact = await repository.get_artifact(active_deployment_artifact.id)
        tracked = await repository.get_artifact(tracked_artifact.id)
        assert failed_artifact is not None
        assert active_artifact is not None
        assert tracked is not None
        assert failed_artifact.status == ArtifactStatus.UPLOADED
        assert active_artifact.status == ArtifactStatus.UPLOADED
        assert tracked.status == ArtifactStatus.UPLOADED
        assert (
            await deployment_repository.get_deployment(
                failed_deployment.id, seeded_collection.orbit.id
            )
            is not None
        )
        assert await entry_repository.has_entries_for_artifact(tracked_artifact.id)

    async def test_mark_deletion_failed_updates_requested_rows(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        artifact = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="artifact",
        )
        await repository.request_batch_deletion(
            seeded_collection.collection.id, [artifact.id]
        )

        await repository.mark_deletion_failed(
            seeded_collection.collection.id, [artifact.id]
        )

        updated = await repository.get_artifact(artifact.id)
        assert updated is not None
        assert updated.status == ArtifactStatus.DELETION_FAILED

    async def test_delete_artifact_record_updates_count_and_reports_missing_record(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        artifacts = [
            await create_artifact(
                engine,
                new_artifact,
                seeded_collection.collection.id,
                name=f"artifact-{index}",
            )
            for index in range(3)
        ]
        assert (
            await repository.get_collection_artifacts_count(
                seeded_collection.collection.id
            )
            == 3
        )

        for artifact in artifacts:
            assert await repository.delete_artifact_record(
                artifact.id, seeded_collection.collection.id
            )
        assert not await repository.delete_artifact_record(
            artifacts[0].id, seeded_collection.collection.id
        )

        for artifact in artifacts:
            assert await repository.get_artifact(artifact.id) is None
        assert (
            await repository.get_collection_artifacts_count(
                seeded_collection.collection.id
            )
            == 0
        )

    async def test_delete_artifact_record_raises_on_deployment_and_track_references(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        deployment_repository = DeploymentRepository(engine)
        track_repository = TrackRepository(engine)
        entry_repository = TrackEntryRepository(engine)
        satellite = await _create_satellite(seeded_collection)
        deployed = await create_artifact(
            engine, new_artifact, seeded_collection.collection.id, name="deployed"
        )
        tracked = await create_artifact(
            engine, new_artifact, seeded_collection.collection.id, name="tracked"
        )
        await deployment_repository.create_deployment(
            DeploymentCreate(
                name="deployment",
                orbit_id=seeded_collection.orbit.id,
                satellite_id=satellite.id,
                artifact_id=deployed.id,
            )
        )
        track = await track_repository.create_track(
            TrackCreate(
                name="track",
                artifact_type=ArtifactType.MODEL,
                orbit_id=seeded_collection.orbit.id,
            )
        )
        await entry_repository.create_entry(
            TrackEntryCreate(
                track_id=track.id,
                artifact_id=tracked.id,
                added_by=seeded_collection.user.email,
            )
        )

        with pytest.raises(DatabaseConstraintError):
            await repository.delete_artifact_record(
                deployed.id, seeded_collection.collection.id
            )
        with pytest.raises(DatabaseConstraintError):
            await repository.delete_artifact_record(
                tracked.id, seeded_collection.collection.id
            )

        assert await repository.get_artifact(deployed.id) is not None
        assert await repository.get_artifact(tracked.id) is not None

    @pytest.mark.parametrize(
        "artifact_status",
        [
            ArtifactStatus.PENDING_UPLOAD,
            ArtifactStatus.UPLOAD_FAILED,
            ArtifactStatus.PENDING_DELETION,
            ArtifactStatus.DELETION_FAILED,
        ],
    )
    async def test_create_deployment_rejects_artifact_not_uploaded(
        self,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
        artifact_status: ArtifactStatus,
    ) -> None:
        deployment_repository = DeploymentRepository(engine)
        artifact = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name=artifact_status.value,
            status=artifact_status,
        )
        satellite = await _create_satellite(seeded_collection)

        with pytest.raises(ArtifactStatusMismatchError, match=artifact_status.value):
            await deployment_repository.create_deployment(
                DeploymentCreate(
                    name="deployment",
                    orbit_id=seeded_collection.orbit.id,
                    satellite_id=satellite.id,
                    artifact_id=artifact.id,
                )
            )

        assert (
            await deployment_repository.list_deployments(seeded_collection.orbit.id)
            == []
        )

    async def test_create_deployment_and_batch_deletion_serialize_on_artifact(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        deployment_repository = DeploymentRepository(engine)
        artifact = await create_artifact(
            engine, new_artifact, seeded_collection.collection.id, name="concurrent"
        )
        satellite = await _create_satellite(seeded_collection)
        deployment_data = DeploymentCreate(
            name="deployment",
            orbit_id=seeded_collection.orbit.id,
            satellite_id=satellite.id,
            artifact_id=artifact.id,
        )

        transition_result, creation_result = await asyncio.gather(
            repository.request_batch_deletion(
                seeded_collection.collection.id, [artifact.id]
            ),
            deployment_repository.create_deployment(deployment_data),
            return_exceptions=True,
        )

        assert not isinstance(transition_result, BaseException)
        assert len(transition_result) == 1
        current = await repository.get_artifact(artifact.id)
        assert current is not None
        deployment_won = not isinstance(creation_result, BaseException)
        deletion_won = isinstance(creation_result, ArtifactStatusMismatchError)
        assert deployment_won != deletion_won
        if deployment_won:
            assert current.status == ArtifactStatus.UPLOADED
            assert transition_result[0].deployments
        else:
            assert current.status == ArtifactStatus.PENDING_DELETION
            assert transition_result[0].deployments == []
            assert (
                await deployment_repository.list_deployments(seeded_collection.orbit.id)
                == []
            )
