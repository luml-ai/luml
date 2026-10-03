from typing import Any, cast
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from luml.api.satellites import satellite_worker_router
from luml.infra.exceptions import NotFoundError
from luml.service import AppService

from tests.support.auth import Principal, satellite
from tests.support.ids import DEPLOYMENT_ID, ORBIT_ID, SATELLITE_ID

FOREIGN_SATELLITE_ID = UUID("0199c337-0a02-7c1e-8a3b-3f0e1a6d95c4")
FOREIGN_ORBIT_ID = UUID("0199c337-0a03-7f5a-bb17-2c9d4e8a1b63")

DEPLOYMENT_PATH = f"/satellites/v1/deployments/{DEPLOYMENT_ID}"


class TestSatellites:
    @pytest.fixture
    def principal(self, request: pytest.FixtureRequest) -> Principal:
        return getattr(request, "param", satellite(SATELLITE_ID, ORBIT_ID))

    def test_satellite_contract_is_public_versioned_and_worker_only(
        self, app: AppService
    ) -> None:
        response = TestClient(app).get("/satellites/v1/contract")

        assert response.status_code == 200
        payload = cast(dict[str, Any], response.json())
        assert payload["api_version"] == 1

        paths = cast(dict[str, dict[str, Any]], payload["openapi"]["paths"])
        assert paths
        assert all(path.startswith("/satellites/v1/") for path in paths)
        assert "post" in paths["/satellites/v1/pair"]
        assert "get" in paths["/satellites/v1/tasks"]
        assert "get" in paths["/satellites/v1/contract"]
        assert not any("organizations" in path for path in paths)

    def test_get_deployment_route_is_registered_once(self) -> None:
        matching_routes = [
            route
            for route in satellite_worker_router.routes
            if isinstance(route, APIRoute)
            and route.path == "/satellites/v1/deployments/{deployment_id}"
            and "GET" in route.methods
        ]

        assert len(matching_routes) == 1

    @patch(
        "luml.api.satellites.satellite_handler.touch_last_seen",
        new_callable=AsyncMock,
    )
    @patch(
        "luml.handlers.deployments.DeploymentHandler.delete_worker_deployment",
        new_callable=AsyncMock,
    )
    def test_delete_deployment_forwards_the_authenticated_satellite(
        self,
        mock_delete_worker_deployment: AsyncMock,
        mock_touch_last_seen: AsyncMock,
        client: TestClient,
    ) -> None:
        response = client.delete(DEPLOYMENT_PATH)

        assert response.status_code == 204
        mock_delete_worker_deployment.assert_awaited_once_with(
            SATELLITE_ID, DEPLOYMENT_ID
        )

    @pytest.mark.parametrize(
        "principal",
        [satellite(FOREIGN_SATELLITE_ID, FOREIGN_ORBIT_ID)],
        ids=["foreign"],
        indirect=True,
    )
    @patch(
        "luml.api.satellites.satellite_handler.touch_last_seen",
        new_callable=AsyncMock,
    )
    @patch(
        "luml.handlers.deployments.DeploymentHandler.delete_worker_deployment",
        new_callable=AsyncMock,
    )
    def test_delete_deployment_from_another_satellite_is_rejected(
        self,
        mock_delete_worker_deployment: AsyncMock,
        mock_touch_last_seen: AsyncMock,
        client: TestClient,
    ) -> None:
        mock_delete_worker_deployment.side_effect = NotFoundError(
            "Deployment not found"
        )

        response = client.delete(DEPLOYMENT_PATH)

        assert response.status_code == 404
        assert response.json() == {"detail": "Deployment not found"}
        mock_delete_worker_deployment.assert_awaited_once_with(
            FOREIGN_SATELLITE_ID, DEPLOYMENT_ID
        )

    @patch(
        "luml.handlers.deployments.DeploymentHandler.update_worker_deployment",
        new_callable=AsyncMock,
    )
    def test_progress_note_over_the_limit_is_rejected(
        self, mock_update_worker_deployment: AsyncMock, client: TestClient
    ) -> None:
        response = client.patch(
            DEPLOYMENT_PATH,
            json={"progress_note": "n" * 1001},
        )

        assert response.status_code == 422
        assert "progress_note" in response.text
        mock_update_worker_deployment.assert_not_awaited()
