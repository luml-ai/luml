from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from luml.schemas.relay import Relay, RelayReportIn, RelayStatus, SessionTokenVerdict

from tests.support.auth import ANONYMOUS, API_KEY_USER, Principal, relay
from tests.support.ids import GRANT_ID, ORGANIZATION_ID, RELAY_ID

HANDLER = "luml.handlers.relay_worker.RelayWorkerHandler"
RELAYS_PATH = f"/v1/organizations/{ORGANIZATION_ID}/relays"
SELF_PATH = "/relays/v1/self"
VALIDATE_PATH = "/relays/v1/tokens/validate"
GRANTS_PATH = "/relays/v1/grants/check"
REPORT_PATH = "/relays/v1/report"
ROUTES = [
    ("get", SELF_PATH, None),
    ("post", VALIDATE_PATH, {"token": "t"}),
    ("post", GRANTS_PATH, {"grant_id": str(GRANT_ID)}),
    ("post", REPORT_PATH, {"connected_agents": 3, "capabilities": {}}),
]
ROUTE_IDS = ["self", "validate", "grants", "report"]


def _relay() -> Relay:
    return Relay(
        id=RELAY_ID,
        organization_id=ORGANIZATION_ID,
        label="lab",
        base_domain="sessions.example",
        agent_url="wss://sessions.example/connect",
        status=RelayStatus.ENABLED,
        created_at=datetime.now(UTC),
    )


class TestRelayWorkerRoutes:
    @pytest.fixture
    def principal(self, request: pytest.FixtureRequest) -> Principal:
        return getattr(request, "param", relay())

    @pytest.mark.parametrize(("method", "path", "body"), ROUTES, ids=ROUTE_IDS)
    @pytest.mark.parametrize("principal", [ANONYMOUS], indirect=True)
    def test_a_refused_relay_token_answers_401(
        self,
        method: str,
        path: str,
        body: dict[str, object] | None,
        client: TestClient,
    ) -> None:
        response = client.request(method, path, json=body)

        assert response.status_code == 401

    @pytest.mark.parametrize(("method", "path", "body"), ROUTES, ids=ROUTE_IDS)
    @pytest.mark.parametrize("principal", [API_KEY_USER], indirect=True)
    def test_a_user_api_key_lacks_the_relay_scope(
        self,
        method: str,
        path: str,
        body: dict[str, object] | None,
        client: TestClient,
    ) -> None:
        response = client.request(method, path, json=body)

        assert response.status_code == 403

    def test_a_relay_token_is_refused_on_organization_routes(
        self, client: TestClient
    ) -> None:
        response = client.get(RELAYS_PATH)

        assert response.status_code == 403

    @patch(f"{HANDLER}.validate_token", new_callable=AsyncMock)
    def test_validate_passes_the_calling_relay_and_answers_inactive_with_200(
        self, mock_validate: AsyncMock, client: TestClient
    ) -> None:
        mock_validate.return_value = SessionTokenVerdict(active=False)

        response = client.post(VALIDATE_PATH, json={"token": "opaque", "launch": True})

        assert response.status_code == 200
        assert response.json()["active"] is False
        assert mock_validate.await_args is not None
        relay_id, data = mock_validate.await_args.args
        assert (relay_id, data.token, data.launch) == (RELAY_ID, "opaque", True)

    @patch(f"{HANDLER}.check_grant", new_callable=AsyncMock)
    def test_check_grant_passes_the_calling_relay(
        self, mock_check: AsyncMock, client: TestClient
    ) -> None:
        mock_check.return_value = {"active": False}

        response = client.post(GRANTS_PATH, json={"grant_id": str(GRANT_ID)})

        assert response.status_code == 200
        mock_check.assert_awaited_once_with(RELAY_ID, GRANT_ID)

    @patch(f"{HANDLER}.report", new_callable=AsyncMock)
    def test_report_records_the_connected_agents_of_the_calling_relay(
        self, mock_report: AsyncMock, client: TestClient
    ) -> None:
        capabilities = {"sessions": {"version": 1, "api_versions": [1]}}

        response = client.post(
            REPORT_PATH, json={"connected_agents": 3, "capabilities": capabilities}
        )

        assert response.status_code == 204
        mock_report.assert_awaited_once_with(
            RELAY_ID, RelayReportIn(connected_agents=3, capabilities=capabilities)
        )

    @pytest.mark.parametrize(
        "body",
        [
            {"connected_agents": 3},
            {"connected_agents": 3, "capabilities": {"replay": {"version": 1}}},
            {"connected_agents": 3, "capabilities": {"sessions": {"version": 0}}},
        ],
        ids=["missing", "unknown", "old-version"],
    )
    @patch(f"{HANDLER}.report", new_callable=AsyncMock)
    def test_report_refuses_missing_or_invalid_capabilities(
        self, mock_report: AsyncMock, body: dict[str, object], client: TestClient
    ) -> None:
        response = client.post(REPORT_PATH, json=body)

        assert response.status_code == 422
        mock_report.assert_not_awaited()

    @patch(f"{HANDLER}.report", new_callable=AsyncMock)
    def test_report_refuses_a_negative_count(
        self, mock_report: AsyncMock, client: TestClient
    ) -> None:
        response = client.post(
            REPORT_PATH, json={"connected_agents": -1, "capabilities": {}}
        )

        assert response.status_code == 422
        mock_report.assert_not_awaited()

    @patch(
        "luml.handlers.relay_worker.RelayRepository.get_relay", new_callable=AsyncMock
    )
    def test_describe_answers_the_calling_relay(
        self, mock_get_relay: AsyncMock, client: TestClient
    ) -> None:
        mock_get_relay.return_value = _relay()

        response = client.get(SELF_PATH)

        assert response.status_code == 200
        body = response.json()
        assert (body["id"], body["base_domain"]) == (str(RELAY_ID), "sessions.example")
        assert body["app_origins"]
        assert body["app_url"]
        mock_get_relay.assert_awaited_once_with(RELAY_ID)
