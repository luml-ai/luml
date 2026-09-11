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
    Artifact,
    ArtifactCreate,
    ArtifactStatus,
    ArtifactType,
)
from luml.schemas.collections import CollectionCreate
from luml.schemas.deployment import DeploymentCreate, DeploymentStatus
from luml.schemas.satellite import Satellite, SatelliteCreate
from luml.schemas.tracks import TrackCreate, TrackEntryCreate

from tests.conftest import CollectionFixtureData


async def _create_artifact(
    repository: ArtifactRepository,
    template: ArtifactCreate,
    collection_id: uuid.UUID,
    *,
    name: str,
    status: ArtifactStatus = ArtifactStatus.UPLOADED,
) -> Artifact:
    data = template.model_copy(
        update={
            "collection_id": collection_id,
            "name": name,
            "status": status,
            "unique_identifier": str(uuid.uuid4()),
            "bucket_location": f"objects/{uuid.uuid4()}",
        }
    )
    return await repository.create_artifact(data)


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


class TestArtifactsBatchDeletion:
    @pytest.mark.asyncio
    async def test_phase_one_accepts_artifacts_in_every_status(
        self,
        create_collection: CollectionFixtureData,
        test_artifact: ArtifactCreate,
    ) -> None:
        repository = ArtifactRepository(create_collection.engine)
        artifacts = [
            await _create_artifact(
                repository,
                test_artifact,
                create_collection.collection.id,
                name=artifact_status.value,
                status=artifact_status,
            )
            for artifact_status in ArtifactStatus
        ]

        records = await repository.request_batch_deletion(
            create_collection.collection.id,
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

    @pytest.mark.asyncio
    async def test_phase_one_ignores_artifacts_outside_the_collection(
        self,
        create_collection: CollectionFixtureData,
        test_artifact: ArtifactCreate,
    ) -> None:
        data = create_collection
        repository = ArtifactRepository(data.engine)
        other_collection = await CollectionRepository(data.engine).create_collection(
            CollectionCreate(
                orbit_id=data.orbit.id,
                description="description",
                name="other",
                type=data.collection.type,
            )
        )
        foreign_artifact = await _create_artifact(
            repository,
            test_artifact,
            other_collection.id,
            name="foreign",
        )

        records = await repository.request_batch_deletion(
            data.collection.id,
            [foreign_artifact.id, uuid.uuid4()],
        )

        assert records == []
        persisted = await repository.get_artifact(foreign_artifact.id)
        assert persisted is not None
        assert persisted.status == ArtifactStatus.UPLOADED

    @pytest.mark.asyncio
    async def test_phase_one_moves_only_unreferenced_artifacts_with_details(
        self,
        create_collection: CollectionFixtureData,
        test_artifact: ArtifactCreate,
    ) -> None:
        data = create_collection
        repository = ArtifactRepository(data.engine)
        deployment_repository = DeploymentRepository(data.engine)
        track_repository = TrackRepository(data.engine)
        entry_repository = TrackEntryRepository(data.engine)
        satellite = await _create_satellite(data)
        eligible = await _create_artifact(
            repository,
            test_artifact,
            data.collection.id,
            name="eligible",
            status=ArtifactStatus.UPLOAD_FAILED,
        )
        failed_deployment_artifact = await _create_artifact(
            repository,
            test_artifact,
            data.collection.id,
            name="failed deployment artifact",
        )
        active_deployment_artifact = await _create_artifact(
            repository,
            test_artifact,
            data.collection.id,
            name="active deployment artifact",
        )
        tracked_artifact = await _create_artifact(
            repository,
            test_artifact,
            data.collection.id,
            name="tracked",
        )
        failed_deployment, _ = await deployment_repository.create_deployment(
            DeploymentCreate(
                name="failed deployment",
                orbit_id=data.orbit.id,
                satellite_id=satellite.id,
                artifact_id=failed_deployment_artifact.id,
                status=DeploymentStatus.FAILED,
            )
        )
        active_deployment, _ = await deployment_repository.create_deployment(
            DeploymentCreate(
                name="active deployment",
                orbit_id=data.orbit.id,
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
                    orbit_id=data.orbit.id,
                )
            )
            for name in ("release", "latest")
        ]
        for track in tracks:
            await entry_repository.create_entry(
                TrackEntryCreate(
                    track_id=track.id,
                    artifact_id=tracked_artifact.id,
                    added_by=data.user.id,
                )
            )

        records = await repository.request_batch_deletion(
            data.collection.id,
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
        assert (
            await repository.get_artifact(failed_deployment_artifact.id)
        ).status == ArtifactStatus.UPLOADED
        assert (
            await repository.get_artifact(active_deployment_artifact.id)
        ).status == ArtifactStatus.UPLOADED
        assert (
            await repository.get_artifact(tracked_artifact.id)
        ).status == ArtifactStatus.UPLOADED
        assert (
            await deployment_repository.get_deployment(
                failed_deployment.id, data.orbit.id
            )
            is not None
        )
        assert await entry_repository.has_entries_for_artifact(tracked_artifact.id)

    @pytest.mark.asyncio
    async def test_mark_deletion_failed_updates_requested_rows(
        self,
        create_collection: CollectionFixtureData,
        test_artifact: ArtifactCreate,
    ) -> None:
        repository = ArtifactRepository(create_collection.engine)
        artifact = await _create_artifact(
            repository,
            test_artifact,
            create_collection.collection.id,
            name="artifact",
        )
        await repository.request_batch_deletion(
            create_collection.collection.id, [artifact.id]
        )

        await repository.mark_deletion_failed(
            create_collection.collection.id, [artifact.id]
        )

        updated = await repository.get_artifact(artifact.id)
        assert updated is not None
        assert updated.status == ArtifactStatus.DELETION_FAILED

    @pytest.mark.asyncio
    async def test_record_removal_updates_count_and_reports_missing_record(
        self,
        create_collection: CollectionFixtureData,
        test_artifact: ArtifactCreate,
    ) -> None:
        repository = ArtifactRepository(create_collection.engine)
        artifacts = [
            await _create_artifact(
                repository,
                test_artifact,
                create_collection.collection.id,
                name=f"artifact-{index}",
            )
            for index in range(3)
        ]
        assert (
            await repository.get_collection_artifacts_count(
                create_collection.collection.id
            )
            == 3
        )

        for artifact in artifacts:
            assert await repository.delete_artifact_record(
                artifact.id, create_collection.collection.id
            )
        assert not await repository.delete_artifact_record(
            artifacts[0].id, create_collection.collection.id
        )

        for artifact in artifacts:
            assert await repository.get_artifact(artifact.id) is None
        assert (
            await repository.get_collection_artifacts_count(
                create_collection.collection.id
            )
            == 0
        )

    @pytest.mark.asyncio
    async def test_record_removal_reports_deployment_and_track_constraints(
        self,
        create_collection: CollectionFixtureData,
        test_artifact: ArtifactCreate,
    ) -> None:
        data = create_collection
        repository = ArtifactRepository(data.engine)
        deployment_repository = DeploymentRepository(data.engine)
        track_repository = TrackRepository(data.engine)
        entry_repository = TrackEntryRepository(data.engine)
        satellite = await _create_satellite(data)
        deployed = await _create_artifact(
            repository,
            test_artifact,
            data.collection.id,
            name="deployed",
        )
        tracked = await _create_artifact(
            repository,
            test_artifact,
            data.collection.id,
            name="tracked",
        )
        await deployment_repository.create_deployment(
            DeploymentCreate(
                name="deployment",
                orbit_id=data.orbit.id,
                satellite_id=satellite.id,
                artifact_id=deployed.id,
            )
        )
        track = await track_repository.create_track(
            TrackCreate(
                name="track",
                artifact_type=ArtifactType.MODEL,
                orbit_id=data.orbit.id,
            )
        )
        await entry_repository.create_entry(
            TrackEntryCreate(
                track_id=track.id,
                artifact_id=tracked.id,
                added_by=data.user.id,
            )
        )

        with pytest.raises(DatabaseConstraintError):
            await repository.delete_artifact_record(deployed.id, data.collection.id)
        with pytest.raises(DatabaseConstraintError):
            await repository.delete_artifact_record(tracked.id, data.collection.id)

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
    @pytest.mark.asyncio
    async def test_deployment_creation_rejects_non_uploaded_status(
        self,
        create_collection: CollectionFixtureData,
        test_artifact: ArtifactCreate,
        artifact_status: ArtifactStatus,
    ) -> None:
        artifact_repository = ArtifactRepository(create_collection.engine)
        deployment_repository = DeploymentRepository(create_collection.engine)
        artifact = await _create_artifact(
            artifact_repository,
            test_artifact,
            create_collection.collection.id,
            name=artifact_status.value,
            status=artifact_status,
        )
        satellite = await _create_satellite(create_collection)

        with pytest.raises(ArtifactStatusMismatchError, match=artifact_status.value):
            await deployment_repository.create_deployment(
                DeploymentCreate(
                    name="deployment",
                    orbit_id=create_collection.orbit.id,
                    satellite_id=satellite.id,
                    artifact_id=artifact.id,
                )
            )

        assert (
            await deployment_repository.list_deployments(create_collection.orbit.id)
            == []
        )

    @pytest.mark.asyncio
    async def test_deployment_creation_and_phase_one_serialize_on_artifact(
        self,
        create_collection: CollectionFixtureData,
        test_artifact: ArtifactCreate,
    ) -> None:
        data = create_collection
        artifact_repository = ArtifactRepository(data.engine)
        deployment_repository = DeploymentRepository(data.engine)
        artifact = await _create_artifact(
            artifact_repository,
            test_artifact,
            data.collection.id,
            name="concurrent",
        )
        satellite = await _create_satellite(data)
        deployment_data = DeploymentCreate(
            name="deployment",
            orbit_id=data.orbit.id,
            satellite_id=satellite.id,
            artifact_id=artifact.id,
        )

        transition_result, creation_result = await asyncio.gather(
            artifact_repository.request_batch_deletion(
                data.collection.id, [artifact.id]
            ),
            deployment_repository.create_deployment(deployment_data),
            return_exceptions=True,
        )

        assert not isinstance(transition_result, BaseException)
        assert len(transition_result) == 1
        current = await artifact_repository.get_artifact(artifact.id)
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
            assert await deployment_repository.list_deployments(data.orbit.id) == []
