import datetime
from typing import Any
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi import status
from luml.handlers.deployments import DeploymentHandler
from luml.infra.exceptions import ApplicationError, NotFoundError
from luml.schemas.deployment import (
    Deployment,
    DeploymentDetailsUpdate,
    DeploymentDetailsUpdateIn,
    DeploymentStatus,
    DeploymentUpdate,
    MonitoringMode,
)
from luml.schemas.permissions import Action, Resource
from pydantic import ValidationError

from tests.support.ids import (
    ARTIFACT_ID,
    COLLECTION_ID,
    DEPLOYMENT_ID,
    ORBIT_ID,
    ORGANIZATION_ID,
    SATELLITE_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.deployments.conftest import _capabilities, _satellite


class TestDeploymentUpdate:
    async def test_list_deployments_returns_orbit_deployments(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        expected = [
            Deployment(
                id=DEPLOYMENT_ID,
                orbit_id=ORBIT_ID,
                satellite_id=SATELLITE_ID,
                satellite_name="Satellite 1",
                name="deployment-1",
                artifact_id=ARTIFACT_ID,
                artifact_name="Model Artifact 1",
                collection_id=COLLECTION_ID,
                status=DeploymentStatus.ACTIVE,
                created_by_user="John Doe",
                created_at=datetime.datetime.now(),
                updated_at=None,
            )
        ]

        mocks.repo.list_deployments.return_value = expected

        result = await mocks.handler.list_deployments(
            USER_ID, ORGANIZATION_ID, ORBIT_ID
        )

        assert result == expected
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.DEPLOYMENT,
            Action.LIST,
            ORBIT_ID,
        )
        mocks.repo.list_deployments.assert_awaited_once_with(ORBIT_ID)

    async def test_get_deployment_returns_deployment(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        expected = Deployment(
            id=DEPLOYMENT_ID,
            orbit_id=ORBIT_ID,
            satellite_id=SATELLITE_ID,
            satellite_name="Satellite 1",
            name="deployment-1",
            artifact_id=ARTIFACT_ID,
            artifact_name="Model Artifact 1",
            collection_id=COLLECTION_ID,
            status=DeploymentStatus.ACTIVE,
            created_by_user="John Doe",
            created_at=datetime.datetime.now(),
            updated_at=None,
        )

        mocks.repo.get_deployment.return_value = expected

        result = await mocks.handler.get_deployment(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
        )

        assert result == expected
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.DEPLOYMENT,
            Action.READ,
            ORBIT_ID,
        )

    async def test_get_deployment_raises_not_found_when_deployment_is_missing(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        mocks.repo.get_deployment.return_value = None

        with pytest.raises(NotFoundError, match="Deployment not found"):
            await mocks.handler.get_deployment(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
            )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.DEPLOYMENT,
            Action.READ,
            ORBIT_ID,
        )
        mocks.repo.get_deployment.assert_awaited_once_with(DEPLOYMENT_ID, ORBIT_ID)

    async def test_update_deployment_details_stores_secret_ids_as_strings(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        secret_id = "0199c40d-fe95-794e-aa9a-cec0aeeb41a9"

        details = DeploymentDetailsUpdateIn(
            name="new-name",
            description="desc",
            dynamic_attributes_secrets={"key": UUID(secret_id)},
            tags=["a", "b"],
        )
        details_converted = DeploymentDetailsUpdate(
            name="new-name",
            description="desc",
            dynamic_attributes_secrets={"key": secret_id},
            tags=["a", "b"],
        )

        expected = Deployment(
            id=DEPLOYMENT_ID,
            orbit_id=ORBIT_ID,
            satellite_id=SATELLITE_ID,
            satellite_name="Satellite 5",
            artifact_id=ARTIFACT_ID,
            artifact_name="Model Artifact 10",
            collection_id=COLLECTION_ID,
            status=DeploymentStatus.ACTIVE,
            name=details.name or "default-name",
            description=details.description,
            dynamic_attributes_secrets={"key": secret_id},
            tags=details.tags,
            created_by_user="User",
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        )

        mocks.repo.update_deployment_details.return_value = expected

        result = await mocks.handler.update_deployment_details(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID, details
        )

        assert result == expected
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.DEPLOYMENT,
            Action.UPDATE,
            ORBIT_ID,
        )
        mocks.repo.update_deployment_details.assert_awaited_once_with(
            ORBIT_ID, DEPLOYMENT_ID, details_converted
        )

    async def test_update_deployment_details_forwards_only_the_fields_sent(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        await mocks.handler.update_deployment_details(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            DEPLOYMENT_ID,
            DeploymentDetailsUpdateIn(name="new-name"),
        )

        update_call = mocks.repo.update_deployment_details.await_args
        assert update_call is not None
        forwarded = update_call.args[2]
        assert forwarded.model_fields_set == {"name"}
        assert forwarded.model_dump(exclude_unset=True) == {"name": "new-name"}

    @pytest.mark.parametrize(
        ("payload", "expected"),
        [
            pytest.param({"dynamic_attributes_secrets": None}, {}, id="explicit-null"),
            pytest.param({"dynamic_attributes_secrets": {}}, {}, id="explicit-empty"),
        ],
    )
    def test_deployment_details_update_in_reads_null_secrets_as_cleared(
        self, payload: dict[str, Any], expected: dict[str, Any]
    ) -> None:
        details = DeploymentDetailsUpdateIn.model_validate(payload)

        assert details.dynamic_attributes_secrets == expected
        assert "dynamic_attributes_secrets" in details.model_fields_set

    @pytest.mark.parametrize("field", ["name", "monitoring_mode"])
    def test_deployment_details_update_in_rejects_null_for_not_null_columns(
        self, field: str
    ) -> None:
        with pytest.raises(ValidationError, match=f"{field} cannot be null"):
            DeploymentDetailsUpdateIn.model_validate({field: None})

    @pytest.mark.parametrize("name", ["", "   "], ids=["empty", "whitespace"])
    def test_deployment_details_update_in_rejects_blank_name(self, name: str) -> None:
        with pytest.raises(ValidationError, match="at least 1 character"):
            DeploymentDetailsUpdateIn(name=name)

    @pytest.mark.parametrize(
        "capabilities",
        [
            pytest.param(_capabilities(monitoring=False), id="missing"),
            pytest.param(
                _capabilities(monitoring_api_versions=[2]),
                id="version-unsupported",
            ),
        ],
    )
    async def test_update_deployment_details_refuses_monitoring_without_capability(
        self,
        mocks: CollaboratorMocks[DeploymentHandler],
        capabilities: dict[str, dict[str, Any]],
    ) -> None:
        details = DeploymentDetailsUpdateIn(monitoring_mode=MonitoringMode.FULL)
        mocks.repo.get_deployment.return_value = Mock(
            monitoring_mode=MonitoringMode.OFF,
            satellite_id=SATELLITE_ID,
        )
        mocks.sat_repo.get_satellite.return_value = _satellite(ORBIT_ID, capabilities)

        with pytest.raises(
            ApplicationError,
            match="present 'monitoring' capability",
        ) as error:
            await mocks.handler.update_deployment_details(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                DEPLOYMENT_ID,
                details,
            )

        assert error.value.status_code == status.HTTP_409_CONFLICT
        mocks.repo.update_deployment_details.assert_not_awaited()

    async def test_update_deployment_details_enables_monitoring_with_capability(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        details = DeploymentDetailsUpdateIn(monitoring_mode=MonitoringMode.FULL)
        expected = Mock()
        mocks.repo.get_deployment.return_value = Mock(
            monitoring_mode=MonitoringMode.OFF,
            satellite_id=SATELLITE_ID,
        )
        mocks.sat_repo.get_satellite.return_value = _satellite(
            ORBIT_ID, _capabilities()
        )
        mocks.repo.update_deployment_details.return_value = expected

        result = await mocks.handler.update_deployment_details(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            DEPLOYMENT_ID,
            details,
        )

        assert result is expected
        mocks.repo.get_deployment.assert_awaited_once_with(DEPLOYMENT_ID, ORBIT_ID)
        mocks.sat_repo.get_satellite.assert_awaited_once_with(SATELLITE_ID)
        mocks.repo.update_deployment_details.assert_awaited_once_with(
            ORBIT_ID,
            DEPLOYMENT_ID,
            DeploymentDetailsUpdate(monitoring_mode=MonitoringMode.FULL),
        )

    async def test_update_deployment_details_keeps_monitoring_after_capability_loss(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        details = DeploymentDetailsUpdateIn(monitoring_mode=MonitoringMode.FULL)
        expected = Mock()
        mocks.repo.get_deployment.return_value = Mock(
            monitoring_mode=MonitoringMode.FULL,
            satellite_id=SATELLITE_ID,
        )
        mocks.repo.update_deployment_details.return_value = expected

        result = await mocks.handler.update_deployment_details(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            DEPLOYMENT_ID,
            details,
        )

        assert result is expected
        mocks.sat_repo.get_satellite.assert_not_awaited()
        mocks.repo.update_deployment_details.assert_awaited_once()

    async def test_update_deployment_details_raises_not_found_when_update_finds_nothing(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        details = DeploymentDetailsUpdateIn(
            name="new-name",
            description="desc",
            tags=["a", "b"],
        )

        mocks.repo.update_deployment_details.return_value = None

        with pytest.raises(NotFoundError, match="Deployment not found") as error:
            await mocks.handler.update_deployment_details(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID, details
            )

        assert error.value.status_code == 404
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.DEPLOYMENT, Action.UPDATE, ORBIT_ID
        )

    async def test_update_deployment_details_raises_not_found_when_deployment_missing(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        mocks.repo.get_deployment.return_value = None

        with pytest.raises(NotFoundError, match="Deployment not found") as error:
            await mocks.handler.update_deployment_details(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                DEPLOYMENT_ID,
                DeploymentDetailsUpdateIn(monitoring_mode=MonitoringMode.FULL),
            )

        assert error.value.status_code == status.HTTP_404_NOT_FOUND
        mocks.repo.get_deployment.assert_awaited_once_with(DEPLOYMENT_ID, ORBIT_ID)
        mocks.sat_repo.get_satellite.assert_not_awaited()
        mocks.repo.update_deployment_details.assert_not_awaited()

    async def test_update_deployment_details_raises_not_found_when_satellite_is_missing(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        mocks.repo.get_deployment.return_value = Mock(
            monitoring_mode=MonitoringMode.OFF,
            satellite_id=SATELLITE_ID,
        )
        mocks.sat_repo.get_satellite.return_value = None

        with pytest.raises(NotFoundError, match="Satellite not found") as error:
            await mocks.handler.update_deployment_details(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                DEPLOYMENT_ID,
                DeploymentDetailsUpdateIn(monitoring_mode=MonitoringMode.FULL),
            )

        assert error.value.status_code == status.HTTP_404_NOT_FOUND
        mocks.sat_repo.get_satellite.assert_awaited_once_with(SATELLITE_ID)
        mocks.repo.update_deployment_details.assert_not_awaited()

    async def test_update_worker_deployment_status_returns_updated_deployment(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        deployment_status = DeploymentStatus.ACTIVE

        expected = Deployment(
            id=DEPLOYMENT_ID,
            orbit_id=ORBIT_ID,
            satellite_id=SATELLITE_ID,
            satellite_name="Satellite 1",
            name="worker-deployment",
            artifact_id=ARTIFACT_ID,
            artifact_name="Model Artifact 1",
            collection_id=COLLECTION_ID,
            status=deployment_status,
            created_by_user="Worker",
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        )

        mocks.repo.update_deployment.return_value = expected

        result = await mocks.handler.update_worker_deployment_status(
            SATELLITE_ID, DEPLOYMENT_ID, deployment_status
        )

        assert result == expected
        mocks.repo.update_deployment.assert_awaited_once()

    async def test_update_worker_deployment_status_raises_not_found_when_missing(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        deployment_status = DeploymentStatus.ACTIVE

        mocks.repo.update_deployment.return_value = None

        with pytest.raises(NotFoundError, match="Deployment not found") as error:
            await mocks.handler.update_worker_deployment_status(
                SATELLITE_ID, DEPLOYMENT_ID, deployment_status
            )

        assert error.value.status_code == 404
        mocks.repo.update_deployment.assert_awaited_once_with(
            DEPLOYMENT_ID,
            SATELLITE_ID,
            DeploymentUpdate(id=DEPLOYMENT_ID, status=deployment_status),
        )
