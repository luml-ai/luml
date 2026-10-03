import uuid

import pytest
from luml.infra.exceptions import NotFoundError
from luml.repositories.deployments import DeploymentRepository
from luml.repositories.orbit_secrets import OrbitSecretRepository
from luml.repositories.satellites import SatelliteRepository
from luml.schemas.deployment import Deployment, DeploymentCreate, DeploymentStatus
from luml.schemas.orbit import OrbitDetails
from luml.schemas.orbit_secret import OrbitSecretCreate
from luml.schemas.satellite import (
    Satellite,
    SatelliteCreate,
    SatelliteTaskStatus,
    SatelliteTaskType,
)

from tests.support.builders import create_sibling_orbit
from tests.support.seeds import SatelliteFixtureData


async def _create_satellite_in(
    data: SatelliteFixtureData, orbit: OrbitDetails
) -> Satellite:
    return await SatelliteRepository(data.engine).create_satellite(
        SatelliteCreate(
            orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="sibling satellite"
        )
    )


async def _create_deployment(data: SatelliteFixtureData) -> Deployment:
    deployment, _ = await DeploymentRepository(data.engine).create_deployment(
        DeploymentCreate(
            name="my-deployment",
            orbit_id=data.orbit.id,
            satellite_id=data.satellite.id,
            artifact_id=data.model.id,
            status=DeploymentStatus.DELETION_PENDING,
        )
    )
    return deployment


