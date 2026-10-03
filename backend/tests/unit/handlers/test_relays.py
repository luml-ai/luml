from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from luml.handlers.relays import RelayHandler
from luml.infra.exceptions import (
    ApplicationError,
    DatabaseConstraintError,
    InsufficientPermissionsError,
    NotFoundError,
)
from luml.schemas.permissions import Action, Resource
from luml.schemas.relay import (
    Relay,
    RelayCreate,
    RelayCreateIn,
    RelayKind,
    RelayStatus,
    RelayUpdateIn,
)
from luml.settings import config
from pydantic import ValidationError

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
RELAY_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")

REPO = "luml.handlers.relays.RelayRepository"
CHECK_PERMISSIONS = "luml.handlers.relays.PermissionsHandler.check_permissions"

handler = RelayHandler()


def _relay(organization_id: UUID | None = ORGANIZATION_ID) -> Relay:
    return Relay(
        id=RELAY_ID,
        organization_id=organization_id,
        label="lab",
        base_domain="tunnel.example",
        agent_url="wss://relay.tunnel.example/connect",
        status=RelayStatus.ENABLED,
        created_at=datetime.now(UTC),
    )


def _create_in() -> RelayCreateIn:
    return RelayCreateIn(
        label="lab",
        base_domain="tunnel.example",
        agent_url="wss://relay.tunnel.example/connect",
    )


