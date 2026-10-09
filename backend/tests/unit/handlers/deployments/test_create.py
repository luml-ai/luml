import datetime
from typing import Any
from unittest.mock import Mock
from uuid import uuid7

import pytest
from fastapi import status
from luml.handlers.deployments import DeploymentHandler
from luml.infra.exceptions import (
    ApplicationError,
    ArtifactStatusMismatchError,
    NotFoundError,
)
from luml.schemas.artifacts import ArtifactStatus
from luml.schemas.deployment import (
    Deployment,
    DeploymentCreate,
    DeploymentCreateIn,
    DeploymentDetailsUpdateIn,
    DeploymentStatus,
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
    OTHER_ORBIT_ID,
    SATELLITE_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.deployments.conftest import (
    _artifact,
    _capabilities,
    _satellite,
)


class TestDeploymentCreation:
    async def test_create_deployment_returns_created_deployment(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        user_name = "User Full Name"

        deployment_create_data_in = DeploymentCreateIn(
            name="my-deployment",
            satellite_id=SATELLITE_ID,
            artifact_id=ARTIFACT_ID,
            monitoring_mode=MonitoringMode.FULL,
            satellite_parameters={
                "health_check_timeout": 60,
                "future_setting": "kept",
            },
            tags=["tag"],
        )
        deployment_create_data = DeploymentCreate(
            name="my-deployment",
            orbit_id=ORBIT_ID,
            satellite_id=SATELLITE_ID,
            artifact_id=ARTIFACT_ID,
            monitoring_mode=MonitoringMode.FULL,
            satellite_parameters=deployment_create_data_in.satellite_parameters,
            tags=deployment_create_data_in.tags,
            created_by_user=user_name,
        )
        expected = Deployment(
            id=DEPLOYMENT_ID,
            orbit_id=ORBIT_ID,
            satellite_id=SATELLITE_ID,
            satellite_name="Satellite 1",
            name="my-deployment",
            artifact_id=ARTIFACT_ID,
            artifact_name="Model Artifact 1",
            collection_id=COLLECTION_ID,
            inference_url=None,
            status=DeploymentStatus.PENDING,
            monitoring_mode=MonitoringMode.FULL,
            created_by_user=user_name,
            tags=deployment_create_data_in.tags,
            created_at=datetime.datetime.now(),
            updated_at=None,
        )

        mocks.orbit_repo.get_orbit_simple.return_value = Mock()
        mocks.sat_repo.get_satellite.return_value = _satellite(
            ORBIT_ID,
            _capabilities(
                supported_tags_combinations=[
                    ["luml.ai::sklearn:v1", "luml.ai::kind_tabular:v1"]
                ]
            ),
        )
        mocks.artifact_repo.get_artifact.return_value = _artifact(
            COLLECTION_ID,
            producer_tags=["luml.ai::sklearn:v1", "luml.ai::kind_tabular:v1"],
        )
        mocks.collection_repo.get_collection.return_value = Mock(orbit_id=ORBIT_ID)
        mocks.user_repo.get_public_user_by_id.return_value = Mock(full_name=user_name)
        mocks.repo.create_deployment.return_value = expected, None

        created_deployment = await mocks.handler.create_deployment(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, deployment_create_data_in
        )

        assert created_deployment == expected

        mocks.repo.create_deployment.assert_awaited_once_with(deployment_create_data)
        mocks.orbit_repo.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.sat_repo.get_satellite.assert_awaited_once_with(
            deployment_create_data_in.satellite_id
        )
        mocks.artifact_repo.get_artifact.assert_awaited_once_with(
            deployment_create_data_in.artifact_id
        )
        mocks.collection_repo.get_collection.assert_awaited_once_with(COLLECTION_ID)
        mocks.user_repo.get_public_user_by_id.assert_awaited_once_with(USER_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.DEPLOYMENT,
            Action.CREATE,
            ORBIT_ID,
        )

    @pytest.mark.parametrize(
        "artifact_status",
        [
            ArtifactStatus.PENDING_UPLOAD,
            ArtifactStatus.UPLOAD_FAILED,
            ArtifactStatus.PENDING_DELETION,
            ArtifactStatus.DELETION_FAILED,
        ],
    )
    async def test_create_deployment_raises_conflict_when_artifact_is_not_uploaded(
        self,
        mocks: CollaboratorMocks[DeploymentHandler],
        artifact_status: ArtifactStatus,
    ) -> None:
        data = DeploymentCreateIn(
            name="deployment",
            satellite_id=SATELLITE_ID,
            artifact_id=ARTIFACT_ID,
        )
        mocks.orbit_repo.get_orbit_simple.return_value = Mock()
        mocks.sat_repo.get_satellite.return_value = _satellite(
            ORBIT_ID, _capabilities()
        )
        mocks.artifact_repo.get_artifact.return_value = _artifact(
            COLLECTION_ID, status=artifact_status
        )
        mocks.collection_repo.get_collection.return_value = Mock(orbit_id=ORBIT_ID)
        mocks.user_repo.get_public_user_by_id.return_value = Mock(full_name="User")
        mocks.repo.create_deployment.side_effect = ArtifactStatusMismatchError(
            artifact_status.value
        )

        with pytest.raises(ApplicationError, match=artifact_status.value) as error:
            await mocks.handler.create_deployment(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, data
            )

        assert error.value.status_code == status.HTTP_409_CONFLICT
        mocks.repo.create_deployment.assert_awaited_once()
        mocks.permissions_handler.check_permissions.assert_awaited_once()

    async def test_create_deployment_hides_artifact_status_when_collection_is_foreign(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        data = DeploymentCreateIn(
            name="deployment",
            satellite_id=SATELLITE_ID,
            artifact_id=ARTIFACT_ID,
        )
        mocks.orbit_repo.get_orbit_simple.return_value = Mock()
        mocks.sat_repo.get_satellite.return_value = _satellite(
            ORBIT_ID, _capabilities()
        )
        mocks.artifact_repo.get_artifact.return_value = _artifact(
            COLLECTION_ID, status=ArtifactStatus.PENDING_DELETION
        )
        mocks.collection_repo.get_collection.return_value = Mock(
            orbit_id=OTHER_ORBIT_ID
        )

        with pytest.raises(NotFoundError, match="Collection not found") as error:
            await mocks.handler.create_deployment(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, data
            )

        assert error.value.status_code == status.HTTP_404_NOT_FOUND
        assert ArtifactStatus.PENDING_DELETION.value not in error.value.message
        mocks.repo.create_deployment.assert_not_awaited()
        mocks.permissions_handler.check_permissions.assert_awaited_once()

    @pytest.mark.parametrize(
        ("capabilities", "monitoring_mode", "variant", "producer_tags", "reason"),
        [
            pytest.param(
                _capabilities(deploy=False),
                MonitoringMode.OFF,
                "pyfunc",
                [],
                "present 'deploy' capability",
                id="deploy-missing",
            ),
            pytest.param(
                _capabilities(deploy_api_versions=[2]),
                MonitoringMode.OFF,
                "pyfunc",
                [],
                "present 'deploy' capability",
                id="deploy-version-unsupported",
            ),
            pytest.param(
                _capabilities(monitoring=False),
                MonitoringMode.FULL,
                "pyfunc",
                [],
                "present 'monitoring' capability",
                id="monitoring-missing",
            ),
            pytest.param(
                _capabilities(monitoring_api_versions=[2]),
                MonitoringMode.FULL,
                "pyfunc",
                [],
                "present 'monitoring' capability",
                id="monitoring-version-unsupported",
            ),
            pytest.param(
                _capabilities(supported_variants=["onnx"]),
                MonitoringMode.OFF,
                "pyfunc",
                [],
                "supported_variants",
                id="variant-unsupported",
            ),
            pytest.param(
                _capabilities(supported_tags_combinations=[["required-tag"]]),
                MonitoringMode.OFF,
                "pyfunc",
                ["other-tag"],
                "supported_tags_combinations",
                id="tags-unsupported",
            ),
        ],
    )
    async def test_create_deployment_raises_conflict_when_capability_unsupported(
        self,
        mocks: CollaboratorMocks[DeploymentHandler],
        capabilities: dict[str, dict[str, Any]],
        monitoring_mode: MonitoringMode,
        variant: str,
        producer_tags: list[str],
        reason: str,
    ) -> None:
        data = DeploymentCreateIn(
            name="my-deployment",
            satellite_id=SATELLITE_ID,
            artifact_id=ARTIFACT_ID,
            monitoring_mode=monitoring_mode,
        )

        mocks.orbit_repo.get_orbit_simple.return_value = Mock()
        mocks.sat_repo.get_satellite.return_value = _satellite(ORBIT_ID, capabilities)
        mocks.artifact_repo.get_artifact.return_value = _artifact(
            COLLECTION_ID,
            variant=variant,
            producer_tags=producer_tags,
        )
        mocks.collection_repo.get_collection.return_value = Mock(orbit_id=ORBIT_ID)
        mocks.user_repo.get_public_user_by_id.return_value = Mock(
            full_name="User Full Name"
        )

        with pytest.raises(ApplicationError, match=reason) as error:
            await mocks.handler.create_deployment(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                data,
            )

        assert error.value.status_code == status.HTTP_409_CONFLICT
        mocks.repo.create_deployment.assert_not_awaited()

    async def test_create_deployment_raises_not_found_when_orbit_is_missing(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        deployment_create_data_in = DeploymentCreateIn(
            name="my-deployment",
            satellite_id=SATELLITE_ID,
            artifact_id=ARTIFACT_ID,
            tags=["tag"],
        )

        mocks.orbit_repo.get_orbit_simple.return_value = None

        with pytest.raises(NotFoundError, match="Orbit not found") as error:
            await mocks.handler.create_deployment(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, deployment_create_data_in
            )

        assert error.value.status_code == 404
        mocks.orbit_repo.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.DEPLOYMENT,
            Action.CREATE,
            ORBIT_ID,
        )

    async def test_create_deployment_raises_not_found_when_satellite_is_missing(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        deployment_create_data_in = DeploymentCreateIn(
            name="my-deployment",
            satellite_id=SATELLITE_ID,
            artifact_id=ARTIFACT_ID,
            tags=["tag"],
        )

        mocks.orbit_repo.get_orbit_simple.return_value = Mock()
        mocks.sat_repo.get_satellite.return_value = None

        with pytest.raises(NotFoundError, match="Satellite not found") as error:
            await mocks.handler.create_deployment(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, deployment_create_data_in
            )

        assert error.value.status_code == 404
        mocks.orbit_repo.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.sat_repo.get_satellite.assert_awaited_once_with(
            deployment_create_data_in.satellite_id
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.DEPLOYMENT,
            Action.CREATE,
            ORBIT_ID,
        )

    async def test_create_deployment_raises_not_found_when_artifact_is_missing(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        deployment_create_data_in = DeploymentCreateIn(
            name="my-deployment",
            satellite_id=SATELLITE_ID,
            artifact_id=ARTIFACT_ID,
            tags=["tag"],
        )

        mocks.orbit_repo.get_orbit_simple.return_value = Mock()
        mocks.sat_repo.get_satellite.return_value = Mock(orbit_id=ORBIT_ID)
        mocks.artifact_repo.get_artifact.return_value = None

        with pytest.raises(NotFoundError, match="Artifact not found") as error:
            await mocks.handler.create_deployment(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, deployment_create_data_in
            )

        assert error.value.status_code == 404
        mocks.orbit_repo.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.sat_repo.get_satellite.assert_awaited_once_with(
            deployment_create_data_in.satellite_id
        )
        mocks.artifact_repo.get_artifact.assert_awaited_once_with(ARTIFACT_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.DEPLOYMENT,
            Action.CREATE,
            ORBIT_ID,
        )

    async def test_create_deployment_raises_not_found_when_collection_is_missing(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        deployment_create_data_in = DeploymentCreateIn(
            name="my-deployment",
            satellite_id=SATELLITE_ID,
            artifact_id=ARTIFACT_ID,
            tags=["tag"],
        )
        mocks.orbit_repo.get_orbit_simple.return_value = Mock()
        mocks.sat_repo.get_satellite.return_value = Mock(orbit_id=ORBIT_ID)
        mocks.artifact_repo.get_artifact.return_value = Mock(
            collection_id=COLLECTION_ID
        )
        mocks.collection_repo.get_collection.return_value = None

        with pytest.raises(NotFoundError, match="Collection not found") as error:
            await mocks.handler.create_deployment(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, deployment_create_data_in
            )

        assert error.value.status_code == 404
        mocks.orbit_repo.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.sat_repo.get_satellite.assert_awaited_once_with(
            deployment_create_data_in.satellite_id
        )
        mocks.artifact_repo.get_artifact.assert_awaited_once_with(ARTIFACT_ID)
        mocks.collection_repo.get_collection.assert_awaited_once_with(COLLECTION_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.DEPLOYMENT,
            Action.CREATE,
            ORBIT_ID,
        )

    async def test_create_deployment_raises_not_found_when_user_is_missing(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        deployment_create_data_in = DeploymentCreateIn(
            name="my-deployment",
            satellite_id=SATELLITE_ID,
            artifact_id=ARTIFACT_ID,
            tags=["tag"],
        )

        mocks.orbit_repo.get_orbit_simple.return_value = Mock()
        mocks.sat_repo.get_satellite.return_value = Mock(orbit_id=ORBIT_ID)
        mocks.artifact_repo.get_artifact.return_value = Mock(
            collection_id=COLLECTION_ID
        )
        mocks.collection_repo.get_collection.return_value = Mock(orbit_id=ORBIT_ID)
        mocks.user_repo.get_public_user_by_id.return_value = None

        with pytest.raises(NotFoundError, match="User not found") as error:
            await mocks.handler.create_deployment(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, deployment_create_data_in
            )

        assert error.value.status_code == 404
        mocks.orbit_repo.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.sat_repo.get_satellite.assert_awaited_once_with(
            deployment_create_data_in.satellite_id
        )
        mocks.artifact_repo.get_artifact.assert_awaited_once_with(ARTIFACT_ID)
        mocks.collection_repo.get_collection.assert_awaited_once_with(COLLECTION_ID)
        mocks.user_repo.get_public_user_by_id.assert_awaited_once_with(USER_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.DEPLOYMENT,
            Action.CREATE,
            ORBIT_ID,
        )

    @pytest.mark.parametrize("name", ["", "   "], ids=["empty", "whitespace"])
    def test_deployment_create_in_rejects_blank_name(self, name: str) -> None:
        with pytest.raises(ValidationError, match="at least 1 character"):
            DeploymentCreateIn(satellite_id=uuid7(), artifact_id=uuid7(), name=name)

    def test_deployment_create_in_and_details_update_in_trim_name(self) -> None:
        assert DeploymentDetailsUpdateIn(name="  prod  ").name == "prod"
        created = DeploymentCreateIn(
            satellite_id=uuid7(), artifact_id=uuid7(), name="  prod  "
        )
        assert created.name == "prod"
