import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from luml.handlers.deployments import DeploymentHandler
from luml.infra.db import engine as shared_engine
from luml.infra.exceptions import InvalidStatusTransitionError
from luml.repositories.deployments import DeploymentRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.satellites import SatelliteRepository
from luml.schemas.deployment import (
    Deployment,
    DeploymentCreate,
    DeploymentDetailsUpdate,
    DeploymentDetailsUpdateIn,
    DeploymentStatus,
    DeploymentUpdate,
    MonitoringMode,
)
from luml.schemas.orbit import OrbitCreateIn, OrbitDetails
from luml.schemas.satellite import (
    Satellite,
    SatelliteCreate,
    SatelliteTaskStatus,
    SatelliteTaskType,
)

from tests.conftest import SatelliteFixtureData


async def _create_sibling_orbit(data: SatelliteFixtureData) -> OrbitDetails:
    orbit = await OrbitRepository(data.engine).create_orbit(
        data.organization.id,
        OrbitCreateIn(name="sibling orbit", bucket_secret_id=data.bucket_secret.id),
    )
    assert orbit is not None
    return orbit


async def _create_satellite_in(
    data: SatelliteFixtureData, orbit: OrbitDetails
) -> Satellite:
    return await SatelliteRepository(data.engine).create_satellite(
        SatelliteCreate(
            orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="sibling satellite"
        )
    )


@pytest_asyncio.fixture
async def deployment_handler() -> AsyncGenerator[DeploymentHandler]:
    """A handler wired to the shared engine, rebound to this test's event loop.

    DeploymentHandler holds repositories built on luml.infra.db.engine, whose
    pool would otherwise still be attached to the previous test's loop.
    """
    await shared_engine.dispose()
    yield DeploymentHandler()
    await shared_engine.dispose()


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
        name="my-deployment",
        orbit_id=orbit.id,
        satellite_id=satellite.id,
        artifact_id=model.id,
        status=DeploymentStatus.PENDING,
        created_by_user="test_user",
        tags=["test", "deployment"],
    )
    deployment, task = await repo.create_deployment(deployment_data)

    assert deployment
    assert deployment.orbit_id == deployment_data.orbit_id
    assert deployment.satellite_id == deployment_data.satellite_id
    assert deployment.artifact_id == deployment_data.artifact_id
    assert deployment.collection_id == model.collection_id
    assert deployment.status == DeploymentStatus.PENDING

    assert task
    assert task.satellite_id == deployment_data.satellite_id
    assert task.orbit_id == deployment_data.orbit_id
    assert task.type == SatelliteTaskType.DEPLOY
    assert task.payload["deployment_id"] == str(deployment.id)


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
        name="my-deployment",
        orbit_id=orbit.id,
        satellite_id=satellite.id,
        artifact_id=model.id,
        status=DeploymentStatus.PENDING,
        created_by_user="test_user",
        tags=["test", "deployment"],
    )
    deployment, _ = await repo.create_deployment(deployment_data)

    fetched_deployment = await repo.get_deployment(deployment.id, orbit.id)

    assert fetched_deployment
    assert fetched_deployment.id == deployment.id
    assert fetched_deployment.orbit_id == deployment_data.orbit_id
    assert fetched_deployment.satellite_id == deployment_data.satellite_id
    assert fetched_deployment.collection_id == model.collection_id


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
        name="my-deployment",
        orbit_id=orbit.id,
        satellite_id=satellite.id,
        artifact_id=model.id,
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
    for d in deployments:
        assert d.collection_id == model.collection_id


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
                name="my-deployment",
                orbit_id=orbit.id,
                satellite_id=satellite.id,
                artifact_id=model.id,
                status=DeploymentStatus.PENDING,
            )
        )
        deployments.append(deployment)

    all_deployments = await repo.list_satellite_deployments(satellite.id)
    ids = [d.id for d in all_deployments]
    assert len(all_deployments) == deployments_num
    assert all(dep.id in ids for dep in deployments)
    assert all(d.collection_id == model.collection_id for d in all_deployments)


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
        name="my-deployment",
        orbit_id=orbit.id,
        satellite_id=satellite.id,
        artifact_id=model.id,
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
    assert updated_deployment.collection_id == model.collection_id