@patch(f"{REPO}.create_relay", new_callable=AsyncMock)
@patch(CHECK_PERMISSIONS, new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_create_relay_stores_the_hash_and_answers_the_token_once(
    mock_check_permissions: AsyncMock, mock_create_relay: AsyncMock
) -> None:
    mock_create_relay.return_value = _relay()

    created = await handler.create_relay(USER_ID, ORGANIZATION_ID, _create_in())

    mock_check_permissions.assert_awaited_once_with(
        ORGANIZATION_ID, USER_ID, Resource.RELAY, Action.CREATE
    )
    stored: RelayCreate = mock_create_relay.await_args_list[0].args[0]
    assert created.token.startswith("dfsrelay_")
    assert stored.organization_id == ORGANIZATION_ID
    assert stored.token_hash == handler.hash_token(created.token)
    assert stored.token_hash != created.token
    assert created.relay.kind == RelayKind.OWN
    assert "token_hash" not in created.relay.model_dump()


@patch(f"{REPO}.create_relay", new_callable=AsyncMock)
@patch(CHECK_PERMISSIONS, new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_create_relay_refuses_a_taken_base_domain_with_a_conflict(
    mock_check_permissions: AsyncMock, mock_create_relay: AsyncMock
) -> None:
    mock_create_relay.side_effect = DatabaseConstraintError()

    with pytest.raises(ApplicationError) as refusal:
        await handler.create_relay(USER_ID, ORGANIZATION_ID, _create_in())

    assert refusal.value.status_code == 409
    assert "base domain" in refusal.value.message


@patch(f"{REPO}.create_relay", new_callable=AsyncMock)
@patch(CHECK_PERMISSIONS, new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_create_relay_without_permission_creates_nothing(
    mock_check_permissions: AsyncMock, mock_create_relay: AsyncMock
) -> None:
    mock_check_permissions.side_effect = InsufficientPermissionsError()

    with pytest.raises(InsufficientPermissionsError):
        await handler.create_relay(USER_ID, ORGANIZATION_ID, _create_in())

    mock_create_relay.assert_not_awaited()


@patch(f"{REPO}.list_usable_relays", new_callable=AsyncMock)
@patch(CHECK_PERMISSIONS, new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_list_relays_includes_managed_ones(
    mock_check_permissions: AsyncMock, mock_list_usable_relays: AsyncMock
) -> None:
    mock_list_usable_relays.return_value = [_relay(), _relay(organization_id=None)]

    relays = await handler.list_relays(USER_ID, ORGANIZATION_ID)

    mock_check_permissions.assert_awaited_once_with(
        ORGANIZATION_ID, USER_ID, Resource.RELAY, Action.LIST
    )
    mock_list_usable_relays.assert_awaited_once_with(ORGANIZATION_ID)
    assert [relay.kind for relay in relays] == [RelayKind.OWN, RelayKind.MANAGED]


@patch(f"{REPO}.get_relay", new_callable=AsyncMock)
@patch(CHECK_PERMISSIONS, new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_get_relay_of_another_organization_is_not_found(
    mock_check_permissions: AsyncMock, mock_get_relay: AsyncMock
) -> None:
    mock_get_relay.return_value = None

    with pytest.raises(NotFoundError):
        await handler.get_relay(USER_ID, ORGANIZATION_ID, RELAY_ID)

    mock_get_relay.assert_awaited_once_with(RELAY_ID, ORGANIZATION_ID)


@patch(f"{REPO}.update_relay", new_callable=AsyncMock)
@patch(f"{REPO}.get_relay", new_callable=AsyncMock)
@patch(CHECK_PERMISSIONS, new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_update_relay_changes_own_relay(
    mock_check_permissions: AsyncMock,
    mock_get_relay: AsyncMock,
    mock_update_relay: AsyncMock,
) -> None:
    mock_get_relay.return_value = _relay()
    mock_update_relay.return_value = _relay().model_copy(
        update={"status": RelayStatus.DRAINING}
    )
    change = RelayUpdateIn(status=RelayStatus.DRAINING)

    updated = await handler.update_relay(USER_ID, ORGANIZATION_ID, RELAY_ID, change)

    mock_check_permissions.assert_awaited_once_with(
        ORGANIZATION_ID, USER_ID, Resource.RELAY, Action.UPDATE
    )
    mock_update_relay.assert_awaited_once_with(RELAY_ID, change)
    assert updated.status == RelayStatus.DRAINING


@patch(f"{REPO}.update_relay", new_callable=AsyncMock)
@patch(f"{REPO}.get_relay", new_callable=AsyncMock)
@patch(CHECK_PERMISSIONS, new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_update_relay_to_a_taken_base_domain_is_a_conflict(
    mock_check_permissions: AsyncMock,
    mock_get_relay: AsyncMock,
    mock_update_relay: AsyncMock,
) -> None:
    mock_get_relay.return_value = _relay()
    mock_update_relay.side_effect = DatabaseConstraintError()

    with pytest.raises(ApplicationError) as refusal:
        await handler.update_relay(
            USER_ID,
            ORGANIZATION_ID,
            RELAY_ID,
            RelayUpdateIn(base_domain="taken.example"),
        )

    assert refusal.value.status_code == 409


@patch(f"{REPO}.rotate_token", new_callable=AsyncMock)
@patch(f"{REPO}.get_relay", new_callable=AsyncMock)
@patch(CHECK_PERMISSIONS, new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_rotate_token_keeps_the_old_token_for_the_overlap(
    mock_check_permissions: AsyncMock,
    mock_get_relay: AsyncMock,
    mock_rotate_token: AsyncMock,
) -> None:
    mock_get_relay.return_value = _relay()
    mock_rotate_token.return_value = _relay()
    before = datetime.now(UTC)

    rotated = await handler.rotate_token(USER_ID, ORGANIZATION_ID, RELAY_ID)

    relay_id, token_hash, overlap_end = mock_rotate_token.await_args_list[0].args
    overlap = timedelta(seconds=config.LIVE_SESSION_RELAY_TOKEN_OVERLAP_SECONDS)
    assert relay_id == RELAY_ID
    assert rotated.token.startswith("dfsrelay_")
    assert token_hash == handler.hash_token(rotated.token)
    assert before + overlap <= overlap_end <= datetime.now(UTC) + overlap


@patch(f"{REPO}.delete_relay", new_callable=AsyncMock)
@patch(f"{REPO}.get_relay", new_callable=AsyncMock)
@patch(CHECK_PERMISSIONS, new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_delete_relay_removes_own_relay(
    mock_check_permissions: AsyncMock,
    mock_get_relay: AsyncMock,
    mock_delete_relay: AsyncMock,
) -> None:
    mock_get_relay.return_value = _relay()
    mock_delete_relay.return_value = True

    await handler.delete_relay(USER_ID, ORGANIZATION_ID, RELAY_ID)

    mock_check_permissions.assert_awaited_once_with(
        ORGANIZATION_ID, USER_ID, Resource.RELAY, Action.DELETE
    )
    mock_delete_relay.assert_awaited_once_with(RELAY_ID)


@patch(f"{REPO}.delete_relay", new_callable=AsyncMock)
@patch(f"{REPO}.rotate_token", new_callable=AsyncMock)
@patch(f"{REPO}.update_relay", new_callable=AsyncMock)
@patch(f"{REPO}.get_relay", new_callable=AsyncMock)
@patch(CHECK_PERMISSIONS, new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_managed_relay_is_read_only(
    mock_check_permissions: AsyncMock,
    mock_get_relay: AsyncMock,
    mock_update_relay: AsyncMock,
    mock_rotate_token: AsyncMock,
    mock_delete_relay: AsyncMock,
) -> None:
    mock_get_relay.return_value = _relay(organization_id=None)

    for attempt in (
        handler.update_relay(
            USER_ID, ORGANIZATION_ID, RELAY_ID, RelayUpdateIn(label="mine")
        ),
        handler.rotate_token(USER_ID, ORGANIZATION_ID, RELAY_ID),
        handler.delete_relay(USER_ID, ORGANIZATION_ID, RELAY_ID),
    ):
        with pytest.raises(ApplicationError, match="Managed relays are read-only"):
            await attempt

    mock_update_relay.assert_not_awaited()
    mock_rotate_token.assert_not_awaited()
    mock_delete_relay.assert_not_awaited()


@patch(f"{REPO}.get_relay_by_token_hash", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_authenticate_token_looks_up_by_hash(
    mock_get_relay_by_token_hash: AsyncMock,
) -> None:
    mock_get_relay_by_token_hash.return_value = _relay()

    relay = await handler.authenticate_token("dfsrelay_secret")

    mock_get_relay_by_token_hash.assert_awaited_once_with(
        handler.hash_token("dfsrelay_secret")
    )
    assert relay is not None


@pytest.mark.parametrize(
    ("base_domain", "problem"),
    [
        ("https://tunnel.example", "scheme"),
        ("tunnel.example:8443", "port"),
        ("tunnel.example/path", "path"),
        ("tunnel.example.", "dot"),
        ("tunnel_example", "bare hostname"),
        ("", "bare hostname"),
    ],
)
def test_base_domain_must_be_a_bare_hostname(base_domain: str, problem: str) -> None:
    with pytest.raises(ValidationError, match=problem):
        RelayCreateIn(
            label="lab", base_domain=base_domain, agent_url="ws://relay.example"
        )


def test_base_domain_is_stored_lower_case() -> None:
    relay = RelayCreateIn(
        label="lab", base_domain="Tunnel.Example", agent_url="ws://relay.example"
    )

    assert relay.base_domain == "tunnel.example"


@pytest.mark.parametrize(
    "agent_url",
    ["https://relay.example/connect", "relay.example:8080", "ws://", "ftp://relay"],
)
def test_agent_address_must_be_a_ws_or_wss_address(agent_url: str) -> None:
    with pytest.raises(ValidationError, match="ws or wss"):
        RelayCreateIn(label="lab", base_domain="tunnel.example", agent_url=agent_url)


def test_update_validates_only_the_given_fields() -> None:
    with pytest.raises(ValidationError, match="port"):
        RelayUpdateIn(base_domain="tunnel.example:80")

    assert RelayUpdateIn(label="new").model_dump(exclude_unset=True) == {"label": "new"}


@pytest.mark.parametrize(
    ("last_seen_ago", "online"),
    [(None, False), (timedelta(minutes=4), True), (timedelta(minutes=6), False)],
)
def test_relay_is_online_while_its_last_report_is_recent(
    last_seen_ago: timedelta | None, online: bool
) -> None:
    last_seen_at = None if last_seen_ago is None else datetime.now(UTC) - last_seen_ago

    relay = _relay().model_copy(update={"last_seen_at": last_seen_at})

    assert relay.online is online
