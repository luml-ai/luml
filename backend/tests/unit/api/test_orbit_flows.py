from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from luml.infra.exceptions import NotFoundError
from luml.models import AuthUser
from luml.schemas.flow import Flow, FlowExposeOut, FlowSession
from luml.schemas.live_session import LiveSessionStartOut, LiveSessionStatus
from luml.service import AppService
from starlette.authentication import AuthCredentials

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
ORBIT_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")
FLOW_ID = UUID("0199c337-09f6-7a3b-8c1d-2e3f4a5b6c7d")
BASE_PATH = f"/v1/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}/flows"
AUTHENTICATE = "luml.infra.security.JWTAuthenticationBackend.authenticate"
HANDLER = "luml.api.orbits.orbit_flows.FlowHandler"
FLOW = Flow(
    id=FLOW_ID,
    orbit_id=ORBIT_ID,
    user_id=USER_ID,
    name="training",
    session=FlowSession(
        id="k3f9x2ab",
        status=LiveSessionStatus.LIVE,
        started_at=datetime(2026, 9, 29, tzinfo=UTC),
        last_heartbeat_at=datetime(2026, 9, 29, 0, 0, 30, tzinfo=UTC),
    ),
    created_at=datetime(2026, 9, 29, tzinfo=UTC),
)


def _signed_in() -> tuple[AuthCredentials, AuthUser]:
    return AuthCredentials(["authenticated", "api_key"]), AuthUser(
        user_id=USER_ID, email="caller@example.com"
    )


@patch(f"{HANDLER}.expose_flow", new_callable=AsyncMock)
@patch(AUTHENTICATE, new_callable=AsyncMock, return_value=_signed_in())
def test_expose_route(mock_authenticate: AsyncMock, mock_expose: AsyncMock) -> None:
    app_url = f"https://app.luml.ai/organization/{ORGANIZATION_ID}/orbit/{ORBIT_ID}"
    mock_expose.return_value = FlowExposeOut(
        flow=FLOW,
        session=LiveSessionStartOut(
            id="k3f9x2ab",
            public_url="https://k3f9x2ab.tunnel.example",
            agent_url="wss://tunnel.example/connect",
            expose_token="token",
            token_expires_at=datetime(2026, 9, 29, tzinfo=UTC),
        ),
        app_url=f"{app_url}/flow",
    )

    response = TestClient(AppService()).post(BASE_PATH, json={"name": "training"})

    assert response.status_code == 200
    body = response.json()
    assert body["flow"]["name"] == "training"
    assert body["flow"]["session"] == {
        "id": "k3f9x2ab",
        "status": "live",
        "started_at": "2026-09-29T00:00:00Z",
        "last_heartbeat_at": "2026-09-29T00:00:30Z",
    }
    assert body["session"]["public_url"] == "https://k3f9x2ab.tunnel.example"
    assert "app_url" not in body["session"]
    assert body["app_url"] == f"{app_url}/flow"
    assert mock_expose.await_args is not None
    args = mock_expose.await_args.args
    assert args[:3] == (USER_ID, ORGANIZATION_ID, ORBIT_ID)
    assert args[3].name == "training"


@pytest.mark.parametrize("body", [{}, {"name": ""}], ids=["no-name", "empty-name"])
@patch(f"{HANDLER}.expose_flow", new_callable=AsyncMock)
@patch(AUTHENTICATE, new_callable=AsyncMock, return_value=_signed_in())
def test_expose_requires_a_name(
    mock_authenticate: AsyncMock, mock_expose: AsyncMock, body: dict[str, str]
) -> None:
    response = TestClient(AppService()).post(BASE_PATH, json=body)

    assert response.status_code == 422
    mock_expose.assert_not_awaited()


@patch(f"{HANDLER}.list_flows", new_callable=AsyncMock, return_value=[FLOW])
@patch(AUTHENTICATE, new_callable=AsyncMock, return_value=_signed_in())
def test_list_route(mock_authenticate: AsyncMock, mock_list: AsyncMock) -> None:
    response = TestClient(AppService()).get(BASE_PATH)

    assert response.status_code == 200
    assert [flow["id"] for flow in response.json()] == [str(FLOW_ID)]
    mock_list.assert_awaited_once_with(USER_ID, ORGANIZATION_ID, ORBIT_ID)


@patch(f"{HANDLER}.get_flow", new_callable=AsyncMock, return_value=FLOW)
@patch(AUTHENTICATE, new_callable=AsyncMock, return_value=_signed_in())
def test_read_route(mock_authenticate: AsyncMock, mock_get: AsyncMock) -> None:
    response = TestClient(AppService()).get(f"{BASE_PATH}/{FLOW_ID}")

    assert response.status_code == 200
    assert response.json()["session"]["id"] == "k3f9x2ab"
    mock_get.assert_awaited_once_with(USER_ID, ORGANIZATION_ID, ORBIT_ID, FLOW_ID)


@patch(f"{HANDLER}.remove_flow", new_callable=AsyncMock, return_value=None)
@patch(AUTHENTICATE, new_callable=AsyncMock, return_value=_signed_in())
def test_remove_route(mock_authenticate: AsyncMock, mock_remove: AsyncMock) -> None:
    response = TestClient(AppService()).delete(f"{BASE_PATH}/{FLOW_ID}")

    assert response.status_code == 204
    mock_remove.assert_awaited_once_with(USER_ID, ORGANIZATION_ID, ORBIT_ID, FLOW_ID)


@pytest.mark.parametrize("method", ["get", "delete"])
@patch(AUTHENTICATE, new_callable=AsyncMock, return_value=_signed_in())
def test_a_flow_the_caller_may_not_see_answers_not_found(
    mock_authenticate: AsyncMock, method: str
) -> None:
    handler_method = "get_flow" if method == "get" else "remove_flow"
    with patch(
        f"{HANDLER}.{handler_method}",
        new_callable=AsyncMock,
        side_effect=NotFoundError("Flow not found"),
    ):
        response = TestClient(AppService()).request(method, f"{BASE_PATH}/{FLOW_ID}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Flow not found"}


@patch(AUTHENTICATE, new_callable=AsyncMock, return_value=None)
def test_operations_require_sign_in(mock_authenticate: AsyncMock) -> None:
    response = TestClient(AppService()).get(BASE_PATH)

    assert response.status_code == 401
