from typing import Any
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from respx import MockRouter

from luml_api._client import AsyncLumlClient, LumlClient
from luml_api._exceptions import (
    ConflictError,
    MultipleResourcesFoundError,
    PermissionDeniedError,
)
from luml_api._types import Relay, RelayKind, RelayStatus, RelayWithToken
from luml_api.resources.relays import AsyncRelayResource, RelayResource

ORG = "0199c337-09f2-7af1-af5e-83fd7a5b51a0"
RELAYS_PATH = f"/v1/organizations/{ORG}/relays"
OWN_RELAY_ID = "0199d001-0000-7000-8000-000000000001"
MANAGED_RELAY_ID = "0199d001-0000-7000-8000-000000000002"
RELAY_TOKEN = "dfsrelay_plaintext"


def _own_relay(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    record: dict[str, Any] = {
        "id": OWN_RELAY_ID,
        "organization_id": ORG,
        "kind": "own",
        "label": "office",
        "base_domain": "tunnel.example.com",
        "agent_url": "wss://tunnel.example.com/.luml-tunnel/agent",
        "status": "enabled",
        "online": True,
        "last_seen_at": "2026-10-01T12:00:00Z",
        "connected_agents": 2,
        "created_at": "2026-09-30T12:00:00Z",
        "updated_at": None,
    }
    record.update(overrides)
    return record


def _managed_relay() -> dict[str, Any]:
    return _own_relay(
        id=MANAGED_RELAY_ID,
        organization_id=None,
        kind="managed",
        label="eu",
        base_domain="eu.luml.example",
        agent_url="wss://eu.luml.example/.luml-tunnel/agent",
        online=False,
        last_seen_at=None,
        connected_agents=0,
    )


def _with_token(relay: dict[str, Any]) -> dict[str, Any]:
    return {"relay": relay, "token": RELAY_TOKEN}


def _assert_no_secret(relay: Relay) -> None:
    assert not any("hash" in field or "token" in field for field in relay.model_dump())


# ---------------------------------------------------------------------------
# List and get
# ---------------------------------------------------------------------------


def test_relay_list_marks_managed_relays(mock_sync_client: Mock) -> None:
    mock_sync_client.get.return_value = [_own_relay(), _managed_relay()]

    relays = RelayResource(mock_sync_client).list()

    mock_sync_client.get.assert_called_once_with(RELAYS_PATH)
    assert [(relay.label, relay.kind) for relay in relays] == [
        ("office", RelayKind.OWN),
        ("eu", RelayKind.MANAGED),
    ]
    assert relays[1].organization_id is None
    assert relays[0].online is True
    assert relays[0].connected_agents == 2


def test_relay_list_drops_a_hash_the_backend_might_send(
    mock_sync_client: Mock,
) -> None:
    mock_sync_client.get.return_value = [_own_relay(token_hash="leaked")]

    relays = RelayResource(mock_sync_client).list()

    _assert_no_secret(relays[0])


def test_relay_get_by_id(mock_sync_client: Mock) -> None:
    mock_sync_client.get.return_value = _own_relay()

    relay = RelayResource(mock_sync_client).get(OWN_RELAY_ID)

    mock_sync_client.get.assert_called_once_with(f"{RELAYS_PATH}/{OWN_RELAY_ID}")
    assert relay is not None
    assert relay.id == OWN_RELAY_ID


def test_relay_get_by_label(mock_sync_client: Mock) -> None:
    mock_sync_client.get.return_value = [_own_relay(), _managed_relay()]

    relay = RelayResource(mock_sync_client).get("eu")

    mock_sync_client.get.assert_called_once_with(RELAYS_PATH)
    assert relay is not None
    assert relay.id == MANAGED_RELAY_ID


def test_relay_get_by_unknown_label_returns_none(mock_sync_client: Mock) -> None:
    mock_sync_client.get.return_value = [_own_relay()]

    assert RelayResource(mock_sync_client).get("missing") is None


def test_relay_get_by_ambiguous_label_raises(mock_sync_client: Mock) -> None:
    mock_sync_client.get.return_value = [
        _own_relay(),
        _own_relay(id=MANAGED_RELAY_ID),
    ]

    with pytest.raises(MultipleResourcesFoundError):
        RelayResource(mock_sync_client).get("office")


# ---------------------------------------------------------------------------
# Create, update, rotate, delete
# ---------------------------------------------------------------------------


def test_relay_create_returns_plaintext_token_once(mock_sync_client: Mock) -> None:
    mock_sync_client.post.return_value = _with_token(_own_relay())

    created = RelayResource(mock_sync_client).create(
        "office",
        "tunnel.example.com",
        "wss://tunnel.example.com/.luml-tunnel/agent",
    )

    mock_sync_client.post.assert_called_once_with(
        RELAYS_PATH,
        json={
            "label": "office",
            "base_domain": "tunnel.example.com",
            "agent_url": "wss://tunnel.example.com/.luml-tunnel/agent",
        },
    )
    assert isinstance(created, RelayWithToken)
    assert created.token == RELAY_TOKEN
    _assert_no_secret(created.relay)


def test_relay_update_sends_only_given_fields(mock_sync_client: Mock) -> None:
    mock_sync_client.patch.return_value = _own_relay(label="lab")

    relay = RelayResource(mock_sync_client).update(OWN_RELAY_ID, label="lab")

    mock_sync_client.patch.assert_called_once_with(
        f"{RELAYS_PATH}/{OWN_RELAY_ID}", json={"label": "lab"}
    )
    assert isinstance(relay, Relay)
    assert relay.label == "lab"


def test_relay_update_status_to_draining(mock_sync_client: Mock) -> None:
    mock_sync_client.patch.return_value = _own_relay(status="draining")

    relay = RelayResource(mock_sync_client).update(
        OWN_RELAY_ID, status=RelayStatus.DRAINING
    )

    mock_sync_client.patch.assert_called_once_with(
        f"{RELAYS_PATH}/{OWN_RELAY_ID}", json={"status": "draining"}
    )
    assert relay.status == RelayStatus.DRAINING


def test_relay_rotate_token_returns_new_plaintext(mock_sync_client: Mock) -> None:
    mock_sync_client.post.return_value = _with_token(_own_relay())

    rotated = RelayResource(mock_sync_client).rotate_token(OWN_RELAY_ID)

    mock_sync_client.post.assert_called_once_with(
        f"{RELAYS_PATH}/{OWN_RELAY_ID}/rotate-token"
    )
    assert rotated.token == RELAY_TOKEN
    _assert_no_secret(rotated.relay)


def test_relay_delete(mock_sync_client: Mock) -> None:
    mock_sync_client.delete.return_value = None

    RelayResource(mock_sync_client).delete(OWN_RELAY_ID)

    mock_sync_client.delete.assert_called_once_with(f"{RELAYS_PATH}/{OWN_RELAY_ID}")


# ---------------------------------------------------------------------------
# Async
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_relay_list(mock_async_client: AsyncMock) -> None:
    mock_async_client.get.return_value = [_own_relay(), _managed_relay()]

    relays = await AsyncRelayResource(mock_async_client).list()

    mock_async_client.get.assert_called_once_with(RELAYS_PATH)
    assert [relay.kind for relay in relays] == [RelayKind.OWN, RelayKind.MANAGED]


@pytest.mark.asyncio
async def test_async_relay_get_by_id(mock_async_client: AsyncMock) -> None:
    mock_async_client.get.return_value = _own_relay()

    relay = await AsyncRelayResource(mock_async_client).get(OWN_RELAY_ID)

    mock_async_client.get.assert_called_once_with(f"{RELAYS_PATH}/{OWN_RELAY_ID}")
    assert relay is not None
    assert relay.id == OWN_RELAY_ID


@pytest.mark.asyncio
async def test_async_relay_get_by_label(mock_async_client: AsyncMock) -> None:
    mock_async_client.get.return_value = [_own_relay(), _managed_relay()]

    relay = await AsyncRelayResource(mock_async_client).get("eu")

    assert relay is not None
    assert relay.kind == RelayKind.MANAGED


@pytest.mark.asyncio
async def test_async_relay_create(mock_async_client: AsyncMock) -> None:
    mock_async_client.post.return_value = _with_token(_own_relay())

    created = await AsyncRelayResource(mock_async_client).create(
        "office",
        "tunnel.example.com",
        "wss://tunnel.example.com/.luml-tunnel/agent",
    )

    mock_async_client.post.assert_called_once_with(
        RELAYS_PATH,
        json={
            "label": "office",
            "base_domain": "tunnel.example.com",
            "agent_url": "wss://tunnel.example.com/.luml-tunnel/agent",
        },
    )
    assert created.token == RELAY_TOKEN
    _assert_no_secret(created.relay)


@pytest.mark.asyncio
async def test_async_relay_update(mock_async_client: AsyncMock) -> None:
    mock_async_client.patch.return_value = _own_relay(label="lab")

    relay = await AsyncRelayResource(mock_async_client).update(
        OWN_RELAY_ID, label="lab"
    )

    mock_async_client.patch.assert_called_once_with(
        f"{RELAYS_PATH}/{OWN_RELAY_ID}", json={"label": "lab"}
    )
    assert relay.label == "lab"


@pytest.mark.asyncio
async def test_async_relay_rotate_token(mock_async_client: AsyncMock) -> None:
    mock_async_client.post.return_value = _with_token(_own_relay())

    rotated = await AsyncRelayResource(mock_async_client).rotate_token(OWN_RELAY_ID)

    mock_async_client.post.assert_called_once_with(
        f"{RELAYS_PATH}/{OWN_RELAY_ID}/rotate-token"
    )
    assert rotated.token == RELAY_TOKEN


@pytest.mark.asyncio
async def test_async_relay_delete(mock_async_client: AsyncMock) -> None:
    mock_async_client.delete.return_value = None

    await AsyncRelayResource(mock_async_client).delete(OWN_RELAY_ID)

    mock_async_client.delete.assert_called_once_with(f"{RELAYS_PATH}/{OWN_RELAY_ID}")


# ---------------------------------------------------------------------------
# Refusals through the real transport
# ---------------------------------------------------------------------------


def test_update_of_managed_relay_surfaces_read_only_refusal(
    client_with_mocks: LumlClient, respx_mock: MockRouter
) -> None:
    respx_mock.patch(f"{RELAYS_PATH}/{MANAGED_RELAY_ID}").mock(
        return_value=httpx.Response(
            403, json={"detail": "Managed relays are read-only"}
        )
    )

    with pytest.raises(PermissionDeniedError) as error:
        client_with_mocks.relays.update(MANAGED_RELAY_ID, label="mine")

    assert "read-only" in str(error.value)


@pytest.mark.asyncio
async def test_async_update_of_managed_relay_surfaces_read_only_refusal(
    async_client_with_mocks: AsyncLumlClient, respx_mock: MockRouter
) -> None:
    respx_mock.patch(f"{RELAYS_PATH}/{MANAGED_RELAY_ID}").mock(
        return_value=httpx.Response(
            403, json={"detail": "Managed relays are read-only"}
        )
    )

    with pytest.raises(PermissionDeniedError):
        await async_client_with_mocks.relays.update(MANAGED_RELAY_ID, label="mine")


def test_delete_of_relay_with_unended_sessions_surfaces_conflict(
    client_with_mocks: LumlClient, respx_mock: MockRouter
) -> None:
    respx_mock.delete(f"{RELAYS_PATH}/{OWN_RELAY_ID}").mock(
        return_value=httpx.Response(
            409, json={"detail": "Relay has 2 sessions that have not ended"}
        )
    )

    with pytest.raises(ConflictError) as error:
        client_with_mocks.relays.delete(OWN_RELAY_ID)

    assert "2 sessions" in str(error.value)
