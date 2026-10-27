from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from luml.infra.exceptions import ApplicationError
from luml.schemas.relay import Relay, RelayStatus, RelayTokenOut

from tests.support.auth import ANONYMOUS, relay
from tests.support.ids import ORGANIZATION_ID, RELAY_ID, USER_ID

RELAYS_PATH = f"/v1/organizations/{ORGANIZATION_ID}/relays"
RELAY_PATH = f"{RELAYS_PATH}/{RELAY_ID}"
HANDLER = "luml.handlers.relays.RelayHandler"


def _relay() -> Relay:
    return Relay(
        id=RELAY_ID,
        organization_id=ORGANIZATION_ID,
        label="lab",
        base_domain="sessions.example",
        agent_url="wss://relay.sessions.example/connect",
        status=RelayStatus.ENABLED,
        created_at=datetime.now(UTC),
    )


class TestOrganizationRelays:
    @pytest.mark.parametrize("principal", [ANONYMOUS], indirect=True)
    @patch(f"{HANDLER}.list_relays", new_callable=AsyncMock)
    def test_relays_require_authentication(
        self, mock_list_relays: AsyncMock, client: TestClient
    ) -> None:
        response = client.get(RELAYS_PATH)

        assert response.status_code == 401
        mock_list_relays.assert_not_awaited()

    @pytest.mark.parametrize("principal", [relay()], ids=["relay"], indirect=True)
    @patch(f"{HANDLER}.list_relays", new_callable=AsyncMock)
    def test_relay_token_is_refused_on_organization_routes(
        self, mock_list_relays: AsyncMock, client: TestClient
    ) -> None:
        response = client.get(RELAYS_PATH)

        assert response.status_code == 403
        mock_list_relays.assert_not_awaited()

    @patch(f"{HANDLER}.list_relays", new_callable=AsyncMock)
    def test_list_relays_answers_kind_and_online_without_hashes(
        self, mock_list_relays: AsyncMock, client: TestClient
    ) -> None:
        mock_list_relays.return_value = [_relay()]

        response = client.get(RELAYS_PATH)

        assert response.status_code == 200
        mock_list_relays.assert_awaited_once_with(USER_ID, ORGANIZATION_ID)
        [listed] = response.json()
        assert listed["kind"] == "own"
        assert listed["online"] is False
        assert listed["status"] == "enabled"
        assert not any("hash" in field for field in listed)

    @patch(f"{HANDLER}.create_relay", new_callable=AsyncMock)
    def test_create_relay_answers_the_plaintext_token(
        self, mock_create_relay: AsyncMock, client: TestClient
    ) -> None:
        mock_create_relay.return_value = RelayTokenOut(
            relay=_relay(), token="dfsrelay_secret"
        )

        response = client.post(
            RELAYS_PATH,
            json={
                "label": "lab",
                "base_domain": "Sessions.Example",
                "agent_url": "wss://relay.sessions.example/connect",
            },
        )

        assert response.status_code == 200
        assert response.json()["token"] == "dfsrelay_secret"
        assert response.json()["relay"]["kind"] == "own"
        created = mock_create_relay.await_args_list[0].args[2]
        assert created.base_domain == "sessions.example"

    @patch(f"{HANDLER}.create_relay", new_callable=AsyncMock)
    def test_create_relay_with_an_invalid_address_is_refused(
        self, mock_create_relay: AsyncMock, client: TestClient
    ) -> None:
        response = client.post(
            RELAYS_PATH,
            json={
                "label": "lab",
                "base_domain": "sessions.example",
                "agent_url": "https://relay.sessions.example/connect",
            },
        )

        assert response.status_code == 422
        assert "ws or wss" in response.text
        mock_create_relay.assert_not_awaited()

    @patch(f"{HANDLER}.update_relay", new_callable=AsyncMock)
    def test_update_relay_forwards_the_change(
        self, mock_update_relay: AsyncMock, client: TestClient
    ) -> None:
        mock_update_relay.return_value = _relay()

        response = client.patch(RELAY_PATH, json={"status": "draining"})

        assert response.status_code == 200
        user_id, organization_id, relay_id, change = mock_update_relay.await_args_list[
            0
        ].args
        assert (user_id, organization_id, relay_id) == (
            USER_ID,
            ORGANIZATION_ID,
            RELAY_ID,
        )
        assert change.model_dump(exclude_unset=True) == {"status": "draining"}

    @patch(f"{HANDLER}.update_relay", new_callable=AsyncMock)
    def test_managed_relay_refusal_reaches_the_caller(
        self, mock_update_relay: AsyncMock, client: TestClient
    ) -> None:
        mock_update_relay.side_effect = ApplicationError(
            "Managed relays are read-only", 403
        )

        response = client.patch(RELAY_PATH, json={"label": "x"})

        assert response.status_code == 403
        assert response.json()["detail"] == "Managed relays are read-only"

    @patch(f"{HANDLER}.rotate_token", new_callable=AsyncMock)
    def test_rotate_token_answers_the_new_token(
        self, mock_rotate_token: AsyncMock, client: TestClient
    ) -> None:
        mock_rotate_token.return_value = RelayTokenOut(
            relay=_relay(), token="dfsrelay_rotated"
        )

        response = client.post(f"{RELAY_PATH}/rotate-token")

        assert response.status_code == 200
        assert response.json()["token"] == "dfsrelay_rotated"
        mock_rotate_token.assert_awaited_once_with(USER_ID, ORGANIZATION_ID, RELAY_ID)

    @patch(f"{HANDLER}.get_relay", new_callable=AsyncMock)
    def test_get_relay_forwards_path_parameters(
        self, mock_get_relay: AsyncMock, client: TestClient
    ) -> None:
        mock_get_relay.return_value = _relay()

        response = client.get(RELAY_PATH)

        assert response.status_code == 200
        assert response.json()["id"] == str(RELAY_ID)
        mock_get_relay.assert_awaited_once_with(USER_ID, ORGANIZATION_ID, RELAY_ID)

    @patch(f"{HANDLER}.delete_relay", new_callable=AsyncMock)
    def test_delete_relay_answers_no_content(
        self, mock_delete_relay: AsyncMock, client: TestClient
    ) -> None:
        response = client.delete(RELAY_PATH)

        assert response.status_code == 204
        mock_delete_relay.assert_awaited_once_with(USER_ID, ORGANIZATION_ID, RELAY_ID)
