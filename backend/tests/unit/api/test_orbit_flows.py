from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from luml.infra.exceptions import NotFoundError
from luml.schemas.flow import Flow, FlowExposeOut, FlowSession
from luml.schemas.live_session import LiveSessionStartOut, LiveSessionStatus

from tests.support.auth import ANONYMOUS
from tests.support.ids import (
    FLOW_ID,
    LIVE_SESSION_ID,
    ORBIT_ID,
    ORGANIZATION_ID,
    USER_ID,
)

FLOWS_PATH = f"/v1/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}/flows"
FLOW_PATH = f"{FLOWS_PATH}/{FLOW_ID}"
HANDLER = "luml.handlers.flows.FlowHandler"
FLOW = Flow(
    id=FLOW_ID,
    orbit_id=ORBIT_ID,
    user_id=USER_ID,
    name="training",
    session=FlowSession(
        id=LIVE_SESSION_ID,
        status=LiveSessionStatus.LIVE,
        started_at=datetime(2026, 9, 29, tzinfo=UTC),
        last_heartbeat_at=datetime(2026, 9, 29, 0, 0, 30, tzinfo=UTC),
    ),
    created_at=datetime(2026, 9, 29, tzinfo=UTC),
)


class TestOrbitFlows:
    @patch(f"{HANDLER}.expose_flow", new_callable=AsyncMock)
    def test_expose_route(self, mock_expose: AsyncMock, client: TestClient) -> None:
        app_url = f"https://app.luml.ai/organization/{ORGANIZATION_ID}/orbit/{ORBIT_ID}"
        mock_expose.return_value = FlowExposeOut(
            flow=FLOW,
            session=LiveSessionStartOut(
                id=LIVE_SESSION_ID,
                public_url=f"https://{LIVE_SESSION_ID}.sessions.example",
                agent_url="wss://sessions.example/connect",
                expose_token="token",
                token_expires_at=datetime(2026, 9, 29, tzinfo=UTC),
            ),
            app_url=f"{app_url}/flow",
        )

        response = client.post(FLOWS_PATH, json={"name": "training"})

        assert response.status_code == 200
        body = response.json()
        assert body["flow"]["name"] == "training"
        assert body["flow"]["session"] == {
            "id": LIVE_SESSION_ID,
            "status": "live",
            "started_at": "2026-09-29T00:00:00Z",
            "last_heartbeat_at": "2026-09-29T00:00:30Z",
        }
        assert (
            body["session"]["public_url"]
            == f"https://{LIVE_SESSION_ID}.sessions.example"
        )
        assert "app_url" not in body["session"]
        assert body["app_url"] == f"{app_url}/flow"
        assert mock_expose.await_args is not None
        args = mock_expose.await_args.args
        assert args[:3] == (USER_ID, ORGANIZATION_ID, ORBIT_ID)
        assert args[3].name == "training"

    @pytest.mark.parametrize("body", [{}, {"name": ""}], ids=["no-name", "empty-name"])
    @patch(f"{HANDLER}.expose_flow", new_callable=AsyncMock)
    def test_expose_requires_a_name(
        self, mock_expose: AsyncMock, body: dict[str, str], client: TestClient
    ) -> None:
        response = client.post(FLOWS_PATH, json=body)

        assert response.status_code == 422
        mock_expose.assert_not_awaited()

    @patch(f"{HANDLER}.list_flows", new_callable=AsyncMock, return_value=[FLOW])
    def test_list_route(self, mock_list: AsyncMock, client: TestClient) -> None:
        response = client.get(FLOWS_PATH)

        assert response.status_code == 200
        assert [flow["id"] for flow in response.json()] == [str(FLOW_ID)]
        mock_list.assert_awaited_once_with(USER_ID, ORGANIZATION_ID, ORBIT_ID)

    @patch(f"{HANDLER}.get_flow", new_callable=AsyncMock, return_value=FLOW)
    def test_read_route(self, mock_get: AsyncMock, client: TestClient) -> None:
        response = client.get(FLOW_PATH)

        assert response.status_code == 200
        assert response.json()["session"]["id"] == LIVE_SESSION_ID
        mock_get.assert_awaited_once_with(USER_ID, ORGANIZATION_ID, ORBIT_ID, FLOW_ID)

    @patch(f"{HANDLER}.remove_flow", new_callable=AsyncMock, return_value=None)
    def test_remove_route(self, mock_remove: AsyncMock, client: TestClient) -> None:
        response = client.delete(FLOW_PATH)

        assert response.status_code == 204
        mock_remove.assert_awaited_once_with(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, FLOW_ID
        )

    @pytest.mark.parametrize(
        ("method", "handler_method"),
        [("get", "get_flow"), ("delete", "remove_flow")],
        ids=["get", "delete"],
    )
    def test_a_flow_the_caller_may_not_see_answers_not_found(
        self, method: str, handler_method: str, client: TestClient
    ) -> None:
        with patch(
            f"{HANDLER}.{handler_method}",
            new_callable=AsyncMock,
            side_effect=NotFoundError("Flow not found"),
        ):
            response = client.request(method, FLOW_PATH)

        assert response.status_code == 404
        assert response.json() == {"detail": "Flow not found"}

    @pytest.mark.parametrize("principal", [ANONYMOUS], indirect=True)
    def test_operations_require_sign_in(self, client: TestClient) -> None:
        response = client.get(FLOWS_PATH)

        assert response.status_code == 401