@pytest.mark.asyncio
async def test_partial_deployment_update_preserves_omitted_fields_and_clears_null(
    create_satellite: SatelliteFixtureData,
) -> None:
    data = create_satellite
    repo = DeploymentRepository(data.engine)
    created, _ = await repo.create_deployment(
        DeploymentCreate(
            name="monitored-deployment",
            orbit_id=data.orbit.id,
            satellite_id=data.satellite.id,
            artifact_id=data.model.id,
            status=DeploymentStatus.PENDING,
        )
    )
    inference_url = f"https://inference-{uuid.uuid4()}.example/api"
    await repo.update_deployment(
        created.id,
        data.satellite.id,
        DeploymentUpdate(
            id=created.id,
            inference_url=inference_url,
            status=DeploymentStatus.ACTIVE,
        ),
    )

    monitored = await repo.update_deployment(
        created.id,
        data.satellite.id,
        DeploymentUpdate(
            id=created.id,
            monitoring_url=f"/deployments/{created.id}/monitoring",
        ),
    )

    assert monitored is not None
    assert monitored.monitoring_url == f"/deployments/{created.id}/monitoring"
    assert monitored.inference_url == inference_url
    assert monitored.status == DeploymentStatus.ACTIVE

    cleared = await repo.update_deployment(
        created.id,
        data.satellite.id,
        DeploymentUpdate(id=created.id, monitoring_url=None),
    )

    assert cleared is not None
    assert cleared.monitoring_url is None
    assert cleared.inference_url == inference_url
    assert cleared.status == DeploymentStatus.ACTIVE


@pytest.mark.asyncio
async def test_update_deployment_with_only_status_set_keeps_the_rest(
    create_satellite: SatelliteFixtureData,
) -> None:
    """A status-only update must not erase routing metadata.

    Reconciliation on the Satellite flips deployment statuses without resending
    inference_url, schemas or tags; only the fields actually marked as set may reach
    the row, or every such flip would strip an active deployment of its routing.
    """
    data = create_satellite
    repo = DeploymentRepository(data.engine)

    created, _ = await repo.create_deployment(
        DeploymentCreate(
            name="my-deployment",
            orbit_id=data.orbit.id,
            satellite_id=data.satellite.id,
            artifact_id=data.model.id,
            status=DeploymentStatus.PENDING,
            tags=["routed"],
        )
    )
    inference_url = f"https://test-inference{uuid.uuid4()}.com/api"
    await repo.update_deployment(
        created.id,
        data.satellite.id,
        DeploymentUpdate(
            id=created.id,
            inference_url=inference_url,
            schemas={"openapi": "3.0.0"},
            status=DeploymentStatus.ACTIVE,
        ),
    )

    updated = await repo.update_deployment(
        created.id,
        data.satellite.id,
        DeploymentUpdate(id=created.id, status=DeploymentStatus.NOT_RESPONDING),
    )

    assert updated
    assert updated.status == DeploymentStatus.NOT_RESPONDING
    assert updated.inference_url == inference_url
    assert updated.schemas == {"openapi": "3.0.0"}
    assert updated.tags == ["routed"]


@pytest.mark.asyncio
async def test_update_deployment_cannot_pull_a_deployment_out_of_deletion(
    create_satellite: SatelliteFixtureData,
) -> None:
    """A stale worker write must not cancel a deletion in progress.

    Satellite recovery can wait half an hour before promoting a deployment to active;
    a deletion requested during that wait must win, or the undeploy task removes the
    container and then finds a status it refuses to delete.
    """
    data = create_satellite
    repo = DeploymentRepository(data.engine)

    created, _ = await repo.create_deployment(
        DeploymentCreate(
            name="my-deployment",
            orbit_id=data.orbit.id,
            satellite_id=data.satellite.id,
            artifact_id=data.model.id,
            status=DeploymentStatus.PENDING,
        )
    )
    await repo.update_deployment(
        created.id,
        data.satellite.id,
        DeploymentUpdate(id=created.id, status=DeploymentStatus.DELETION_PENDING),
    )

    with pytest.raises(InvalidStatusTransitionError):
        await repo.update_deployment(
            created.id,
            data.satellite.id,
            DeploymentUpdate(id=created.id, status=DeploymentStatus.ACTIVE),
        )

    # writes within the deletion family still land: the undeploy task reports
    # its failure
    updated = await repo.update_deployment(
        created.id,
        data.satellite.id,
        DeploymentUpdate(
            id=created.id,
            status=DeploymentStatus.DELETION_FAILED,
            error_message={"reason": "x", "error": "y"},
        ),
    )
    assert updated
    assert updated.status == DeploymentStatus.DELETION_FAILED


