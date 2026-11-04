from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from luml.schemas.live_session import (
    LiveSession,
    LiveSessionStartIn,
    LiveSessionStartOut,
    LiveSessionVisibility,
)
from luml.schemas.orbit import Orbit

from tests.support.auth import ANONYMOUS
from tests.support.ids import (
    BUCKET_SECRET_ID,
    LIVE_SESSION_ID,
    ORBIT_ID,
    ORGANIZATION_ID,
    RELAY_ID,
    USER_ID,
)

LIVE_SESSIONS_PATH = (
    f"/v1/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}/live-sessions"
)
LIVE_SESSION_PATH = f"{LIVE_SESSIONS_PATH}/{LIVE_SESSION_ID}"
HANDLER = "luml.handlers.live_sessions.LiveSessionHandler"
REPO = "luml.handlers.live_sessions.LiveSessionRepository"
VIEW_TOKEN_OUT = {
    "token": "t",
    "launch_url": f"https://{LIVE_SESSION_ID}.sessions.example/.luml-relay/launch?token=t",
    "expires_at": "2026-09-29T12:00:00Z",
}
START_OUT = LiveSessionStartOut(
    id=LIVE_SESSION_ID,
    public_url=f"https://{LIVE_SESSION_ID}.sessions.example",
    agent_url="wss://sessions.example/connect",
    expose_token="token",
    token_expires_at=datetime(2026, 9, 29, tzinfo=UTC),
)


class TestOrbitLiveSessions:
    @pytest.mark.parametrize("principal", [ANONYMOUS], indirect=True)
    def test_public_keys_are_no_longer_published(self, client: TestClient) -> None:
        response = client.get("/.well-known/jwks.json")

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
    def test_start_in_an_orbit_without_a_relay_answers_a_conflict(
        self,
        mock_check_permissions: AsyncMock,
        mock_get_orbit: AsyncMock,
        mock_create: AsyncMock,
        client: TestClient,
    ) -> None:
        mock_get_orbit.return_value = Orbit(
            id=ORBIT_ID,
            name="orbit",
            organization_id=ORGANIZATION_ID,
            bucket_secret_id=BUCKET_SECRET_ID,
            created_at=datetime.now(UTC),
        )

        response = client.post(LIVE_SESSIONS_PATH, json={"label": "run"})

        assert response.status_code == 409
        assert response.json() == {
            "detail": "The orbit has no relay; assign a relay in orbit settings"
        }
        mock_create.assert_not_awaited()

    def test_start_refuses_an_empty_label(self, client: TestClient) -> None:
        response = client.post(LIVE_SESSIONS_PATH, json={"label": ""})

        assert response.status_code == 422

    @pytest.mark.parametrize("principal", [ANONYMOUS], indirect=True)
    def test_operations_require_sign_in(self, client: TestClient) -> None:
        response = client.get(LIVE_SESSIONS_PATH)

        assert response.status_code == 401

    @patch(f"{HANDLER}.start_session", new_callable=AsyncMock, return_value=START_OUT)
    def test_start_route(self, mock_start: AsyncMock, client: TestClient) -> None:
        response = client.post(LIVE_SESSIONS_PATH, json={"label": "training run"})

        assert response.status_code == 200
        assert response.json()["heartbeat_interval"] == 30
        assert "app_url" not in response.json()
        assert mock_start.await_args is not None
        args = mock_start.await_args.args
        assert args[:3] == (USER_ID, ORGANIZATION_ID, ORBIT_ID)
        assert args[3].label == "training run"

    @pytest.mark.parametrize(
        "body", [{}, {"visibility": "orbit"}], ids=["no-label", "visibility"]
    )
    @patch(f"{HANDLER}.start_session", new_callable=AsyncMock, return_value=START_OUT)
    def test_start_takes_neither_a_label_nor_a_visibility(
        self, mock_start: AsyncMock, body: dict[str, str], client: TestClient
    ) -> None:
        response = client.post(LIVE_SESSIONS_PATH, json=body)

        assert response.status_code == 200
        assert mock_start.await_args is not None
        assert mock_start.await_args.args[3] == LiveSessionStartIn()

    @patch(f"{HANDLER}.record_heartbeat", new_callable=AsyncMock)
    def test_heartbeat_refuses_a_token_expiry_without_a_timezone(
        self, mock_record_heartbeat: AsyncMock, client: TestClient
    ) -> None:
        response = client.post(
            f"{LIVE_SESSION_PATH}/heartbeat",
            json={"connected": True, "token_expires_at": "2026-10-04T08:00:00"},
        )

        assert response.status_code == 422
        mock_record_heartbeat.assert_not_awaited()

    @pytest.mark.parametrize(
        ("method", "path", "handler_method", "body"),
        [
            ("get", "", "list_sessions", None),
            ("get", f"/{LIVE_SESSION_ID}", "get_session", None),
            (
                "post",
                f"/{LIVE_SESSION_ID}/heartbeat",
                "record_heartbeat",
                {"connected": True, "token_expires_at": "2026-09-29T12:00:00Z"},
            ),
            ("post", f"/{LIVE_SESSION_ID}/view-token", "issue_view_token", None),
            ("post", f"/{LIVE_SESSION_ID}/end", "end_session", None),
        ],
        ids=["list", "get", "heartbeat", "view-token", "end"],
    )
    def test_session_routes_pass_the_caller_and_the_session(
        self,
        method: str,
        path: str,
        handler_method: str,
        body: dict[str, object] | None,
        client: TestClient,
    ) -> None:
        session = LiveSession(
            id=LIVE_SESSION_ID,
            orbit_id=ORBIT_ID,
            user_id=USER_ID,
            label="run",
            visibility=LiveSessionVisibility.OWNER,
            relay_id=RELAY_ID,
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
            f"{HANDLER}.{handler_method}",
            new_callable=AsyncMock,
            return_value=results[handler_method],
        ) as mock_handler:
            response = client.request(method, LIVE_SESSIONS_PATH + path, json=body)

        assert response.status_code == 200
        assert mock_handler.await_args is not None
        args = mock_handler.await_args.args
        assert args[:3] == (USER_ID, ORGANIZATION_ID, ORBIT_ID)
        if path:
            assert args[3] == LIVE_SESSION_ID

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
    @patch(f"{HANDLER}.issue_view_token", new_callable=AsyncMock)
    def test_view_token_with_a_destination_that_is_not_a_relative_path_is_refused(
        self, mock_issue: AsyncMock, destination: str, client: TestClient
    ) -> None:
        response = client.post(
            f"{LIVE_SESSION_PATH}/view-token", json={"destination": destination}
        )

        assert response.status_code == 422
        mock_issue.assert_not_awaited()

    @patch(
        f"{HANDLER}.issue_view_token",
        new_callable=AsyncMock,
        return_value=VIEW_TOKEN_OUT,
    )
    def test_view_token_passes_the_destination(
        self, mock_issue: AsyncMock, client: TestClient
    ) -> None:
        response = client.post(
            f"{LIVE_SESSION_PATH}/view-token",
            json={"destination": "/experiments/42?tab=metrics"},
        )

        assert response.status_code == 200
        assert mock_issue.await_args is not None
        assert (
            mock_issue.await_args.args[4].destination == "/experiments/42?tab=metrics"
        )
