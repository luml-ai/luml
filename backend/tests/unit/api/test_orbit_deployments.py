from unittest.mock import AsyncMock, patch
from uuid import uuid7

import pytest
from fastapi.testclient import TestClient
from luml.schemas.deployment import (
    DeploymentBatchAction,
    DeploymentBatchFailure,
    DeploymentsBatchRequest,
    DeploymentsBatchResponse,
)

from tests.support.ids import ORBIT_ID, ORGANIZATION_ID, USER_ID

DEPLOYMENTS_PATH = f"/v1/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}/deployments"


@patch(
    "luml.handlers.deployments.DeploymentHandler.batch_action", new_callable=AsyncMock
)
def test_batch_route_forwards_selection_and_reports_partial_failure(
    mock_batch_action: AsyncMock, client: TestClient
) -> None:
    success, failed = uuid7(), uuid7()
    expected = DeploymentsBatchResponse(
        succeeded=[success],
        failed=[
            DeploymentBatchFailure(
                deployment_id=failed,
                name="blocked",
                reason="active",
                message="Stop active deployments first",
            )
        ],
    )
    mock_batch_action.return_value = expected
    response = client.post(
        f"{DEPLOYMENTS_PATH}/batch",
        json={
            "deployment_ids": [str(success), str(failed), str(success)],
            "action": "delete",
        },
    )
    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")
    mock_batch_action.assert_awaited_once_with(
        USER_ID,
        ORGANIZATION_ID,
        ORBIT_ID,
        DeploymentsBatchRequest(
            deployment_ids=[success, failed], action=DeploymentBatchAction.DELETE
        ),
    )


@pytest.mark.parametrize(
    "selection", [[], [str(uuid7()) for _ in range(101)], ["invalid"]]
)
@patch(
    "luml.handlers.deployments.DeploymentHandler.batch_action", new_callable=AsyncMock
)
def test_batch_route_rejects_invalid_selection(
    mock_batch_action: AsyncMock, client: TestClient, selection: list[str]
) -> None:
    response = client.post(
        f"{DEPLOYMENTS_PATH}/batch",
        json={"deployment_ids": selection, "action": "undeploy"},
    )
    assert response.status_code == 422
    mock_batch_action.assert_not_awaited()