@pytest.mark.asyncio
async def test_update_deployment_rejects_an_explicit_null_status(
    create_satellite: SatelliteFixtureData,
) -> None:
    """An explicit null is not "leave it alone" — and must not become a 500.

    The status column is NOT NULL; without the guard an explicit null sailed past
    the deletion check and blew up as an IntegrityError inside the locked
    transaction.
    """
    data = create_satellite
    repo = DeploymentRepository(data.engine)

    created, _ = await repo.create_deployment(
        DeploymentCreate(
            name="my-deployment",
            orbit_id=data.orbit.id,
            satellite_id=data.satellite.id,
            artifact_id=data.model.id,
            status=DeploymentStatus.PENDING,
        )
    )

    with pytest.raises(InvalidStatusTransitionError):
        await repo.update_deployment(
            created.id,
            data.satellite.id,
            DeploymentUpdate(id=created.id, status=None),
        )

    unchanged = await repo.get_deployment(created.id, data.orbit.id)
    assert unchanged
    assert unchanged.status == DeploymentStatus.PENDING


@pytest.mark.asyncio
async def test_update_deployment_details(
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

    created_deployment, _ = await repo.create_deployment(
        DeploymentCreate(
            name="my-deployment",
            orbit_id=orbit.id,
            satellite_id=satellite.id,
            artifact_id=model.id,
            status=DeploymentStatus.PENDING,
            tags=["original"],
        )
    )

    details = DeploymentDetailsUpdate(
        name="my-deployment",
        description="some desc",
        dynamic_attributes_secrets={"token": str(uuid.uuid7())},
        tags=["one", "two"],
    )

    updated = await repo.update_deployment_details(
        orbit.id, created_deployment.id, details
    )

    assert updated is not None
    assert updated.id == created_deployment.id
    assert updated.name == details.name
    assert updated.description == details.description
    assert updated.dynamic_attributes_secrets == details.dynamic_attributes_secrets
    assert updated.tags == details.tags
    assert updated.collection_id == model.collection_id


@pytest.mark.asyncio
async def test_update_monitoring_mode_enqueues_reconcile(
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
    sat_repo = SatelliteRepository(engine)

    created, _ = await repo.create_deployment(
        DeploymentCreate(
            name="my-deployment",
            orbit_id=orbit.id,
            satellite_id=satellite.id,
            artifact_id=model.id,
            monitoring_mode=MonitoringMode.OFF,
        )
    )

    updated = await repo.update_deployment_details(
        orbit.id,
        created.id,
        DeploymentDetailsUpdate(monitoring_mode=MonitoringMode.FULL),
    )

    assert updated is not None
    assert updated.monitoring_mode == MonitoringMode.FULL

    tasks = await sat_repo.list_tasks(satellite.id)
    reconcile_tasks = [t for t in tasks if t.type == SatelliteTaskType.RECONCILE]
    assert len(reconcile_tasks) == 1
    assert reconcile_tasks[0].payload["deployment_id"] == str(created.id)


@pytest.mark.asyncio
async def test_update_details_without_mode_change_no_reconcile(
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
    sat_repo = SatelliteRepository(engine)

    created, _ = await repo.create_deployment(
        DeploymentCreate(
            name="my-deployment",
            orbit_id=orbit.id,
            satellite_id=satellite.id,
            artifact_id=model.id,
            monitoring_mode=MonitoringMode.FULL,
        )
    )

    # Same mode + unrelated field change must not enqueue a reconcile task.
    await repo.update_deployment_details(
        orbit.id,
        created.id,
        DeploymentDetailsUpdate(description="new", monitoring_mode=MonitoringMode.FULL),
    )

    tasks = await sat_repo.list_tasks(satellite.id)
    assert [t for t in tasks if t.type == SatelliteTaskType.RECONCILE] == []


@pytest.mark.asyncio
async def test_request_deployment_deletion(
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

    created, _ = await repo.create_deployment(
        DeploymentCreate(
            name="my-deployment",
            orbit_id=orbit.id,
            satellite_id=satellite.id,
            artifact_id=model.id,
            status=DeploymentStatus.PENDING,
        )
    )

    result = await repo.request_deployment_deletion(orbit.id, created.id)
    assert result is not None
    dep, task = result
    assert dep.status == DeploymentStatus.DELETION_PENDING
    assert dep.collection_id == model.collection_id
    assert task is not None
    assert task.type == SatelliteTaskType.UNDEPLOY
    assert task.payload["deployment_id"] == str(created.id)

    result2 = await repo.request_deployment_deletion(orbit.id, created.id)
    assert result2 is not None
    dep2, task2 = result2
    assert dep2.status == DeploymentStatus.DELETION_PENDING
    assert task2 is None


@pytest.mark.asyncio
async def test_enqueue_undeploy_task(create_satellite: SatelliteFixtureData) -> None:
    data = create_satellite
    engine, orbit, model, satellite = (
        data.engine,
        data.orbit,
        data.model,
        data.satellite,
    )
    repo = DeploymentRepository(engine)

    deployment, _ = await repo.create_deployment(
        DeploymentCreate(
            name="my-deployment",
            orbit_id=orbit.id,
            satellite_id=satellite.id,
            artifact_id=model.id,
            status=DeploymentStatus.ACTIVE,
        )
    )

    task = await repo.enqueue_undeploy_task(deployment.id)
    assert task is not None
    assert task.type == SatelliteTaskType.UNDEPLOY
    assert task.payload["deployment_id"] == str(deployment.id)
    assert task.status == SatelliteTaskStatus.PENDING

    duplicate_task = await repo.enqueue_undeploy_task(deployment.id)
    assert duplicate_task is not None
    assert duplicate_task.id == task.id


@pytest.mark.asyncio
async def test_get_deployment_from_another_orbit(
    create_satellite: SatelliteFixtureData,
) -> None:
    data = create_satellite
    repo = DeploymentRepository(data.engine)
    deployment = await _create_deployment(data)
    sibling_orbit = await _create_sibling_orbit(data)

    assert await repo.get_deployment(deployment.id, sibling_orbit.id) is None
    assert await repo.get_deployment(deployment.id, data.orbit.id) is not None


@pytest.mark.asyncio
async def test_delete_deployment_from_another_orbit(
    create_satellite: SatelliteFixtureData,
) -> None:
    data = create_satellite
    repo = DeploymentRepository(data.engine)
    deployment = await _create_deployment(data)
    sibling_orbit = await _create_sibling_orbit(data)

    await repo.delete_deployment(deployment.id, sibling_orbit.id)

    assert await repo.get_deployment(deployment.id, data.orbit.id) is not None

    await repo.delete_deployment(deployment.id, data.orbit.id)

    assert await repo.get_deployment(deployment.id, data.orbit.id) is None


@pytest.mark.asyncio
async def test_delete_satellite_deployment_from_another_satellite(
    create_satellite: SatelliteFixtureData,
) -> None:
    data = create_satellite
    repo = DeploymentRepository(data.engine)
    deployment = await _create_deployment(data)
    foreign_satellite = await _create_satellite_in(
        data, await _create_sibling_orbit(data)
    )

    await repo.delete_satellite_deployment(deployment.id, foreign_satellite.id)

    assert await repo.get_deployment(deployment.id, data.orbit.id) is not None

    await repo.delete_satellite_deployment(deployment.id, data.satellite.id)

    assert await repo.get_deployment(deployment.id, data.orbit.id) is None


@pytest.mark.asyncio
async def test_get_satellite_deployment(
    create_satellite: SatelliteFixtureData,
) -> None:
    data = create_satellite
    repo = DeploymentRepository(data.engine)
    deployment = await _create_deployment(data)
    foreign_satellite = await _create_satellite_in(
        data, await _create_sibling_orbit(data)
    )

    found = await repo.get_satellite_deployment(deployment.id, data.satellite.id)

    assert found is not None
    assert found.id == deployment.id
    assert found.satellite_id == data.satellite.id
    assert (
        await repo.get_satellite_deployment(deployment.id, foreign_satellite.id) is None
    )
    assert await repo.get_satellite_deployment(uuid.uuid7(), data.satellite.id) is None


@pytest.mark.asyncio
async def test_operations_on_an_unknown_deployment_return_none(
    create_satellite: SatelliteFixtureData,
) -> None:
    data = create_satellite
    repo = DeploymentRepository(data.engine)
    missing_id = uuid.uuid7()

    assert (
        await repo.update_deployment(
            missing_id,
            data.satellite.id,
            DeploymentUpdate(id=missing_id, status=DeploymentStatus.ACTIVE),
        )
        is None
    )
    assert await repo.request_deployment_deletion(data.orbit.id, missing_id) is None
    assert (
        await repo.update_deployment_details(
            data.orbit.id, missing_id, DeploymentDetailsUpdate(name="renamed")
        )
        is None
    )
    assert await repo.enqueue_undeploy_task(missing_id) is None


@pytest.mark.asyncio
async def test_delete_deployments_by_artifact_id(
    create_satellite: SatelliteFixtureData,
) -> None:
    data = create_satellite
    repo = DeploymentRepository(data.engine)
    for name in ["first", "second"]:
        await repo.create_deployment(
            DeploymentCreate(
                name=name,
                orbit_id=data.orbit.id,
                satellite_id=data.satellite.id,
                artifact_id=data.model.id,
                status=DeploymentStatus.PENDING,
            )
        )
    assert len(await repo.list_deployments(data.orbit.id)) == 2

    await repo.delete_deployments_by_artifact_id(data.model.id)

    assert await repo.list_deployments(data.orbit.id) == []


@patch(
    "luml.handlers.deployments.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_partial_details_update_preserves_untouched_columns(
    mock_check_permissions: AsyncMock,  # noqa: ARG001
    create_satellite: SatelliteFixtureData,
    deployment_handler: DeploymentHandler,
) -> None:
    """A PATCH carrying one field must leave every other column as it was.

    This goes through the handler and back out of the database, because the bug
    it guards against lived in the handler's conversion and only became visible
    once the row was written and read again.
    """
    data = create_satellite
    repo = DeploymentRepository(data.engine)
    secret_id = str(uuid.uuid7())

    created, _ = await repo.create_deployment(
        DeploymentCreate(
            name="original",
            orbit_id=data.orbit.id,
            satellite_id=data.satellite.id,
            artifact_id=data.model.id,
            status=DeploymentStatus.PENDING,
            description="keep me",
            tags=["keep"],
            dynamic_attributes_secrets={"token": secret_id},
            env_variables={"LEVEL": "debug"},
        )
    )

    await deployment_handler.update_deployment_details(
        data.user.id,
        data.organization.id,
        data.orbit.id,
        created.id,
        DeploymentDetailsUpdateIn(name="renamed"),
    )

    reloaded = await repo.get_deployment(created.id, data.orbit.id)
    assert reloaded is not None
    assert reloaded.name == "renamed"
    assert reloaded.description == "keep me"
    assert reloaded.tags == ["keep"]
    assert reloaded.dynamic_attributes_secrets == {"token": secret_id}
    assert reloaded.env_variables == {"LEVEL": "debug"}


@patch(
    "luml.handlers.deployments.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_details_update_treats_explicit_null_secrets_as_cleared(
    mock_check_permissions: AsyncMock,  # noqa: ARG001
    create_satellite: SatelliteFixtureData,
    deployment_handler: DeploymentHandler,
) -> None:
    """An explicit null for a NOT NULL column clears it instead of erroring."""
    data = create_satellite
    repo = DeploymentRepository(data.engine)

    created, _ = await repo.create_deployment(
        DeploymentCreate(
            name="original",
            orbit_id=data.orbit.id,
            satellite_id=data.satellite.id,
            artifact_id=data.model.id,
            status=DeploymentStatus.PENDING,
            dynamic_attributes_secrets={"token": str(uuid.uuid7())},
        )
    )

    await deployment_handler.update_deployment_details(
        data.user.id,
        data.organization.id,
        data.orbit.id,
        created.id,
        DeploymentDetailsUpdateIn.model_validate({"dynamic_attributes_secrets": None}),
    )

    reloaded = await repo.get_deployment(created.id, data.orbit.id)
    assert reloaded is not None
    assert reloaded.dynamic_attributes_secrets == {}
