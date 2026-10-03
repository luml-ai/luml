import datetime
from unittest.mock import Mock
from uuid import UUID, uuid7

import pytest
from fastapi import status
from luml.handlers.deployments import DeploymentHandler
from luml.infra.exceptions import ApplicationError, NotFoundError
from luml.schemas.deployment import Deployment, DeploymentStatus
from luml.schemas.permissions import Action, Resource
from luml.schemas.satellite import (
    SatelliteQueueTask,
    SatelliteTaskStatus,
    SatelliteTaskType,
)

from tests.support.ids import (
    ARTIFACT_ID,
    COLLECTION_ID,
    DEPLOYMENT_ID,
    ORBIT_ID,
    ORGANIZATION_ID,
    OTHER_ORBIT_ID,
    SATELLITE_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks


class TestDeploymentDeletion:
    async def test_request_deployment_deletion_returns_undeploy_task(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        task_id = UUID("0199c337-0a01-7f32-9a65-9c3df0dc4cb2")
        now = datetime.datetime.now()

        deployment = Deployment(
            id=DEPLOYMENT_ID,
            orbit_id=ORBIT_ID,
            satellite_id=SATELLITE_ID,
            satellite_name="Satellite 1",
            name="deployment-1",
            artifact_id=ARTIFACT_ID,
            artifact_name="Model Artifact 1",
            collection_id=COLLECTION_ID,
            status=DeploymentStatus.ACTIVE,
            created_by_user="John",
            created_at=now,
            updated_at=now,
        )
        task = SatelliteQueueTask(
            id=task_id,
            satellite_id=deployment.satellite_id,
            orbit_id=ORBIT_ID,
            type=SatelliteTaskType.UNDEPLOY,
            payload={"deployment_id": DEPLOYMENT_ID},
            status=SatelliteTaskStatus.PENDING,
            scheduled_at=now,
            started_at=None,
            finished_at=None,
            result=None,
            created_at=now,
            updated_at=None,
        )

        mocks.repo.request_deployment_deletion.return_value = (deployment, task)

        result = await mocks.handler.request_deployment_deletion(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
        )

        assert result == task
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.DEPLOYMENT,
            Action.DELETE,
            ORBIT_ID,
        )
        mocks.repo.request_deployment_deletion.assert_awaited_once_with(
            ORBIT_ID, DEPLOYMENT_ID
        )

    async def test_request_deployment_deletion_raises_not_found_when_missing(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        mocks.repo.request_deployment_deletion.return_value = None

        with pytest.raises(NotFoundError, match="Deployment not found"):
            await mocks.handler.request_deployment_deletion(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
            )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.DEPLOYMENT,
            Action.DELETE,
            ORBIT_ID,
        )
        mocks.repo.request_deployment_deletion.assert_awaited_once_with(
            ORBIT_ID, DEPLOYMENT_ID
        )

    async def test_request_deployment_deletion_raises_conflict_when_already_pending(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        now = datetime.datetime.now()
        deployment = Deployment(
            id=DEPLOYMENT_ID,
            orbit_id=ORBIT_ID,
            satellite_id=SATELLITE_ID,
            satellite_name="Satellite 1",
            name="deployment-1",
            artifact_id=ARTIFACT_ID,
            artifact_name="Model Artifact 1",
            collection_id=COLLECTION_ID,
            status=DeploymentStatus.DELETION_PENDING,
            created_by_user="User",
            created_at=now,
            updated_at=now,
        )
        mocks.repo.request_deployment_deletion.return_value = (deployment, None)

        with pytest.raises(
            ApplicationError, match="Deployment deletion already pending"
        ) as exc:
            await mocks.handler.request_deployment_deletion(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
            )

        assert exc.value.status_code == status.HTTP_409_CONFLICT
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.DEPLOYMENT, Action.DELETE, ORBIT_ID
        )
        mocks.repo.request_deployment_deletion.assert_awaited_once_with(
            ORBIT_ID, DEPLOYMENT_ID
        )

    async def test_request_deployment_deletion_returns_task_for_pending_deployment(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        now = datetime.datetime.now()

        deployment = Deployment(
            id=DEPLOYMENT_ID,
            orbit_id=ORBIT_ID,
            satellite_id=SATELLITE_ID,
            satellite_name="Satellite 1",
            name="deployment",
            artifact_id=ARTIFACT_ID,
            artifact_name="Model Artifact 1",
            collection_id=COLLECTION_ID,
            status=DeploymentStatus.DELETION_PENDING,
            created_by_user="User",
            created_at=now,
            updated_at=now,
        )
        task = SatelliteQueueTask(
            id=uuid7(),
            satellite_id=SATELLITE_ID,
            orbit_id=ORBIT_ID,
            type=SatelliteTaskType.UNDEPLOY,
            payload={"deployment_id": str(DEPLOYMENT_ID)},
            status=SatelliteTaskStatus.PENDING,
            created_at=now,
            scheduled_at=now,
        )

        mocks.repo.request_deployment_deletion.return_value = (deployment, task)

        result = await mocks.handler.request_deployment_deletion(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
        )

        assert result == task
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.DEPLOYMENT,
            Action.DELETE,
            ORBIT_ID,
        )
        mocks.repo.request_deployment_deletion.assert_awaited_once_with(
            ORBIT_ID, DEPLOYMENT_ID
        )

    async def test_force_delete_deployment_deletes_orbit_deployment(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        mocks.repo.get_deployment.return_value = Mock(id=DEPLOYMENT_ID)
        mocks.repo.delete_deployment.return_value = None

        await mocks.handler.force_delete_deployment(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
        )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.DEPLOYMENT, Action.DELETE, ORBIT_ID
        )
        mocks.repo.get_deployment.assert_awaited_once_with(DEPLOYMENT_ID, ORBIT_ID)
        mocks.repo.delete_deployment.assert_awaited_once_with(DEPLOYMENT_ID, ORBIT_ID)

    async def test_force_delete_deployment_raises_not_found_when_deployment_is_missing(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        mocks.repo.get_deployment.return_value = None

        with pytest.raises(NotFoundError, match="Deployment not found") as error:
            await mocks.handler.force_delete_deployment(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
            )

        assert error.value.status_code == 404
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.DEPLOYMENT, Action.DELETE, ORBIT_ID
        )
        mocks.repo.get_deployment.assert_awaited_once_with(DEPLOYMENT_ID, ORBIT_ID)

    async def test_force_delete_deployment_raises_not_found_for_foreign_orbit(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        deployment = Mock(id=DEPLOYMENT_ID, orbit_id=OTHER_ORBIT_ID)

        def stored_in_owner_orbit(
            requested_id: UUID, orbit_id: UUID | None = None
        ) -> Mock | None:
            if requested_id != DEPLOYMENT_ID:
                return None
            if orbit_id is not None and orbit_id != OTHER_ORBIT_ID:
                return None
            return deployment

        mocks.repo.get_deployment.side_effect = stored_in_owner_orbit

        with pytest.raises(NotFoundError, match="Deployment not found") as error:
            await mocks.handler.force_delete_deployment(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
            )

        assert error.value.status_code == 404
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.DEPLOYMENT,
            Action.DELETE,
            ORBIT_ID,
        )
        mocks.repo.delete_deployment.assert_not_awaited()
