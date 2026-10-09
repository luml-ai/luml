import datetime
from unittest.mock import Mock
from uuid import UUID

import pytest
from luml.handlers.deployments import DeploymentHandler
from luml.infra.exceptions import (
    ApplicationError,
    InsufficientPermissionsError,
    NotFoundError,
)
from luml.schemas.deployment import (
    Deployment,
    DeploymentStatus,
    DeploymentUpdate,
    DeploymentUpdateIn,
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


class TestWorkerDeployments:
    async def test_list_worker_deployments_returns_satellite_deployments(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        expected_deployments = [
            Deployment(
                id=DEPLOYMENT_ID,
                orbit_id=ORBIT_ID,
                satellite_id=SATELLITE_ID,
                satellite_name="Satellite 1",
                name="worker-deployment",
                artifact_id=ARTIFACT_ID,
                artifact_name="Model Artifact 1",
                collection_id=COLLECTION_ID,
                status=DeploymentStatus.ACTIVE,
                created_by_user="Worker",
                created_at=datetime.datetime.now(),
                updated_at=None,
            )
        ]

        mocks.repo.list_satellite_deployments.return_value = expected_deployments

        result = await mocks.handler.list_worker_deployments(SATELLITE_ID)

        assert result == expected_deployments
        mocks.repo.list_satellite_deployments.assert_awaited_once_with(SATELLITE_ID)

    async def test_get_worker_deployment_returns_deployment(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        expected = Deployment(
            id=DEPLOYMENT_ID,
            orbit_id=ORBIT_ID,
            satellite_id=SATELLITE_ID,
            satellite_name="satellite",
            name="worker-deployment",
            artifact_id=ARTIFACT_ID,
            artifact_name="model",
            collection_id=COLLECTION_ID,
            status=DeploymentStatus.ACTIVE,
            created_by_user="Worker",
            created_at=datetime.datetime.now(),
            updated_at=None,
        )

        mocks.repo.get_satellite_deployment.return_value = expected

        result = await mocks.handler.get_worker_deployment(SATELLITE_ID, DEPLOYMENT_ID)

        assert result == expected
        mocks.repo.get_satellite_deployment.assert_awaited_once_with(
            DEPLOYMENT_ID, SATELLITE_ID
        )

    async def test_get_worker_deployment_raises_not_found_when_deployment_is_missing(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        mocks.repo.get_satellite_deployment.return_value = None

        with pytest.raises(NotFoundError, match="Deployment not found") as error:
            await mocks.handler.get_worker_deployment(SATELLITE_ID, DEPLOYMENT_ID)

        assert error.value.status_code == 404
        mocks.repo.get_satellite_deployment.assert_awaited_once_with(
            DEPLOYMENT_ID, SATELLITE_ID
        )

    async def test_update_worker_deployment_returns_updated_deployment(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        inference_url = "https://inference.example.com"

        update_deployment_data = DeploymentUpdate(
            id=DEPLOYMENT_ID,
            inference_url=inference_url,
            status=DeploymentStatus.ACTIVE,
        )

        expected = Deployment(
            id=DEPLOYMENT_ID,
            orbit_id=ORBIT_ID,
            satellite_id=SATELLITE_ID,
            satellite_name="Satellite 1",
            name="worker-deployment",
            artifact_id=ARTIFACT_ID,
            artifact_name="Model Artifact 1",
            collection_id=COLLECTION_ID,
            inference_url=inference_url,
            status=DeploymentStatus.ACTIVE,
            created_by_user="User Name",
            tags=["tag"],
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        )

        mocks.repo.update_deployment.return_value = expected
        result = await mocks.handler.update_worker_deployment(
            SATELLITE_ID,
            DEPLOYMENT_ID,
            DeploymentUpdateIn(
                inference_url=inference_url, status=DeploymentStatus.ACTIVE
            ),
        )

        assert result == expected
        mocks.repo.update_deployment.assert_awaited_once_with(
            DEPLOYMENT_ID, SATELLITE_ID, update_deployment_data
        )

    async def test_update_worker_deployment_forwards_and_clears_progress_metadata(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        mocks.repo.update_deployment.return_value = Mock(spec=Deployment)

        await mocks.handler.update_worker_deployment(
            SATELLITE_ID,
            DEPLOYMENT_ID,
            DeploymentUpdateIn(
                provider_ref="provider-job-123",
                progress_note="Creating workload",
            ),
        )
        await mocks.handler.update_worker_deployment(
            SATELLITE_ID,
            DEPLOYMENT_ID,
            DeploymentUpdateIn(status=DeploymentStatus.ACTIVE, progress_note=None),
        )

        first_update = mocks.repo.update_deployment.await_args_list[0].args[2]
        second_update = mocks.repo.update_deployment.await_args_list[1].args[2]
        assert first_update.model_dump(exclude_unset=True) == {
            "id": DEPLOYMENT_ID,
            "provider_ref": "provider-job-123",
            "progress_note": "Creating workload",
        }
        assert second_update.model_dump(exclude_unset=True) == {
            "id": DEPLOYMENT_ID,
            "status": DeploymentStatus.ACTIVE,
            "progress_note": None,
        }

    @pytest.mark.parametrize(
        "data",
        [
            {"provider_ref": "p" * 513},
            {"progress_note": "n" * 1001},
        ],
    )
    def test_deployment_update_in_rejects_oversized_metadata(
        self, data: dict[str, str]
    ) -> None:
        with pytest.raises(ValidationError):
            DeploymentUpdateIn.model_validate(data)

    @pytest.mark.parametrize(
        "monitoring_url",
        ["/deployments/dep-1/monitoring", None],
    )
    async def test_update_worker_deployment_preserves_partial_fields(
        self,
        mocks: CollaboratorMocks[DeploymentHandler],
        monitoring_url: str | None,
    ) -> None:
        expected = Mock(spec=Deployment)
        mocks.repo.update_deployment.return_value = expected

        result = await mocks.handler.update_worker_deployment(
            SATELLITE_ID,
            DEPLOYMENT_ID,
            DeploymentUpdateIn(monitoring_url=monitoring_url),
        )

        assert result is expected
        update_call = mocks.repo.update_deployment.await_args
        assert update_call is not None
        update = update_call.args[2]
        assert update.model_dump(exclude_unset=True) == {
            "id": DEPLOYMENT_ID,
            "monitoring_url": monitoring_url,
        }

    async def test_update_worker_deployment_with_status_only_keeps_other_fields_unset(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        mocks.repo.update_deployment.return_value = Mock()
        await mocks.handler.update_worker_deployment(
            SATELLITE_ID,
            DEPLOYMENT_ID,
            DeploymentUpdateIn(status=DeploymentStatus.ACTIVE),
        )

        update_call = mocks.repo.update_deployment.await_args
        assert update_call is not None
        sent = update_call.args[2]
        assert sent.model_dump(exclude_unset=True) == {
            "id": DEPLOYMENT_ID,
            "status": DeploymentStatus.ACTIVE,
        }

    async def test_update_worker_deployment_clears_error_message_when_sent_as_null(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        mocks.repo.update_deployment.return_value = Mock()
        await mocks.handler.update_worker_deployment(
            SATELLITE_ID,
            DEPLOYMENT_ID,
            DeploymentUpdateIn(status=DeploymentStatus.ACTIVE, error_message=None),
        )

        update_call = mocks.repo.update_deployment.await_args
        assert update_call is not None
        sent = update_call.args[2]
        assert sent.model_dump(exclude_unset=True) == {
            "id": DEPLOYMENT_ID,
            "status": DeploymentStatus.ACTIVE,
            "error_message": None,
        }

    async def test_update_worker_deployment_raises_not_found_when_deployment_is_missing(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        inference_url = "https://inference.example.com"
        update_deployment_data = DeploymentUpdate(
            id=DEPLOYMENT_ID,
            inference_url=inference_url,
            status=DeploymentStatus.ACTIVE,
        )

        mocks.repo.update_deployment.return_value = None

        with pytest.raises(NotFoundError, match="Deployment not found") as error:
            await mocks.handler.update_worker_deployment(
                SATELLITE_ID,
                DEPLOYMENT_ID,
                DeploymentUpdateIn(
                    inference_url=inference_url, status=DeploymentStatus.ACTIVE
                ),
            )

        assert error.value.status_code == 404
        mocks.repo.update_deployment.assert_awaited_once_with(
            DEPLOYMENT_ID, SATELLITE_ID, update_deployment_data
        )

    async def test_delete_worker_deployment_deletes_pending_deployment(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        mocks.repo.get_satellite_deployment.return_value = Mock(
            id=DEPLOYMENT_ID,
            status=DeploymentStatus.DELETION_PENDING,
        )
        mocks.repo.delete_satellite_deployment.return_value = None

        await mocks.handler.delete_worker_deployment(SATELLITE_ID, DEPLOYMENT_ID)

        mocks.repo.delete_satellite_deployment.assert_awaited_once_with(
            DEPLOYMENT_ID, SATELLITE_ID
        )
        mocks.repo.get_satellite_deployment.assert_awaited_once_with(
            DEPLOYMENT_ID, SATELLITE_ID
        )

    async def test_delete_worker_deployment_returns_when_deployment_is_already_deleted(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        mocks.repo.get_satellite_deployment.return_value = None
        mocks.repo.deployment_exists.return_value = False

        await mocks.handler.delete_worker_deployment(SATELLITE_ID, DEPLOYMENT_ID)

        mocks.repo.get_satellite_deployment.assert_awaited_once_with(
            DEPLOYMENT_ID, SATELLITE_ID
        )
        mocks.repo.delete_satellite_deployment.assert_not_awaited()

    async def test_delete_worker_deployment_raises_not_found_for_foreign_satellite(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        foreign_satellite_id = UUID("0199c337-0a02-7c1e-8a3b-3f0e1a6d95c4")

        deployment = Mock(id=DEPLOYMENT_ID, status=DeploymentStatus.DELETION_PENDING)

        def owned_by_first_satellite(
            requested_id: UUID, satellite_id: UUID
        ) -> Mock | None:
            if requested_id != DEPLOYMENT_ID or satellite_id != SATELLITE_ID:
                return None
            return deployment

        mocks.repo.get_satellite_deployment.side_effect = owned_by_first_satellite
        mocks.repo.deployment_exists.return_value = True

        with pytest.raises(NotFoundError, match="Deployment not found") as error:
            await mocks.handler.delete_worker_deployment(
                foreign_satellite_id, DEPLOYMENT_ID
            )

        assert error.value.status_code == 404
        mocks.repo.delete_satellite_deployment.assert_not_awaited()

    async def test_delete_worker_deployment_raises_conflict_when_deletion_not_requested(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        mocks.repo.get_satellite_deployment.return_value = Mock(
            id=DEPLOYMENT_ID,
            status=DeploymentStatus.ACTIVE,
        )

        with pytest.raises(ApplicationError) as error:
            await mocks.handler.delete_worker_deployment(SATELLITE_ID, DEPLOYMENT_ID)

        assert error.value.status_code == 409
        mocks.repo.get_satellite_deployment.assert_awaited_once_with(
            DEPLOYMENT_ID, SATELLITE_ID
        )

    async def test_verify_user_inference_access_returns_true_when_permitted(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        api_key = "test_api_key"

        mocks.api_key_handler.authenticate_api_key.return_value = Mock(id=USER_ID)
        mocks.orbit_repo.get_orbit_by_id.return_value = Mock(
            id=ORBIT_ID, organization_id=ORGANIZATION_ID
        )

        result = await mocks.handler.verify_user_inference_access(ORBIT_ID, api_key)

        assert result is True
        mocks.api_key_handler.authenticate_api_key.assert_awaited_once_with(api_key)
        mocks.orbit_repo.get_orbit_by_id.assert_awaited_once_with(ORBIT_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.DEPLOYMENT, Action.READ, ORBIT_ID
        )

    async def test_verify_user_inference_access_returns_false_when_api_key_is_invalid(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        api_key = "invalid_api_key"

        mocks.api_key_handler.authenticate_api_key.return_value = None

        result = await mocks.handler.verify_user_inference_access(ORBIT_ID, api_key)

        assert result is False
        mocks.api_key_handler.authenticate_api_key.assert_awaited_once_with(api_key)

    async def test_verify_user_inference_access_returns_false_when_orbit_is_missing(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        api_key = "test_api_key"

        mocks.api_key_handler.authenticate_api_key.return_value = Mock(id=USER_ID)
        mocks.orbit_repo.get_orbit_by_id.return_value = None

        result = await mocks.handler.verify_user_inference_access(ORBIT_ID, api_key)

        assert result is False
        mocks.api_key_handler.authenticate_api_key.assert_awaited_once_with(api_key)
        mocks.orbit_repo.get_orbit_by_id.assert_awaited_once_with(ORBIT_ID)

    async def test_verify_user_inference_access_returns_false_when_permission_denied(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        api_key = "test_api_key"

        mocks.api_key_handler.authenticate_api_key.return_value = Mock(id=USER_ID)
        mocks.orbit_repo.get_orbit_by_id.return_value = Mock(
            id=ORBIT_ID, organization_id=ORGANIZATION_ID
        )
        mocks.permissions_handler.check_permissions.side_effect = (
            InsufficientPermissionsError()
        )

        result = await mocks.handler.verify_user_inference_access(ORBIT_ID, api_key)

        assert result is False
        mocks.api_key_handler.authenticate_api_key.assert_awaited_once_with(api_key)
        mocks.orbit_repo.get_orbit_by_id.assert_awaited_once_with(ORBIT_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.DEPLOYMENT, Action.READ, ORBIT_ID
        )

    async def test_verify_user_inference_access_returns_false_instead_of_not_found(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        api_key = "test_api_key"

        mocks.api_key_handler.authenticate_api_key.return_value = Mock(id=USER_ID)
        mocks.orbit_repo.get_orbit_by_id.return_value = Mock(
            id=ORBIT_ID, organization_id=ORGANIZATION_ID
        )
        mocks.permissions_handler.check_permissions.side_effect = NotFoundError(
            "Orbit not found"
        )

        result = await mocks.handler.verify_user_inference_access(ORBIT_ID, api_key)

        assert result is False
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.DEPLOYMENT, Action.READ, ORBIT_ID
        )
