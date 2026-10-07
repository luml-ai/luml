from unittest.mock import Mock, call
from uuid import uuid7

import pytest
from luml.handlers.deployments import DeploymentHandler
from luml.infra.exceptions import (
    InsufficientPermissionsError,
    InvalidStatusTransitionError,
)
from luml.schemas.deployment import (
    Deployment,
    DeploymentBatchAction,
    DeploymentsBatchRequest,
    DeploymentStatus,
)
from luml.schemas.permissions import Action, Resource
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from tests.support.ids import ORBIT_ID, ORGANIZATION_ID, USER_ID
from tests.support.mocks import CollaboratorMocks


class TestDeploymentBatchActions:
    async def test_undeploy_mixed_selection_reports_every_result_and_deduplicates(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        success, pending, missing, offline = [uuid7() for _ in range(4)]
        mocks.repo.get_deployment.side_effect = [
            Deployment.model_construct(name="first"),
            Deployment.model_construct(name="pending"),
            None,
            Deployment.model_construct(name="offline"),
        ]
        mocks.repo.request_deployment_deletion.side_effect = [
            (Mock(), Mock()),
            (Mock(), None),
            (Mock(), Mock()),
        ]

        result = await mocks.handler.batch_action(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            DeploymentsBatchRequest(
                deployment_ids=[success, pending, missing, offline, success],
                action=DeploymentBatchAction.UNDEPLOY,
            ),
        )

        assert result.succeeded == [success, offline]
        assert [entry.deployment_id for entry in result.failed] == [pending, missing]
        assert [entry.reason for entry in result.failed] == [
            "already_pending",
            "not_found",
        ]
        assert all(entry.message for entry in result.failed)
        assert mocks.repo.request_deployment_deletion.await_args_list == [
            call(ORBIT_ID, success),
            call(ORBIT_ID, pending),
            call(ORBIT_ID, offline),
        ]
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.DEPLOYMENT, Action.DELETE, ORBIT_ID
        )
        mocks.sat_repo.get_satellite.assert_not_awaited()

    async def test_delete_reference_refusal_does_not_block_the_rest(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        blocked, success = uuid7(), uuid7()
        mocks.repo.get_deployment.side_effect = [
            Deployment.model_construct(name="blocked", status=DeploymentStatus.FAILED),
            Deployment.model_construct(name="success", status=DeploymentStatus.FAILED),
        ]
        error = RuntimeError("private database error")
        error.sqlstate = "23503"  # type: ignore[attr-defined]
        mocks.repo.force_delete_inactive_deployment.side_effect = [
            IntegrityError("private statement", {}, error),
            Mock(),
        ]

        result = await mocks.handler.batch_action(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            DeploymentsBatchRequest(
                deployment_ids=[blocked, success], action=DeploymentBatchAction.DELETE
            ),
        )

        assert result.succeeded == [success]
        assert result.failed[0].deployment_id == blocked
        assert result.failed[0].reason == "references"
        assert "private" not in result.failed[0].message
        assert mocks.repo.force_delete_inactive_deployment.await_args_list == [
            call(blocked, ORBIT_ID),
            call(success, ORBIT_ID),
        ]

    async def test_permission_failure_changes_nothing(
        self, mocks: CollaboratorMocks[DeploymentHandler]
    ) -> None:
        mocks.permissions_handler.check_permissions.side_effect = (
            InsufficientPermissionsError()
        )
        with pytest.raises(InsufficientPermissionsError):
            await mocks.handler.batch_action(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                DeploymentsBatchRequest(
                    deployment_ids=[uuid7()], action=DeploymentBatchAction.UNDEPLOY
                ),
            )
        mocks.repo.get_deployment.assert_not_awaited()
        mocks.repo.request_deployment_deletion.assert_not_awaited()
        mocks.repo.force_delete_inactive_deployment.assert_not_awaited()

    @pytest.mark.parametrize("ids", [[], [uuid7() for _ in range(101)], ["invalid"]])
    def test_request_rejects_invalid_selection(self, ids: list[object]) -> None:
        with pytest.raises(ValidationError):
            DeploymentsBatchRequest.model_validate(
                {"deployment_ids": ids, "action": "undeploy"}
            )

    def test_request_rejects_unknown_action(self) -> None:
        with pytest.raises(ValidationError):
            DeploymentsBatchRequest.model_validate(
                {"deployment_ids": [uuid7()], "action": "restart"}
            )

    @pytest.mark.parametrize(
        ("outcome", "reason"),
        [
            (InvalidStatusTransitionError("Stop active deployments first"), "active"),
            (SQLAlchemyError("private details"), "database_error"),
            (None, "not_found"),
        ],
    )
    async def test_delete_rechecks_status_and_isolates_failures(
        self,
        mocks: CollaboratorMocks[DeploymentHandler],
        outcome: Exception | None,
        reason: str,
    ) -> None:
        first, second = uuid7(), uuid7()
        mocks.repo.get_deployment.side_effect = [
            Deployment.model_construct(name="first", status=DeploymentStatus.FAILED),
            Deployment.model_construct(name="second", status=DeploymentStatus.FAILED),
        ]
        mocks.repo.force_delete_inactive_deployment.side_effect = [outcome, Mock()]
        result = await mocks.handler.batch_action(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            DeploymentsBatchRequest(
                deployment_ids=[first, second], action=DeploymentBatchAction.DELETE
            ),
        )
        assert result.succeeded == [second]
        assert len(result.failed) == 1
        assert result.failed[0].deployment_id == first
        assert result.failed[0].reason == reason
        assert "private details" not in result.failed[0].message
