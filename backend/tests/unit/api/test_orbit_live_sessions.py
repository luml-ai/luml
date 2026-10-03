from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from luml.models import AuthUser
from luml.schemas.live_session import LiveSession, LiveSessionStartOut
from luml.schemas.orbit import Orbit
from luml.service import AppService
from starlette.authentication import AuthCredentials

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
ORBIT_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")
BASE_PATH = f"/v1/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}/live-sessions"
AUTHENTICATE = "luml.infra.security.JWTAuthenticationBackend.authenticate"
REPO = "luml.handlers.live_sessions.LiveSessionRepository"
VIEW_TOKEN_OUT = {
    "token": "t",
    "launch_url": "https://k3f9x2ab.tunnel.example/.luml-tunnel/launch?token=t",
    "expires_at": "2026-09-29T12:00:00Z",
}


def _signed_in() -> tuple[AuthCredentials, AuthUser]:
    return AuthCredentials(["authenticated", "api_key"]), AuthUser(
        user_id=USER_ID, email="caller@example.com"
    )


@patch(AUTHENTICATE, new_callable=AsyncMock, return_value=None)
def test_public_keys_are_no_longer_published(mock_authenticate: AsyncMock) -> None:
    response = TestClient(AppService()).get("/.well-known/jwks.json")

    assert response.status_code == 404


@patch(f"{REPO}.create_live_session", new_callable=AsyncMock)
@patch(
    "luml.handlers.live_sessions.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.live_sessions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(AUTHENTICATE, new_callable=AsyncMock, return_value=_signed_in())
def test_start_in_an_orbit_without_a_relay_answers_a_conflict(
    mock_authenticate: AsyncMock,
    mock_check_permissions: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_create: AsyncMock,
) -> None:
    mock_get_orbit.return_value = Orbit(
        id=ORBIT_ID,
        name="orbit",
        organization_id=ORGANIZATION_ID,
        bucket_secret_id=UUID("0199c337-09f5-7a3b-8c1d-2e3f4a5b6c7d"),
        created_at=datetime.now(UTC),
    )
    response = TestClient(AppService()).post(BASE_PATH, json={"name": "run"})

    assert response.status_code == 409
    assert response.json() == {
        "detail": "The orbit has no relay; assign a relay in orbit settings"
    }
    mock_create.assert_not_awaited()


@patch(AUTHENTICATE, new_callable=AsyncMock, return_value=_signed_in())
def test_start_requires_a_name(mock_authenticate: AsyncMock) -> None:
    response = TestClient(AppService()).post(BASE_PATH, json={"name": ""})

    assert response.status_code == 422


@patch(AUTHENTICATE, new_callable=AsyncMock, return_value=None)
def test_operations_require_sign_in(mock_authenticate: AsyncMock) -> None:
    response = TestClient(AppService()).get(BASE_PATH)

    assert response.status_code == 401


@patch(
    "luml.api.orbits.orbit_live_sessions.LiveSessionHandler.start_session",
    new_callable=AsyncMock,
)
@patch(AUTHENTICATE, new_callable=AsyncMock, return_value=_signed_in())
def test_start_route(mock_authenticate: AsyncMock, mock_start: AsyncMock) -> None:
    mock_start.return_value = LiveSessionStartOut(
        id="k3f9x2ab",
        public_url="https://k3f9x2ab.tunnel.example",
        app_url="https://app.luml.ai/flow/k3f9x2ab",
        agent_url="wss://tunnel.example/connect",
        expose_token="token",
        token_expires_at=datetime(2026, 9, 29, tzinfo=UTC),
    )

    response = TestClient(AppService()).post(BASE_PATH, json={"name": "training run"})

    assert response.status_code == 200
    assert response.json()["heartbeat_interval"] == 30
    assert mock_start.await_args is not None
    args = mock_start.await_args.args
    assert args[:3] == (USER_ID, ORGANIZATION_ID, ORBIT_ID)
    assert args[3].name == "training run"


@pytest.mark.parametrize(
    ("method", "path", "handler_method", "body"),
    [
        ("get", "", "list_sessions", None),
        ("get", "/k3f9x2ab", "get_session", None),
        (
            "post",
            "/k3f9x2ab/heartbeat",
            "record_heartbeat",
            {"connected": True, "token_expires_at": "2026-09-29T12:00:00Z"},
        ),
        ("post", "/k3f9x2ab/view-token", "issue_view_token", None),
        ("post", "/k3f9x2ab/end", "end_session", None),
    ],
)
@patch(AUTHENTICATE, new_callable=AsyncMock, return_value=_signed_in())
def test_session_routes_pass_the_caller_and_the_session(
    mock_authenticate: AsyncMock,
    method: str,
    path: str,
    handler_method: str,
    body: dict[str, object] | None,
) -> None:
    session = LiveSession(
        id="k3f9x2ab",
        orbit_id=ORBIT_ID,
        user_id=USER_ID,
        name="run",
        relay_id=UUID("0199c337-09f4-7a3b-8c1d-2e3f4a5b6c7d"),
        started_at=datetime.now(UTC),
        connected=False,
    )
    results = {
        "list_sessions": [session],
        "get_session": session,
        "record_heartbeat": {"status": "live"},
        "issue_view_token": VIEW_TOKEN_OUT,
        "end_session": session,
    }
    with patch(
        f"luml.api.orbits.orbit_live_sessions.LiveSessionHandler.{handler_method}",
        new_callable=AsyncMock,
        return_value=results[handler_method],
    ) as mock_handler:
        client = TestClient(AppService())
        response = client.request(method, BASE_PATH + path, json=body)

    assert response.status_code == 200
    assert mock_handler.await_args is not None
    args = mock_handler.await_args.args
    assert args[:3] == (USER_ID, ORGANIZATION_ID, ORBIT_ID)
    if path:
        assert args[3] == "k3f9x2ab"


@pytest.mark.parametrize(
    "destination",
    [
        "https://evil.example/experiments",
        "//evil.example/experiments",
        "experiments/42",
        "/\\evil.example/experiments",
        "/\t/evil.example/experiments",
    ],
    ids=["full-address", "two-slashes", "no-slash", "backslash", "tab"],
)
@patch(
    "luml.api.orbits.orbit_live_sessions.LiveSessionHandler.issue_view_token",
    new_callable=AsyncMock,
)
@patch(AUTHENTICATE, new_callable=AsyncMock, return_value=_signed_in())
def test_view_token_with_a_destination_that_is_not_a_relative_path_is_refused(
    mock_authenticate: AsyncMock, mock_issue: AsyncMock, destination: str
) -> None:
    response = TestClient(AppService()).post(
        f"{BASE_PATH}/k3f9x2ab/view-token", json={"destination": destination}
    )

    assert response.status_code == 422
    mock_issue.assert_not_awaited()


@patch(
    "luml.api.orbits.orbit_live_sessions.LiveSessionHandler.issue_view_token",
    new_callable=AsyncMock,
    return_value=VIEW_TOKEN_OUT,
)
@patch(AUTHENTICATE, new_callable=AsyncMock, return_value=_signed_in())
def test_view_token_passes_the_destination(
    mock_authenticate: AsyncMock, mock_issue: AsyncMock
) -> None:
    response = TestClient(AppService()).post(
        f"{BASE_PATH}/k3f9x2ab/view-token",
        json={"destination": "/experiments/42?tab=metrics"},
    )

    assert response.status_code == 200
    assert mock_issue.await_args is not None
    assert mock_issue.await_args.args[4].destination == "/experiments/42?tab=metrics"
