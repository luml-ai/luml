from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from luml.schemas.relay import Relay, RelayReportIn, RelayStatus, SessionTokenVerdict
from luml.schemas.user import UserOut
from luml.service import AppService

RELAY_ID = UUID("0199c337-09f4-7a3b-8c1d-2e3f4a5b6c7d")
USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
GRANT_ID = UUID("0199c337-09f6-7a3b-8c1d-2e3f4a5b6c7d")
RELAY_TOKEN = "dfsrelay_secret"
USER_API_KEY = "dfs_secret"

FIND_RELAY = "luml.handlers.relays.RelayRepository.get_relay_by_token_hash"
FIND_USER = "luml.handlers.api_keys.APIKeyHandler.authenticate_api_key"
HANDLER = "luml.api.relays.RelayWorkerHandler"


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


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


ROUTES = [
    ("get", "/relays/v1/self", None),
    ("post", "/relays/v1/tokens/validate", {"token": "t"}),
    ("post", "/relays/v1/grants/check", {"grant_id": str(GRANT_ID)}),
    ("post", "/relays/v1/report", {"connected_agents": 3, "capabilities": {}}),
]


@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
@patch(FIND_USER, new_callable=AsyncMock)
@patch(FIND_RELAY, new_callable=AsyncMock, return_value=None)
def test_a_refused_relay_token_answers_401(
    mock_find_relay: AsyncMock,
    mock_find_user: AsyncMock,
    method: str,
    path: str,
    body: dict[str, object] | None,
) -> None:
    response = TestClient(AppService()).request(
        method, path, json=body, headers=_bearer(RELAY_TOKEN)
    )

    assert response.status_code == 401
    mock_find_user.assert_not_awaited()


@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
@patch(FIND_RELAY, new_callable=AsyncMock)
@patch(FIND_USER, new_callable=AsyncMock)
def test_a_user_api_key_lacks_the_relay_scope(
    mock_find_user: AsyncMock,
    mock_find_relay: AsyncMock,
    method: str,
    path: str,
    body: dict[str, object] | None,
) -> None:
    mock_find_user.return_value = UserOut(
        id=USER_ID, email="caller@example.com", full_name="Caller", disabled=False
    )

    response = TestClient(AppService()).request(
        method, path, json=body, headers=_bearer(USER_API_KEY)
    )

    assert response.status_code == 403
    mock_find_relay.assert_not_awaited()


@patch(FIND_RELAY, new_callable=AsyncMock, return_value=_relay())
def test_a_relay_token_is_refused_on_organization_routes(
    mock_find_relay: AsyncMock,
) -> None:
    response = TestClient(AppService()).get(
        f"/v1/organizations/{ORGANIZATION_ID}/relays", headers=_bearer(RELAY_TOKEN)
    )

    assert response.status_code == 403


@patch(f"{HANDLER}.validate_token", new_callable=AsyncMock)
@patch(FIND_RELAY, new_callable=AsyncMock, return_value=_relay())
def test_validate_passes_the_calling_relay_and_answers_inactive_with_200(
    mock_find_relay: AsyncMock, mock_validate: AsyncMock
) -> None:
    mock_validate.return_value = SessionTokenVerdict(active=False)

    response = TestClient(AppService()).post(
        "/relays/v1/tokens/validate",
        json={"token": "opaque", "launch": True},
        headers=_bearer(RELAY_TOKEN),
    )

    assert response.status_code == 200
    assert response.json()["active"] is False
    assert mock_validate.await_args is not None
    relay_id, data = mock_validate.await_args.args
    assert (relay_id, data.token, data.launch) == (RELAY_ID, "opaque", True)


@patch(f"{HANDLER}.check_grant", new_callable=AsyncMock)
@patch(FIND_RELAY, new_callable=AsyncMock, return_value=_relay())
def test_check_grant_passes_the_calling_relay(
    mock_find_relay: AsyncMock, mock_check: AsyncMock
) -> None:
    mock_check.return_value = {"active": False}

    response = TestClient(AppService()).post(
        "/relays/v1/grants/check",
        json={"grant_id": str(GRANT_ID)},
        headers=_bearer(RELAY_TOKEN),
    )

    assert response.status_code == 200
    mock_check.assert_awaited_once_with(RELAY_ID, GRANT_ID)


@patch(f"{HANDLER}.report", new_callable=AsyncMock)
@patch(FIND_RELAY, new_callable=AsyncMock, return_value=_relay())
def test_report_records_the_connected_agents_of_the_calling_relay(
    mock_find_relay: AsyncMock, mock_report: AsyncMock
) -> None:
    capabilities = {"sessions": {"version": 1, "api_versions": [1]}}

    response = TestClient(AppService()).post(
        "/relays/v1/report",
        json={"connected_agents": 3, "capabilities": capabilities},
        headers=_bearer(RELAY_TOKEN),
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
)
@patch(f"{HANDLER}.report", new_callable=AsyncMock)
@patch(FIND_RELAY, new_callable=AsyncMock, return_value=_relay())
def test_report_refuses_missing_or_invalid_capabilities(
    mock_find_relay: AsyncMock, mock_report: AsyncMock, body: dict[str, object]
) -> None:
    response = TestClient(AppService()).post(
        "/relays/v1/report", json=body, headers=_bearer(RELAY_TOKEN)
    )

    assert response.status_code == 422
    mock_report.assert_not_awaited()


@patch(f"{HANDLER}.report", new_callable=AsyncMock)
@patch(FIND_RELAY, new_callable=AsyncMock, return_value=_relay())
def test_report_refuses_a_negative_count(
    mock_find_relay: AsyncMock, mock_report: AsyncMock
) -> None:
    response = TestClient(AppService()).post(
        "/relays/v1/report",
        json={"connected_agents": -1, "capabilities": {}},
        headers=_bearer(RELAY_TOKEN),
    )

    assert response.status_code == 422
    mock_report.assert_not_awaited()


@patch("luml.handlers.relay_worker.RelayRepository.get_relay", new_callable=AsyncMock)
@patch(FIND_RELAY, new_callable=AsyncMock, return_value=_relay())
def test_describe_answers_the_calling_relay(
    mock_find_relay: AsyncMock, mock_get_relay: AsyncMock
) -> None:
    mock_get_relay.return_value = _relay()

    response = TestClient(AppService()).get(
        "/relays/v1/self", headers=_bearer(RELAY_TOKEN)
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["id"], body["base_domain"]) == (str(RELAY_ID), "sessions.example")
    assert body["app_origins"]
    assert body["app_url"]
    mock_get_relay.assert_awaited_once_with(RELAY_ID)
