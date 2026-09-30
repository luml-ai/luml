import uuid
from contextlib import nullcontext

import pytest
from luml.infra.exceptions import ArtifactDeployedError, ArtifactTrackedError
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.deployments import DeploymentRepository
from luml.repositories.lineage import LineageRepository
from luml.repositories.satellites import SatelliteRepository
from luml.schemas.artifacts import (
    ArtifactCreate,
    ArtifactStatus,
    ArtifactType,
    ArtifactUpdate,
)
from luml.schemas.deployment import DeploymentCreate, DeploymentStatus
from luml.schemas.lineage import LineageVia
from luml.schemas.satellite import (
    SatelliteCreate,
    SatelliteTaskStatus,
    SatelliteTaskType,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.repositories.artifacts.conftest import _add_artifact_to_track
from tests.support.builders import create_artifact
from tests.support.seeds import CollectionFixtureData


class TestArtifactRepositoryDeletion:
    async def test_delete_artifact_removes_artifact(
        self,
        repository: ArtifactRepository,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        model = new_artifact.model_copy()
        model.collection_id = seeded_collection.collection.id

        created_model = await repository.create_artifact(model)

        await repository.delete_artifact(created_model.id)

        fetched_model = await repository.get_artifact(created_model.id)
        assert fetched_model is None

    async def test_delete_artifact_rolls_back_with_failing_caller_transaction(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        lineage_repository = LineageRepository(engine)
        artifact = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="kept-on-failure",
            status=new_artifact.status,
        )

        async def delete_then_fail_lineage_cleanup() -> None:
            async with lineage_repository.transaction() as session:
                await repository.delete_artifact(artifact.id, session)
                raise RuntimeError("cleanup failed")

        with pytest.raises(RuntimeError, match="cleanup failed"):
            await delete_then_fail_lineage_cleanup()

        assert await repository.get_artifact(artifact.id) is not None

        async with lineage_repository.transaction() as session:
            await repository.delete_artifact(artifact.id, session)

        assert await repository.get_artifact(artifact.id) is None

    async def test_delete_artifact_preserves_connected_lineage_node_snapshot(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        lineage_repository = LineageRepository(engine)
        deleted_artifact = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="artifact-to-delete",
            status=new_artifact.status,
        )
        surviving_artifact = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="surviving-artifact",
            status=new_artifact.status,
        )
        listed = await repository.get_artifacts_by_ids_in_orbit(
            seeded_collection.orbit.id, [deleted_artifact.id, surviving_artifact.id]
        )
        listed_by_id = {artifact.id: artifact for artifact in listed}
        deleted_node = await lineage_repository.get_or_create_node(
            seeded_collection.orbit.id, listed_by_id[deleted_artifact.id]
        )
        surviving_node = await lineage_repository.get_or_create_node(
            seeded_collection.orbit.id, listed_by_id[surviving_artifact.id]
        )
        edge = (
            await lineage_repository.create_edges(
                seeded_collection.orbit.id,
                [(deleted_node.id, surviving_node.id)],
                "Artifact User",
                LineageVia.API,
            )
        )[0]
        await repository.update_artifact(
            deleted_artifact.id,
            seeded_collection.collection.id,
            ArtifactUpdate(id=deleted_artifact.id, name="refreshed-name"),
        )

        await lineage_repository.refresh_node_copy(deleted_artifact.id)
        await repository.delete_artifact(deleted_artifact.id)
        await lineage_repository.delete_edgeless_nodes(seeded_collection.orbit.id)

        assert await repository.get_artifact(deleted_artifact.id) is None
        detached_node = (
            await lineage_repository.get_nodes_by_ids(
                seeded_collection.orbit.id, [deleted_node.id]
            )
        )[0]
        assert detached_node.artifact_id is None
        assert detached_node.name == "refreshed-name"
        assert detached_node.type == ArtifactType.MODEL.value
        assert detached_node.collection_name == seeded_collection.collection.name
        assert await lineage_repository.get_edges_by_ids(
            seeded_collection.orbit.id, [edge.id]
        )

    async def test_delete_artifact_refuses_deployed_artifact(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        lineage_repository = LineageRepository(engine)
        satellite_repository = SatelliteRepository(engine)
        deployment_repository = DeploymentRepository(engine)

        model = new_artifact.model_copy()
        model.collection_id = seeded_collection.collection.id
        model.status = ArtifactStatus.UPLOADED

        created_model = await repository.create_artifact(model)
        peer_model = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="lineage-peer",
            status=new_artifact.status,
        )
        listed = await repository.get_artifacts_by_ids_in_orbit(
            seeded_collection.orbit.id, [created_model.id, peer_model.id]
        )
        listed_by_id = {artifact.id: artifact for artifact in listed}
        created_node = await lineage_repository.get_or_create_node(
            seeded_collection.orbit.id, listed_by_id[created_model.id]
        )
        peer_node = await lineage_repository.get_or_create_node(
            seeded_collection.orbit.id, listed_by_id[peer_model.id]
        )
        edge = (
            await lineage_repository.create_edges(
                seeded_collection.orbit.id,
                [(created_node.id, peer_node.id)],
                "Artifact User",
                LineageVia.API,
            )
        )[0]

        satellite = await satellite_repository.create_satellite(
            SatelliteCreate(
                orbit_id=seeded_collection.orbit.id,
                api_key_hash=str(uuid.uuid4()),
                name="test_satellite",
            )
        )

        deployment_data = DeploymentCreate(
            name="my-deployment",
            orbit_id=seeded_collection.orbit.id,
            satellite_id=satellite.id,
            artifact_id=created_model.id,
            status=DeploymentStatus.PENDING,
        )
        await deployment_repository.create_deployment(deployment_data)
        await lineage_repository.refresh_node_copy(created_model.id)

        with pytest.raises(ArtifactDeployedError) as error:
            await repository.delete_artifact(created_model.id)

        assert error.value.status_code == 409
        assert await repository.get_artifact(created_model.id) is not None
        attached_node = (
            await lineage_repository.get_nodes_by_ids(
                seeded_collection.orbit.id, [created_node.id]
            )
        )[0]
        assert attached_node.artifact_id == created_model.id
        assert await lineage_repository.get_edges_by_ids(
            seeded_collection.orbit.id, [edge.id]
        )

    @pytest.mark.parametrize("tracked", [False, True])
    async def test_forced_deletion_undeploys_then_removes_the_artifact(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
        tracked: bool,
    ) -> None:
        orbit = seeded_collection.orbit
        lineage_repository = LineageRepository(engine)
        deployment_repository = DeploymentRepository(engine)
        satellite_repository = SatelliteRepository(engine)
        artifact = await create_artifact(
            engine, new_artifact, seeded_collection.collection.id, name="deployed"
        )
        satellite = await satellite_repository.create_satellite(
            SatelliteCreate(
                orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="test_satellite"
            )
        )
        deployment, _ = await deployment_repository.create_deployment(
            DeploymentCreate(
                name="my-deployment",
                orbit_id=orbit.id,
                satellite_id=satellite.id,
                artifact_id=artifact.id,
                status=DeploymentStatus.ACTIVE,
            )
        )
        if tracked:
            await _add_artifact_to_track(
                engine, orbit.id, artifact.id, seeded_collection.user.email
            )

        with pytest.raises(ArtifactTrackedError) if tracked else nullcontext():
            async with lineage_repository.transaction() as session:
                await lineage_repository.lock_orbit(orbit.id, session)
                await deployment_repository.undeploy_artifact_deployments(
                    artifact.id, session
                )
                await lineage_repository.refresh_node_copy(artifact.id, session)
                await repository.delete_artifact(artifact.id, session)
                await lineage_repository.delete_unreachable_deleted_nodes(
                    orbit.id, session
                )

        stored = await repository.get_artifact(artifact.id)
        remaining = await deployment_repository.list_deployments(orbit.id)
        tasks = await satellite_repository.list_tasks(
            satellite.id, status=SatelliteTaskStatus.PENDING
        )
        undeploys = [task for task in tasks if task.type == SatelliteTaskType.UNDEPLOY]
        if tracked:
            assert stored is not None
            assert [item.id for item in remaining] == [deployment.id]
            assert undeploys == []
        else:
            assert stored is None
            assert remaining == []
            assert [task.payload["deployment_id"] for task in undeploys] == [
                str(deployment.id)
            ]

    async def test_delete_artifact_refuses_tracked_artifact(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        artifact = await create_artifact(
            engine, new_artifact, seeded_collection.collection.id, name="tracked"
        )
        await _add_artifact_to_track(
            engine,
            seeded_collection.orbit.id,
            artifact.id,
            seeded_collection.user.email,
        )

        with pytest.raises(ArtifactTrackedError) as error:
            await repository.delete_artifact(artifact.id)

        assert error.value.status_code == 409
        assert await repository.get_artifact(artifact.id) is not None