class TestDeploymentRepositoryCrud:
    async def test_create_deployment_returns_deployment_and_deploy_task(
        self, repository: DeploymentRepository, seeded_satellite: SatelliteFixtureData
    ) -> None:
        deployment_data = DeploymentCreate(
            name="my-deployment",
            orbit_id=seeded_satellite.orbit.id,
            satellite_id=seeded_satellite.satellite.id,
            artifact_id=seeded_satellite.model.id,
            status=DeploymentStatus.PENDING,
            created_by_user="test_user",
            tags=["test", "deployment"],
        )
        deployment, task = await repository.create_deployment(deployment_data)

        assert deployment
        assert deployment.orbit_id == deployment_data.orbit_id
        assert deployment.satellite_id == deployment_data.satellite_id
        assert deployment.artifact_id == deployment_data.artifact_id
        assert deployment.collection_id == seeded_satellite.model.collection_id
        assert deployment.status == DeploymentStatus.PENDING

        assert task
        assert task.satellite_id == deployment_data.satellite_id
        assert task.orbit_id == deployment_data.orbit_id
        assert task.type == SatelliteTaskType.DEPLOY
        assert task.payload["deployment_id"] == str(deployment.id)

    async def test_get_deployment_returns_created_deployment(
        self, repository: DeploymentRepository, seeded_satellite: SatelliteFixtureData
    ) -> None:
        deployment_data = DeploymentCreate(
            name="my-deployment",
            orbit_id=seeded_satellite.orbit.id,
            satellite_id=seeded_satellite.satellite.id,
            artifact_id=seeded_satellite.model.id,
            status=DeploymentStatus.PENDING,
            created_by_user="test_user",
            tags=["test", "deployment"],
        )
        deployment, _ = await repository.create_deployment(deployment_data)

        fetched_deployment = await repository.get_deployment(
            deployment.id, seeded_satellite.orbit.id
        )

        assert fetched_deployment
        assert fetched_deployment.id == deployment.id
        assert fetched_deployment.orbit_id == deployment_data.orbit_id
        assert fetched_deployment.satellite_id == deployment_data.satellite_id
        assert fetched_deployment.collection_id == seeded_satellite.model.collection_id

    async def test_request_deployment_deletion_enqueues_undeploy_task_only_once(
        self, repository: DeploymentRepository, seeded_satellite: SatelliteFixtureData
    ) -> None:
        created, _ = await repository.create_deployment(
            DeploymentCreate(
                name="my-deployment",
                orbit_id=seeded_satellite.orbit.id,
                satellite_id=seeded_satellite.satellite.id,
                artifact_id=seeded_satellite.model.id,
                status=DeploymentStatus.PENDING,
            )
        )

        result = await repository.request_deployment_deletion(
            seeded_satellite.orbit.id, created.id
        )
        assert result is not None
        dep, task = result
        assert dep.status == DeploymentStatus.DELETION_PENDING
        assert dep.collection_id == seeded_satellite.model.collection_id
        assert task is not None
        assert task.type == SatelliteTaskType.UNDEPLOY
        assert task.payload["deployment_id"] == str(created.id)

        result2 = await repository.request_deployment_deletion(
            seeded_satellite.orbit.id, created.id
        )
        assert result2 is not None
        dep2, task2 = result2
        assert dep2.status == DeploymentStatus.DELETION_PENDING
        assert task2 is None

    async def test_enqueue_undeploy_task_returns_existing_task_when_repeated(
        self, repository: DeploymentRepository, seeded_satellite: SatelliteFixtureData
    ) -> None:
        deployment, _ = await repository.create_deployment(
            DeploymentCreate(
                name="my-deployment",
                orbit_id=seeded_satellite.orbit.id,
                satellite_id=seeded_satellite.satellite.id,
                artifact_id=seeded_satellite.model.id,
                status=DeploymentStatus.ACTIVE,
            )
        )

        task = await repository.enqueue_undeploy_task(deployment.id)
        assert task is not None
        assert task.type == SatelliteTaskType.UNDEPLOY
        assert task.payload["deployment_id"] == str(deployment.id)
        assert task.status == SatelliteTaskStatus.PENDING

        duplicate_task = await repository.enqueue_undeploy_task(deployment.id)
        assert duplicate_task is not None
        assert duplicate_task.id == task.id

    async def test_get_deployment_returns_none_when_orbit_differs(
        self, repository: DeploymentRepository, seeded_satellite: SatelliteFixtureData
    ) -> None:
        deployment = await _create_deployment(seeded_satellite)
        sibling_orbit = await create_sibling_orbit(
            seeded_satellite.engine,
            seeded_satellite.organization.id,
            seeded_satellite.bucket_secret.id,
        )

        assert await repository.get_deployment(deployment.id, sibling_orbit.id) is None
        assert (
            await repository.get_deployment(deployment.id, seeded_satellite.orbit.id)
            is not None
        )

    async def test_delete_deployment_keeps_deployment_when_orbit_differs(
        self, repository: DeploymentRepository, seeded_satellite: SatelliteFixtureData
    ) -> None:
        deployment = await _create_deployment(seeded_satellite)
        sibling_orbit = await create_sibling_orbit(
            seeded_satellite.engine,
            seeded_satellite.organization.id,
            seeded_satellite.bucket_secret.id,
        )

        await repository.delete_deployment(deployment.id, sibling_orbit.id)

        assert (
            await repository.get_deployment(deployment.id, seeded_satellite.orbit.id)
            is not None
        )

        await repository.delete_deployment(deployment.id, seeded_satellite.orbit.id)

        assert (
            await repository.get_deployment(deployment.id, seeded_satellite.orbit.id)
            is None
        )

    async def test_delete_satellite_deployment_keeps_deployment_when_satellite_differs(
        self, repository: DeploymentRepository, seeded_satellite: SatelliteFixtureData
    ) -> None:
        deployment = await _create_deployment(seeded_satellite)
        foreign_satellite = await _create_satellite_in(
            seeded_satellite,
            await create_sibling_orbit(
                seeded_satellite.engine,
                seeded_satellite.organization.id,
                seeded_satellite.bucket_secret.id,
            ),
        )

        await repository.delete_satellite_deployment(
            deployment.id, foreign_satellite.id
        )

        assert (
            await repository.get_deployment(deployment.id, seeded_satellite.orbit.id)
            is not None
        )

        await repository.delete_satellite_deployment(
            deployment.id, seeded_satellite.satellite.id
        )

        assert (
            await repository.get_deployment(deployment.id, seeded_satellite.orbit.id)
            is None
        )

    async def test_get_satellite_deployment_returns_deployment_only_for_its_satellite(
        self, repository: DeploymentRepository, seeded_satellite: SatelliteFixtureData
    ) -> None:
        deployment = await _create_deployment(seeded_satellite)
        foreign_satellite = await _create_satellite_in(
            seeded_satellite,
            await create_sibling_orbit(
                seeded_satellite.engine,
                seeded_satellite.organization.id,
                seeded_satellite.bucket_secret.id,
            ),
        )

        found = await repository.get_satellite_deployment(
            deployment.id, seeded_satellite.satellite.id
        )

        assert found is not None
        assert found.id == deployment.id
        assert found.satellite_id == seeded_satellite.satellite.id
        assert (
            await repository.get_satellite_deployment(
                deployment.id, foreign_satellite.id
            )
            is None
        )
        assert (
            await repository.get_satellite_deployment(
                uuid.uuid7(), seeded_satellite.satellite.id
            )
            is None
        )

    async def test_delete_deployments_by_artifact_id_removes_artifact_deployments(
        self, repository: DeploymentRepository, seeded_satellite: SatelliteFixtureData
    ) -> None:
        for name in ["first", "second"]:
            await repository.create_deployment(
                DeploymentCreate(
                    name=name,
                    orbit_id=seeded_satellite.orbit.id,
                    satellite_id=seeded_satellite.satellite.id,
                    artifact_id=seeded_satellite.model.id,
                    status=DeploymentStatus.PENDING,
                )
            )
        assert len(await repository.list_deployments(seeded_satellite.orbit.id)) == 2

        await repository.delete_deployments_by_artifact_id(seeded_satellite.model.id)

        assert await repository.list_deployments(seeded_satellite.orbit.id) == []

    @pytest.mark.parametrize(
        "binding", ["dynamic_attributes_secrets", "env_variables_secrets"]
    )
    async def test_create_deployment_raises_not_found_for_missing_secret(
        self,
        repository: DeploymentRepository,
        seeded_satellite: SatelliteFixtureData,
        binding: str,
    ) -> None:
        existing = await OrbitSecretRepository(
            seeded_satellite.engine
        ).create_orbit_secret(
            OrbitSecretCreate(
                name="token", value="secret", orbit_id=seeded_satellite.orbit.id
            )
        )

        with pytest.raises(NotFoundError, match="Orbit secret not found"):
            await repository.create_deployment(
                DeploymentCreate(
                    name="missing-secret",
                    orbit_id=seeded_satellite.orbit.id,
                    satellite_id=seeded_satellite.satellite.id,
                    artifact_id=seeded_satellite.model.id,
                    status=DeploymentStatus.PENDING,
                    **{binding: {"A": str(existing.id), "B": str(uuid.uuid7())}},
                )
            )

        assert await repository.list_deployments(seeded_satellite.orbit.id) == []
