import uuid

import pytest

from dataforce_studio.repositories.deployments import DeploymentRepository
from dataforce_studio.schemas.deployment import (
    DeploymentCreate,
    DeploymentStatus,
    DeploymentUpdate,
)
from dataforce_studio.schemas.satellite import (
    SatelliteTaskType,
)
from tests.conftest import SatelliteFixtureData


@pytest.mark.asyncio
async def test_create_deployment(create_satellite: SatelliteFixtureData) -> None:
    data = create_satellite
    engine, orbit, model, satellite = (
        data.engine,
        data.orbit,
        data.model,
        data.satellite,
    )
    repo = DeploymentRepository(engine)

    deployment_data = DeploymentCreate(
        orbit_id=orbit.id,
        satellite_id=satellite.id,
        model_id=model.id,
        secrets={"api_key": 123},
        status=DeploymentStatus.PENDING,
        created_by_user="test_user",
        tags=["test", "deployment"],
    )
    deployment, task = await repo.create_deployment(deployment_data)

    assert deployment
    assert deployment.orbit_id == deployment_data.orbit_id
    assert deployment.satellite_id == deployment_data.satellite_id
    assert deployment.model_id == deployment_data.model_id
    assert deployment.status == DeploymentStatus.PENDING
    assert deployment.secrets == deployment_data.secrets

    assert task
    assert task.satellite_id == deployment_data.satellite_id
    assert task.orbit_id == deployment_data.orbit_id
    assert task.type == SatelliteTaskType.DEPLOY
    assert task.payload["deployment_id"] == deployment.id
    assert task.payload["model_id"] == deployment_data.model_id


@pytest.mark.asyncio
async def test_get_deployment(create_satellite: SatelliteFixtureData) -> None:
    data = create_satellite
    engine, orbit, model, satellite = (
        data.engine,
        data.orbit,
        data.model,
        data.satellite,
    )
    repo = DeploymentRepository(engine)

    deployment_data = DeploymentCreate(
        orbit_id=orbit.id,
        satellite_id=satellite.id,
        model_id=model.id,
        secrets={"api_key": 123},
        status=DeploymentStatus.PENDING,
        created_by_user="test_user",
        tags=["test", "deployment"],
    )
    deployment, _ = await repo.create_deployment(deployment_data)

    fetched_deployment = await repo.get_deployment(deployment.id)

    assert fetched_deployment
    assert fetched_deployment.id == deployment.id
    assert fetched_deployment.orbit_id == deployment_data.orbit_id
    assert fetched_deployment.satellite_id == deployment_data.satellite_id


@pytest.mark.asyncio
async def test_list_deployments(create_satellite: SatelliteFixtureData) -> None:
    data = create_satellite
    engine, orbit, model, satellite = (
        data.engine,
        data.orbit,
        data.model,
        data.satellite,
    )
    repo = DeploymentRepository(engine)

    deployment_data = DeploymentCreate(
        orbit_id=orbit.id,
        satellite_id=satellite.id,
        model_id=model.id,
        secrets={"api_key": 123},
        status=DeploymentStatus.PENDING,
        created_by_user="test_user",
        tags=["test", "deployment"],
    )

    created_dep1, _ = await repo.create_deployment(deployment_data)

    deployment_data.status = DeploymentStatus.ACTIVE
    created_dep2, _ = await repo.create_deployment(deployment_data)

    deployments = await repo.list_deployments(orbit.id)

    assert len(deployments) == 2
    deployment_ids = [d.id for d in deployments]
    assert created_dep1.id in deployment_ids
    assert created_dep2.id in deployment_ids


@pytest.mark.asyncio
async def test_list_satellite_deployments(
    create_satellite: SatelliteFixtureData,
) -> None:
    data = create_satellite
    engine, orbit, model, satellite = (
        data.engine,
        data.orbit,
        data.model,
        data.satellite,
    )
    repo = DeploymentRepository(engine)
    deployments_num = 4
    deployments = []

    for _ in range(deployments_num):
        deployment, _ = await repo.create_deployment(
            DeploymentCreate(
                orbit_id=orbit.id,
                satellite_id=satellite.id,
                model_id=model.id,
                status=DeploymentStatus.PENDING,
            )
        )
        deployments.append(deployment)

    all_deployments = await repo.list_satellite_deployments(satellite.id)
    ids = [d.id for d in all_deployments]
    assert len(all_deployments) == deployments_num
    assert all(dep.id in ids for dep in deployments)


@pytest.mark.asyncio
async def test_update_deployment(create_satellite: SatelliteFixtureData) -> None:
    data = create_satellite
    engine, orbit, model, satellite = (
        data.engine,
        data.orbit,
        data.model,
        data.satellite,
    )
    repo = DeploymentRepository(engine)

    deployment_data = DeploymentCreate(
        orbit_id=orbit.id,
        satellite_id=satellite.id,
        model_id=model.id,
        status=DeploymentStatus.PENDING,
        tags=["original"],
    )
    created_deployment, _ = await repo.create_deployment(deployment_data)

    update_data = DeploymentUpdate(
        id=created_deployment.id,
        inference_url=f"https://test-inference{uuid.uuid4()}.com/api",
        status=DeploymentStatus.ACTIVE,
        tags=["updated", "active"],
    )
    updated_deployment = await repo.update_deployment(
        created_deployment.id, satellite.id, update_data
    )

    assert updated_deployment
    assert updated_deployment.id == created_deployment.id
    assert updated_deployment.inference_url == update_data.inference_url
    assert updated_deployment.status == update_data.status
    assert updated_deployment.tags == update_data.tags
