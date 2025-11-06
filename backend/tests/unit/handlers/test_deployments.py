import datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest
import uuid6
from fastapi import status

from dataforce_studio.handlers.deployments import DeploymentHandler
from dataforce_studio.infra.exceptions import (
    ApplicationError,
    InsufficientPermissionsError,
    NotFoundError,
)
from dataforce_studio.schemas.deployment import (
    Deployment,
    DeploymentCreate,
    DeploymentCreateIn,
    DeploymentDetailsUpdate,
    DeploymentDetailsUpdateIn,
    DeploymentStatus,
    DeploymentUpdate,
    DeploymentUpdateIn,
)
from dataforce_studio.schemas.permissions import Action, Resource
from dataforce_studio.schemas.satellite import (
    SatelliteQueueTask,
    SatelliteTaskStatus,
    SatelliteTaskType,
)

handler = DeploymentHandler()


@patch(
    "dataforce_studio.handlers.deployments.DeploymentRepository.create_deployment",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.UserRepository.get_public_user_by_id",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.ModelArtifactRepository.get_model_artifact",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbit_secrets.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_deployment(
    mock_check_orbit_action_access: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_satellite: AsyncMock,
    mock_get_model_artifact: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_public_user_by_id: AsyncMock,
    mock_create_deployment: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    deployment_id = UUID("0199c337-09f7-751e-add2-d952f0d6cf4e")
    satellite_id = UUID("0199c337-09f9-706e-9b80-58939d5fba79")
    model_artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    user_name = "User Full Name"

    deployment_create_data_in = DeploymentCreateIn(
        name="my-deployment",
        satellite_id=satellite_id,
        model_artifact_id=model_artifact_id,
        tags=["tag"],
    )
    deployment_create_data = DeploymentCreate(
        name="my-deployment",
        orbit_id=orbit_id,
        satellite_id=satellite_id,
        model_id=model_artifact_id,
        tags=deployment_create_data_in.tags,
        created_by_user=user_name,
    )
    expected = Deployment(
        id=deployment_id,
        orbit_id=orbit_id,
        satellite_id=satellite_id,
        satellite_name="Satellite 1",
        name="my-deployment",
        model_id=model_artifact_id,
        model_artifact_name="Model Artifact 1",
        collection_id=collection_id,
        inference_url=None,
        status=DeploymentStatus.PENDING,
        created_by_user=user_name,
        tags=deployment_create_data_in.tags,
        created_at=datetime.datetime.now(),
        updated_at=None,
    )

    mock_get_orbit_simple.return_value = Mock()
    mock_get_satellite.return_value = Mock(orbit_id=orbit_id)
    mock_get_model_artifact.return_value = Mock(collection_id=collection_id)
    mock_get_collection.return_value = Mock(orbit_id=orbit_id)
    mock_get_public_user_by_id.return_value = Mock(full_name=user_name)
    mock_create_deployment.return_value = expected, None

    created_secret = await handler.create_deployment(
        user_id, organization_id, orbit_id, deployment_create_data_in
    )

    assert created_secret == expected

    mock_create_deployment.assert_awaited_once_with(deployment_create_data)
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_satellite.assert_awaited_once_with(deployment_create_data_in.satellite_id)
    mock_get_model_artifact.assert_awaited_once_with(
        deployment_create_data_in.model_artifact_id
    )
    mock_get_collection.assert_awaited_once_with(collection_id)
    mock_get_public_user_by_id.assert_awaited_once_with(user_id)
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id,
        orbit_id,
        user_id,
        Resource.DEPLOYMENT,
        Action.CREATE,
    )


@patch(
    "dataforce_studio.handlers.deployments.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbit_secrets.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_deployment_orbit_not_found(
    mock_check_orbit_action_access: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c337-09f9-706e-9b80-58939d5fba79")
    model_artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    deployment_create_data_in = DeploymentCreateIn(
        name="my-deployment",
        satellite_id=satellite_id,
        model_artifact_id=model_artifact_id,
        tags=["tag"],
    )

    mock_get_orbit_simple.return_value = None

    with pytest.raises(NotFoundError, match="Orbit not found") as error:
        await handler.create_deployment(
            user_id, organization_id, orbit_id, deployment_create_data_in
        )

    assert error.value.status_code == 404
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id,
        orbit_id,
        user_id,
        Resource.DEPLOYMENT,
        Action.CREATE,
    )


@patch(
    "dataforce_studio.handlers.deployments.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbit_secrets.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_deployment_satellite_not_found(
    mock_check_orbit_action_access: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c337-09f9-706e-9b80-58939d5fba79")
    model_artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    deployment_create_data_in = DeploymentCreateIn(
        name="my-deployment",
        satellite_id=satellite_id,
        model_artifact_id=model_artifact_id,
        tags=["tag"],
    )

    mock_get_orbit_simple.return_value = Mock()
    mock_get_satellite.return_value = None

    with pytest.raises(NotFoundError, match="Satellite not found") as error:
        await handler.create_deployment(
            user_id, organization_id, orbit_id, deployment_create_data_in
        )

    assert error.value.status_code == 404
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_satellite.assert_awaited_once_with(deployment_create_data_in.satellite_id)
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id,
        orbit_id,
        user_id,
        Resource.DEPLOYMENT,
        Action.CREATE,
    )


@patch(
    "dataforce_studio.handlers.deployments.ModelArtifactRepository.get_model_artifact",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbit_secrets.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_deployment_model_artifact_not_found(
    mock_check_orbit_action_access: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_satellite: AsyncMock,
    mock_get_model_artifact: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c337-09f9-706e-9b80-58939d5fba79")
    model_artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    deployment_create_data_in = DeploymentCreateIn(
        name="my-deployment",
        satellite_id=satellite_id,
        model_artifact_id=model_artifact_id,
        tags=["tag"],
    )

    mock_get_orbit_simple.return_value = Mock()
    mock_get_satellite.return_value = Mock(orbit_id=orbit_id)
    mock_get_model_artifact.return_value = None

    with pytest.raises(NotFoundError, match="Model artifact not found") as error:
        await handler.create_deployment(
            user_id, organization_id, orbit_id, deployment_create_data_in
        )

    assert error.value.status_code == 404
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_satellite.assert_awaited_once_with(deployment_create_data_in.satellite_id)
    mock_get_model_artifact.assert_awaited_once_with(model_artifact_id)
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id,
        orbit_id,
        user_id,
        Resource.DEPLOYMENT,
        Action.CREATE,
    )


@patch(
    "dataforce_studio.handlers.deployments.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.ModelArtifactRepository.get_model_artifact",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbit_secrets.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_deployment_collection_not_found(
    mock_check_orbit_action_access: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_satellite: AsyncMock,
    mock_get_model_artifact: AsyncMock,
    mock_get_collection: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    satellite_id = UUID("0199c337-09f9-706e-9b80-58939d5fba79")
    model_artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    deployment_create_data_in = DeploymentCreateIn(
        name="my-deployment",
        satellite_id=satellite_id,
        model_artifact_id=model_artifact_id,
        tags=["tag"],
    )
    mock_get_orbit_simple.return_value = Mock()
    mock_get_satellite.return_value = Mock(orbit_id=orbit_id)
    mock_get_model_artifact.return_value = Mock(collection_id=collection_id)
    mock_get_collection.return_value = None

    with pytest.raises(NotFoundError, match="Collection not found") as error:
        await handler.create_deployment(
            user_id, organization_id, orbit_id, deployment_create_data_in
        )

    assert error.value.status_code == 404
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_satellite.assert_awaited_once_with(deployment_create_data_in.satellite_id)
    mock_get_model_artifact.assert_awaited_once_with(model_artifact_id)
    mock_get_collection.assert_awaited_once_with(collection_id)
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id,
        orbit_id,
        user_id,
        Resource.DEPLOYMENT,
        Action.CREATE,
    )


@patch(
    "dataforce_studio.handlers.deployments.UserRepository.get_public_user_by_id",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.ModelArtifactRepository.get_model_artifact",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbit_secrets.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_deployment_user_not_found(
    mock_check_orbit_action_access: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_satellite: AsyncMock,
    mock_get_model_artifact: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_public_user_by_id: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    satellite_id = UUID("0199c337-09f9-706e-9b80-58939d5fba79")
    model_artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    deployment_create_data_in = DeploymentCreateIn(
        name="my-deployment",
        satellite_id=satellite_id,
        model_artifact_id=model_artifact_id,
        tags=["tag"],
    )

    mock_get_orbit_simple.return_value = Mock()
    mock_get_satellite.return_value = Mock(orbit_id=orbit_id)
    mock_get_model_artifact.return_value = Mock(collection_id=collection_id)
    mock_get_collection.return_value = Mock(orbit_id=orbit_id)
    mock_get_public_user_by_id.return_value = None

    with pytest.raises(NotFoundError, match="User not found") as error:
        await handler.create_deployment(
            user_id, organization_id, orbit_id, deployment_create_data_in
        )

    assert error.value.status_code == 404
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_satellite.assert_awaited_once_with(deployment_create_data_in.satellite_id)
    mock_get_model_artifact.assert_awaited_once_with(model_artifact_id)
    mock_get_collection.assert_awaited_once_with(collection_id)
    mock_get_public_user_by_id.assert_awaited_once_with(user_id)
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id,
        orbit_id,
        user_id,
        Resource.DEPLOYMENT,
        Action.CREATE,
    )


@patch(
    "dataforce_studio.handlers.deployments.DeploymentRepository.list_deployments",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_deployments(
    mock_check_orbit_action_access: AsyncMock,
    mock_list_deployments: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    deployment_id = UUID("0199c337-09f7-751e-add2-d952f0d6cf4e")
    satellite_id = UUID("0199c337-09f9-706e-9b80-58939d5fba79")
    model_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    expected = [
        Deployment(
            id=deployment_id,
            orbit_id=orbit_id,
            satellite_id=satellite_id,
            satellite_name="Satellite 1",
            name="deployment-1",
            model_id=model_id,
            model_artifact_name="Model Artifact 1",
            collection_id=collection_id,
            status=DeploymentStatus.ACTIVE,
            created_by_user="John Doe",
            created_at=datetime.datetime.now(),
            updated_at=None,
        )
    ]

    mock_list_deployments.return_value = expected

    result = await handler.list_deployments(user_id, organization_id, orbit_id)

    assert result == expected
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.DEPLOYMENT, Action.LIST
    )
    mock_list_deployments.assert_awaited_once_with(orbit_id)


@patch(
    "dataforce_studio.handlers.deployments.DeploymentRepository.get_deployment",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_deployment(
    mock_check_orbit_action_access: AsyncMock,
    mock_get_deployment: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    deployment_id = UUID("0199c337-09f7-751e-add2-d952f0d6cf4e")
    satellite_id = UUID("0199c337-09f9-706e-9b80-58939d5fba79")
    model_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    expected = Deployment(
        id=deployment_id,
        orbit_id=orbit_id,
        satellite_id=satellite_id,
        satellite_name="Satellite 1",
        name="deployment-1",
        model_id=model_id,
        model_artifact_name="Model Artifact 1",
        collection_id=collection_id,
        status=DeploymentStatus.ACTIVE,
        created_by_user="John Doe",
        created_at=datetime.datetime.now(),
        updated_at=None,
    )

    mock_check_orbit_action_access.return_value = None
    mock_get_deployment.return_value = expected

    result = await handler.get_deployment(
        user_id, organization_id, orbit_id, deployment_id
    )

    assert result == expected
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.DEPLOYMENT, Action.READ
    )


@patch(
    "dataforce_studio.handlers.deployments.DeploymentRepository.request_deployment_deletion",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_deployment(
    mock_check_orbit_action_access: AsyncMock,
    mock_request_deletion: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    deployment_id = UUID("0199c337-09f7-751e-add2-d952f0d6cf4e")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    satellite_id = UUID("0199c337-09f9-706e-9b80-58939d5fba79")
    model_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")
    task_id = UUID("0199c337-0a01-7f32-9a65-9c3df0dc4cb2")
    now = datetime.datetime.now()

    deployment = Deployment(
        id=deployment_id,
        orbit_id=orbit_id,
        satellite_id=satellite_id,
        satellite_name="Satellite 1",
        name="deployment-1",
        model_id=model_id,
        model_artifact_name="Model Artifact 1",
        collection_id=collection_id,
        status=DeploymentStatus.ACTIVE,
        created_by_user="John",
        created_at=now,
        updated_at=now,
    )
    task = SatelliteQueueTask(
        id=task_id,
        satellite_id=deployment.satellite_id,
        orbit_id=orbit_id,
        type=SatelliteTaskType.UNDEPLOY,
        payload={"deployment_id": deployment_id},
        status=SatelliteTaskStatus.PENDING,
        scheduled_at=now,
        started_at=None,
        finished_at=None,
        result=None,
        created_at=now,
        updated_at=None,
    )

    mock_request_deletion.return_value = (deployment, task)

    result = await handler.request_deployment_deletion(
        user_id, organization_id, orbit_id, deployment_id
    )

    assert result == task
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.DEPLOYMENT, Action.DELETE
    )
    mock_request_deletion.assert_awaited_once_with(orbit_id, deployment_id)


@patch(
    "dataforce_studio.handlers.deployments.DeploymentRepository.request_deployment_deletion",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_deployment_not_found(
    mock_check_orbit_action_access: AsyncMock,
    mock_request_deletion: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    deployment_id = UUID("0199c337-09f7-751e-add2-d952f0d6cf4e")

    mock_request_deletion.return_value = None

    with pytest.raises(NotFoundError, match="Deployment not found"):
        await handler.request_deployment_deletion(
            user_id, organization_id, orbit_id, deployment_id
        )

    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.DEPLOYMENT, Action.DELETE
    )
    mock_request_deletion.assert_awaited_once_with(orbit_id, deployment_id)


@patch(
    "dataforce_studio.handlers.deployments.DeploymentRepository.request_deployment_deletion",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_deployment_already_pending(
    mock_check_orbit_action_access: AsyncMock,
    mock_request_deletion: AsyncMock,
) -> None:
    now = datetime.datetime.now()
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    deployment_id = UUID("0199c337-09f7-751e-add2-d952f0d6cf4e")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    satellite_id = UUID("0199c337-09f9-706e-9b80-58939d5fba79")
    model_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")
    deployment = Deployment(
        id=deployment_id,
        orbit_id=orbit_id,
        satellite_id=satellite_id,
        satellite_name="Satellite 1",
        name="deployment-1",
        model_id=model_id,
        model_artifact_name="Model Artifact 1",
        collection_id=collection_id,
        status=DeploymentStatus.DELETION_PENDING,
        created_by_user="User",
        created_at=now,
        updated_at=now,
    )
    mock_request_deletion.return_value = (deployment, None)

    with pytest.raises(
        ApplicationError, match="Deployment deletion already pending"
    ) as exc:
        await handler.request_deployment_deletion(
            user_id, organization_id, orbit_id, deployment_id
        )

    assert exc.value.status_code == status.HTTP_409_CONFLICT
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.DEPLOYMENT, Action.DELETE
    )
    mock_request_deletion.assert_awaited_once_with(orbit_id, deployment_id)


@patch(
    "dataforce_studio.handlers.deployments.DeploymentRepository.get_deployment",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.DeploymentRepository.delete_deployment",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_worker_deployment(
    mock_delete_deployment: AsyncMock,
    mock_get_deployment: AsyncMock,
) -> None:
    datetime.datetime.now()
    UUID("0199c337-09f9-706e-9b80-58939d5fba79")
    deployment_id = UUID("0199c337-09f7-751e-add2-d952f0d6cf4e")
    UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")
    UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_get_deployment.return_value = Mock(
        id=deployment_id,
        status=DeploymentStatus.DELETION_PENDING,
    )
    mock_delete_deployment.return_value = None

    await handler.delete_worker_deployment(deployment_id)

    mock_delete_deployment.assert_awaited_once_with(deployment_id)
    mock_get_deployment.assert_awaited_once_with(deployment_id)


@patch(
    "dataforce_studio.handlers.deployments.DeploymentRepository.get_deployment",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_worker_deployment_not_found(
    mock_get_deployment: AsyncMock,
) -> None:
    UUID("0199c337-09f9-706e-9b80-58939d5fba79")
    deployment_id = UUID("0199c337-09f7-751e-add2-d952f0d6cf4e")
    mock_get_deployment.return_value = None

    with pytest.raises(NotFoundError, match="Deployment not found"):
        await handler.delete_worker_deployment(deployment_id)

    mock_get_deployment.assert_awaited_once_with(deployment_id)


@patch(
    "dataforce_studio.handlers.deployments.DeploymentRepository.get_deployment",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_deployment_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_deployment: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    deployment_id = UUID("0199c337-09f7-751e-add2-d952f0d6cf4e")

    mock_check_permissions.return_value = None
    mock_get_deployment.return_value = None

    with pytest.raises(NotFoundError, match="Deployment not found"):
        await handler.get_deployment(user_id, organization_id, orbit_id, deployment_id)

    mock_check_permissions.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.DEPLOYMENT, Action.READ
    )
    mock_get_deployment.assert_awaited_once_with(deployment_id, orbit_id)


@patch(
    "dataforce_studio.handlers.deployments.DeploymentRepository.list_satellite_deployments",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_worker_deployments(
    mock_list_satellite_deployments: AsyncMock,
) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    deployment_id = UUID("0199c337-09f7-751e-add2-d952f0d6cf4e")
    satellite_id = UUID("0199c337-09f9-706e-9b80-58939d5fba79")
    model_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    expected_deployments = [
        Deployment(
            id=deployment_id,
            orbit_id=orbit_id,
            satellite_id=satellite_id,
            satellite_name="Satellite 1",
            name="worker-deployment",
            model_id=model_id,
            model_artifact_name="Model Artifact 1",
            collection_id=collection_id,
            status=DeploymentStatus.ACTIVE,
            created_by_user="Worker",
            created_at=datetime.datetime.now(),
            updated_at=None,
        )
    ]

    mock_list_satellite_deployments.return_value = expected_deployments

    result = await handler.list_worker_deployments(satellite_id)

    assert result == expected_deployments
    mock_list_satellite_deployments.assert_awaited_once_with(satellite_id)


@patch(
    "dataforce_studio.handlers.deployments.DeploymentRepository.update_deployment_details",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_deployment_details(
    mock_check_orbit_action_access: AsyncMock,
    mock_update_deployment_details: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    deployment_id = UUID("0199c337-09f7-751e-add2-d952f0d6cf4e")
    satellite_id = UUID("0199c337-09f9-706e-9b80-58939d5fba79")
    model_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")
    key_id = "0199c40d-fe95-794e-aa9a-cec0aeeb41a9"

    details = DeploymentDetailsUpdateIn(
        name="new-name",
        description="desc",
        dynamic_attributes_secrets={"key": UUID(key_id)},
        tags=["a", "b"],
    )
    details_converted = DeploymentDetailsUpdate(
        name="new-name",
        description="desc",
        dynamic_attributes_secrets={"key": key_id},
        tags=["a", "b"],
    )

    expected = Deployment(
        id=deployment_id,
        orbit_id=orbit_id,
        satellite_id=satellite_id,
        satellite_name="Satellite 5",
        model_id=model_id,
        model_artifact_name="Model Artifact 10",
        collection_id=collection_id,
        status=DeploymentStatus.ACTIVE,
        name=details.name or "default-name",
        description=details.description,
        dynamic_attributes_secrets={"key": key_id},
        tags=details.tags,
        created_by_user="User",
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )

    mock_update_deployment_details.return_value = expected

    result = await handler.update_deployment_details(
        user_id, organization_id, orbit_id, deployment_id, details
    )

    assert result == expected
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.DEPLOYMENT, Action.UPDATE
    )
    mock_update_deployment_details.assert_awaited_once_with(
        orbit_id, deployment_id, details_converted
    )


@patch(
    "dataforce_studio.handlers.deployments.DeploymentRepository.request_deployment_deletion",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_request_deployment_deletion(
    mock_check_orbit_action_access: AsyncMock, mock_request_delete: AsyncMock
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    deployment_id = UUID("0199c337-09f7-751e-add2-d952f0d6cf4e")
    satellite_id = UUID("0199c337-09f9-706e-9b80-58939d5fba79")
    model_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")
    now = datetime.datetime.now()

    deployment = Deployment(
        id=deployment_id,
        orbit_id=orbit_id,
        satellite_id=satellite_id,
        satellite_name="Satellite 1",
        name="deployment",
        model_id=model_id,
        model_artifact_name="Model Artifact 1",
        collection_id=collection_id,
        status=DeploymentStatus.DELETION_PENDING,
        created_by_user="User",
        created_at=now,
        updated_at=now,
    )
    task = SatelliteQueueTask(
        id=uuid6.uuid7(),
        satellite_id=satellite_id,
        orbit_id=orbit_id,
        type=SatelliteTaskType.UNDEPLOY,
        payload={"deployment_id": str(deployment_id)},
        status=SatelliteTaskStatus.PENDING,
        created_at=now,
        scheduled_at=now,
    )

    mock_request_delete.return_value = (deployment, task)

    result = await handler.request_deployment_deletion(
        user_id, organization_id, orbit_id, deployment_id
    )

    assert result == task
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.DEPLOYMENT, Action.DELETE
    )
    mock_request_delete.assert_awaited_once_with(orbit_id, deployment_id)


@patch(
    "dataforce_studio.handlers.deployments.DeploymentRepository.update_deployment",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_worker_deployment_status(
    mock_update_deployment: AsyncMock,
) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    deployment_id = UUID("0199c337-09f7-751e-add2-d952f0d6cf4e")
    satellite_id = UUID("0199c337-09f9-706e-9b80-58939d5fba79")
    model_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    dep_status = DeploymentStatus.ACTIVE

    expected = Deployment(
        id=deployment_id,
        orbit_id=orbit_id,
        satellite_id=satellite_id,
        satellite_name="Satellite 1",
        name="worker-deployment",
        model_id=model_id,
        model_artifact_name="Model Artifact 1",
        collection_id=collection_id,
        status=dep_status,
        created_by_user="Worker",
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )

    mock_update_deployment.return_value = expected

    result = await handler.update_worker_deployment_status(
        satellite_id, deployment_id, dep_status
    )

    assert result == expected
    mock_update_deployment.assert_awaited_once()


@patch(
    "dataforce_studio.handlers.deployments.DeploymentRepository.update_deployment",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_worker_deployment(
    mock_update_deployment: AsyncMock,
) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    deployment_id = UUID("0199c337-09f7-751e-add2-d952f0d6cf4e")
    satellite_id = UUID("0199c337-09f9-706e-9b80-58939d5fba79")
    model_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    inference_url = "https://inference.example.com"

    update_deployment_data = DeploymentUpdate(
        id=deployment_id,
        inference_url=inference_url,
        status=DeploymentStatus.ACTIVE,
    )

    expected = Deployment(
        id=deployment_id,
        orbit_id=orbit_id,
        satellite_id=satellite_id,
        satellite_name="Satellite 1",
        name="worker-deployment",
        model_id=model_id,
        model_artifact_name="Model Artifact 1",
        collection_id=collection_id,
        inference_url=inference_url,
        status=DeploymentStatus.ACTIVE,
        created_by_user="User Name",
        tags=["tag"],
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )

    mock_update_deployment.return_value = expected
    result = await handler.update_worker_deployment(
        satellite_id,
        deployment_id,
        DeploymentUpdateIn(inference_url=inference_url, status=DeploymentStatus.ACTIVE),
    )

    assert result == expected
    mock_update_deployment.assert_awaited_once_with(
        deployment_id, satellite_id, update_deployment_data
    )


@patch(
    "dataforce_studio.handlers.deployments.DeploymentRepository.update_deployment",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_worker_deployment_not_found(
    mock_update_deployment: AsyncMock,
) -> None:
    deployment_id = UUID("0199c337-09f7-751e-add2-d952f0d6cf4e")
    satellite_id = UUID("0199c337-09f9-706e-9b80-58939d5fba79")

    inference_url = "https://inference.example.com"
    update_deployment_data = DeploymentUpdate(
        id=deployment_id,
        inference_url=inference_url,
        status=DeploymentStatus.ACTIVE,
    )

    mock_update_deployment.return_value = None

    with pytest.raises(NotFoundError, match="Deployment not found") as error:
        await handler.update_worker_deployment(
            satellite_id,
            deployment_id,
            DeploymentUpdateIn(
                inference_url=inference_url, status=DeploymentStatus.ACTIVE
            ),
        )

    assert error.value.status_code == 404
    mock_update_deployment.assert_awaited_once_with(
        deployment_id, satellite_id, update_deployment_data
    )


@patch(
    "dataforce_studio.handlers.deployments.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.OrbitRepository.get_orbit_by_id",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.APIKeyHandler.authenticate_api_key",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_verify_user_inference_access(
    mock_authenticate_api_key: AsyncMock,
    mock_get_orbit_by_id: AsyncMock,
    mock_check_orbit_action_access: AsyncMock,
) -> None:
    api_key = "test_api_key"
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_authenticate_api_key.return_value = Mock(id=user_id)
    mock_get_orbit_by_id.return_value = Mock(
        id=orbit_id, organization_id=organization_id
    )

    result = await handler.verify_user_inference_access(orbit_id, api_key)

    assert result is True
    mock_authenticate_api_key.assert_awaited_once_with(api_key)
    mock_get_orbit_by_id.assert_awaited_once_with(orbit_id)
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.DEPLOYMENT, Action.READ
    )


@patch(
    "dataforce_studio.handlers.deployments.APIKeyHandler.authenticate_api_key",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_verify_user_inference_access_invalid_api_key(
    mock_authenticate_api_key: AsyncMock,
) -> None:
    api_key = "invalid_api_key"
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_authenticate_api_key.return_value = None

    result = await handler.verify_user_inference_access(orbit_id, api_key)

    assert result is False
    mock_authenticate_api_key.assert_awaited_once_with(api_key)


@patch(
    "dataforce_studio.handlers.deployments.OrbitRepository.get_orbit_by_id",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.APIKeyHandler.authenticate_api_key",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_verify_user_inference_access_orbit_not_found(
    mock_authenticate_api_key: AsyncMock,
    mock_get_orbit_by_id: AsyncMock,
) -> None:
    api_key = "test_api_key"
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_authenticate_api_key.return_value = Mock(id=user_id)
    mock_get_orbit_by_id.return_value = None

    result = await handler.verify_user_inference_access(orbit_id, api_key)

    assert result is False
    mock_authenticate_api_key.assert_awaited_once_with(api_key)
    mock_get_orbit_by_id.assert_awaited_once_with(orbit_id)


@patch(
    "dataforce_studio.handlers.deployments.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.OrbitRepository.get_orbit_by_id",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.deployments.APIKeyHandler.authenticate_api_key",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_verify_user_inference_access_insufficient_permissions(
    mock_authenticate_api_key: AsyncMock,
    mock_get_orbit_by_id: AsyncMock,
    mock_check_orbit_action_access: AsyncMock,
) -> None:
    api_key = "test_api_key"
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_user = Mock(id=user_id)
    mock_orbit = Mock(id=orbit_id, organization_id=organization_id)

    mock_authenticate_api_key.return_value = mock_user
    mock_get_orbit_by_id.return_value = mock_orbit
    mock_check_orbit_action_access.side_effect = InsufficientPermissionsError()

    result = await handler.verify_user_inference_access(orbit_id, api_key)

    assert result is False
    mock_authenticate_api_key.assert_awaited_once_with(api_key)
    mock_get_orbit_by_id.assert_awaited_once_with(orbit_id)
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.DEPLOYMENT, Action.READ
    )
