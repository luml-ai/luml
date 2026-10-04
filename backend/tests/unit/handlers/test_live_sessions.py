from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import pytest
from luml.handlers.live_sessions import LiveSessionHandler
from luml.infra.exceptions import (
    ApplicationError,
    InsufficientPermissionsError,
    LiveSessionEndedError,
    NotFoundError,
    OrganizationLimitReachedError,
)
from luml.repositories.limits import OrganizationResource
from luml.schemas.live_session import (
    LiveSession,
    LiveSessionHeartbeatIn,
    LiveSessionStartIn,
    LiveSessionStatus,
    LiveSessionTokenCreate,
    LiveSessionViewTokenIn,
    LiveSessionVisibility,
    SessionTokenKind,
)
from luml.schemas.orbit import Orbit
from luml.schemas.permissions import Action, Resource
from luml.schemas.relay import Relay, RelayStatus
from luml.settings import config

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
OTHER_USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24c")
ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
ORBIT_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")
SESSION_ID = "k3f9x2ab"
RELAY_ID = UUID("0199c337-09f4-7a3b-8c1d-2e3f4a5b6c7d")
OTHER_RELAY_ID = UUID("0199c337-09f4-7a3b-8c1d-2e3f4a5b6c7e")
BASE_DOMAIN = "sessions.example"
AGENT_URL = "wss://sessions.example/connect"
SESSIONS: dict[str, dict[str, Any]] = {"sessions": {"version": 1, "api_versions": [1]}}

REPO = "luml.handlers.live_sessions.LiveSessionRepository"
ORBIT_REPO = "luml.handlers.live_sessions.OrbitRepository"
RELAY_REPO = "luml.handlers.live_sessions.RelayRepository"
TOKEN_REPO = "luml.handlers.live_sessions.LiveSessionTokenRepository"
CHECK_PERMISSIONS = "luml.handlers.live_sessions.PermissionsHandler.check_permissions"


ENABLED_SETTINGS: dict[str, Any] = {
    "LIVE_SESSION_EXPOSE_TOKEN_LIFETIME_SECONDS": 600,
    "LIVE_SESSION_VIEW_TOKEN_LIFETIME_SECONDS": 300,
    "APP_EMAIL_URL": "https://app.luml.ai/",
}


def _handler(**overrides: Any) -> LiveSessionHandler:  # noqa: ANN401
    settings = config.model_copy(update={**ENABLED_SETTINGS, **overrides})
    return LiveSessionHandler(settings)


def _relay(
    relay_id: UUID = RELAY_ID,
    organization_id: UUID | None = ORGANIZATION_ID,
    status: RelayStatus = RelayStatus.ENABLED,
    base_domain: str = BASE_DOMAIN,
    agent_url: str = AGENT_URL,
    capabilities: dict[str, dict[str, Any]] | None = None,
) -> Relay:
    return Relay(
        id=relay_id,
        organization_id=organization_id,
        label="lab",
        base_domain=base_domain,
        agent_url=agent_url,
        status=status,
        capabilities=SESSIONS if capabilities is None else capabilities,
        created_at=datetime.now(UTC),
    )


def _orbit(relay_id: UUID | None = RELAY_ID) -> Orbit:
    return Orbit(
        id=ORBIT_ID,
        name="orbit",
        organization_id=ORGANIZATION_ID,
        bucket_secret_id=UUID("0199c337-09f5-7a3b-8c1d-2e3f4a5b6c7d"),
        relay_id=relay_id,
        created_at=datetime.now(UTC),
    )


def _session(
    user_id: UUID = USER_ID,
    last_heartbeat_ago: timedelta | None = timedelta(seconds=5),
    connected: bool = True,
    ended_at: datetime | None = None,
    relay_id: UUID | None = RELAY_ID,
    started_ago: timedelta = timedelta(hours=2),
) -> LiveSession:
    now = datetime.now(UTC)
    return LiveSession(
        id=SESSION_ID,
        orbit_id=ORBIT_ID,
        user_id=user_id,
        label="training run",
        visibility=LiveSessionVisibility.OWNER,
        relay_id=relay_id,
        started_at=now - started_ago,
        last_heartbeat_at=now - last_heartbeat_ago if last_heartbeat_ago else None,
        connected=connected,
        ended_at=ended_at,
    )


def _issued(repo: dict[str, AsyncMock]) -> list[LiveSessionTokenCreate]:
    return [call.args[0] for call in repo["issue_token"].await_args_list]


def _assert_lifetime(issued: LiveSessionTokenCreate, seconds: int) -> None:
    remaining = issued.expires_at - datetime.now(UTC)
    assert timedelta(seconds=seconds - 5) < remaining <= timedelta(seconds=seconds)


@pytest.fixture
def check_permissions() -> Iterator[AsyncMock]:
    with patch(CHECK_PERMISSIONS, new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def repo() -> Iterator[dict[str, AsyncMock]]:
    targets = {
        "check_session_slot": f"{REPO}.check_session_slot",
        "create_live_session": f"{REPO}.create_live_session",
        "get_live_session": f"{REPO}.get_live_session",
        "list_live_sessions": f"{REPO}.list_live_sessions",
        "record_heartbeat": f"{REPO}.record_heartbeat",
        "end_live_session": f"{REPO}.end_live_session",
        "get_orbit_simple": f"{ORBIT_REPO}.get_orbit_simple",
        "get_relay": f"{RELAY_REPO}.get_relay",
        "record_viewer_activity": f"{REPO}.record_viewer_activity",
        "issue_token": f"{TOKEN_REPO}.issue_token",
    }
    patches = {
        name: patch(target, new_callable=AsyncMock) for name, target in targets.items()
    }
    mocks = {name: p.start() for name, p in patches.items()}
    mocks["get_orbit_simple"].return_value = _orbit()
    mocks["get_relay"].return_value = _relay()
    mocks["issue_token"].side_effect = [f"opaque-{n}" for n in range(5)]
    yield mocks
    for p in patches.values():
        p.stop()


@pytest.mark.asyncio
async def test_start_session(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    repo["create_live_session"].return_value = _session(last_heartbeat_ago=None)
    handler = _handler()

    result = await handler.start_session(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(label="training run")
    )

    check_permissions.assert_awaited_once_with(
        ORGANIZATION_ID, USER_ID, Resource.LIVE_SESSION, Action.CREATE, ORBIT_ID
    )
    repo["get_orbit_simple"].assert_awaited_once_with(ORBIT_ID, ORGANIZATION_ID)
    repo["get_relay"].assert_awaited_once_with(RELAY_ID)
    repo["check_session_slot"].assert_awaited_once_with(
        ORGANIZATION_ID, OrganizationResource.OWN_RELAY_SESSIONS, None
    )
    assert repo["create_live_session"].await_args is not None
    created, organization_id, limit, replacing = repo[
        "create_live_session"
    ].await_args.args
    assert replacing is None
    assert (
        created.orbit_id,
        created.user_id,
        created.label,
        created.visibility,
        created.relay_id,
    ) == (ORBIT_ID, USER_ID, "training run", LiveSessionVisibility.OWNER, RELAY_ID)
    assert (organization_id, limit) == (
        ORGANIZATION_ID,
        OrganizationResource.OWN_RELAY_SESSIONS,
    )
    assert result.id == SESSION_ID
    assert result.public_url == "https://k3f9x2ab.sessions.example"
    assert "app_url" not in result.model_dump()
    assert result.agent_url == AGENT_URL
    assert result.heartbeat_interval == 30
    [issued] = _issued(repo)
    assert (issued.kind, issued.session_id, issued.user_id) == (
        SessionTokenKind.EXPOSE,
        SESSION_ID,
        USER_ID,
    )
    _assert_lifetime(issued, 600)
    assert result.expose_token == "opaque-0"
    assert result.token_expires_at == issued.expires_at


@pytest.mark.asyncio
async def test_public_url_keeps_the_scheme_and_port_of_the_agent_address(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    repo["create_live_session"].return_value = _session(last_heartbeat_ago=None)
    repo["get_relay"].return_value = _relay(
        base_domain="sessions.localhost",
        agent_url="ws://sessions.localhost:8090/connect",
    )
    handler = _handler()

    result = await handler.start_session(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(label="dev")
    )

    assert result.public_url == "http://k3f9x2ab.sessions.localhost:8090"


@pytest.mark.asyncio
async def test_someone_outside_the_orbit_cannot_start_a_session(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    check_permissions.side_effect = InsufficientPermissionsError()

    with pytest.raises(InsufficientPermissionsError):
        await _handler().start_session(
            OTHER_USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            LiveSessionStartIn(label="run"),
        )

    repo["create_live_session"].assert_not_awaited()


@pytest.mark.asyncio
async def test_heartbeat_renews_a_token_about_to_expire(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    repo["get_live_session"].return_value = _session()
    repo["record_heartbeat"].return_value = _session()
    handler = _handler()

    result = await handler.record_heartbeat(
        USER_ID,
        ORGANIZATION_ID,
        ORBIT_ID,
        SESSION_ID,
        LiveSessionHeartbeatIn(
            connected=True,
            token_expires_at=datetime.now(UTC) + timedelta(minutes=2),
        ),
    )

    check_permissions.assert_awaited_once_with(
        ORGANIZATION_ID, USER_ID, Resource.LIVE_SESSION, Action.UPDATE, ORBIT_ID
    )
    repo["record_heartbeat"].assert_awaited_once_with(SESSION_ID, True)
    assert result.status == LiveSessionStatus.LIVE
    [issued] = _issued(repo)
    assert (issued.kind, issued.session_id) == (SessionTokenKind.EXPOSE, SESSION_ID)
    _assert_lifetime(issued, 600)
    assert result.expose_token == "opaque-0"
    assert result.token_expires_at == issued.expires_at


@pytest.mark.asyncio
async def test_heartbeat_well_before_expiry_carries_no_token(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    repo["get_live_session"].return_value = _session()
    repo["record_heartbeat"].return_value = _session(connected=False)

    result = await _handler().record_heartbeat(
        USER_ID,
        ORGANIZATION_ID,
        ORBIT_ID,
        SESSION_ID,
        LiveSessionHeartbeatIn(
            connected=False,
            token_expires_at=datetime.now(UTC) + timedelta(minutes=9),
        ),
    )

    repo["record_heartbeat"].assert_awaited_once_with(SESSION_ID, False)
    assert result.status == LiveSessionStatus.DISCONNECTED
    assert result.expose_token is None
    assert result.token_expires_at is None
    repo["issue_token"].assert_not_awaited()


@pytest.mark.parametrize(
    "stored",
    [
        _session(ended_at=datetime.now(UTC) - timedelta(minutes=1)),
        _session(last_heartbeat_ago=timedelta(hours=1, minutes=1)),
        _session(started_ago=timedelta(days=8)),
    ],
    ids=["ended", "silent-for-an-hour", "no-viewer-for-the-idle-period"],
)
@pytest.mark.asyncio
async def test_heartbeat_to_an_ended_session_says_so_and_carries_no_token(
    check_permissions: AsyncMock,
    repo: dict[str, AsyncMock],
    stored: LiveSession,
) -> None:
    repo["get_live_session"].return_value = stored
    repo["record_heartbeat"].return_value = stored

    result = await _handler().record_heartbeat(
        USER_ID,
        ORGANIZATION_ID,
        ORBIT_ID,
        SESSION_ID,
        LiveSessionHeartbeatIn(connected=True, token_expires_at=datetime.now(UTC)),
    )

    assert result.status == LiveSessionStatus.ENDED
    assert result.expose_token is None
    repo["issue_token"].assert_not_awaited()


@pytest.mark.parametrize(
    "stored",
    [_session(ended_at=datetime.now(UTC)), _session(started_ago=timedelta(days=8))],
    ids=["ended", "no-viewer-for-the-idle-period"],
)
@pytest.mark.asyncio
async def test_view_token_is_refused_for_an_ended_session(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock], stored: LiveSession
) -> None:
    repo["get_live_session"].return_value = stored

    with pytest.raises(LiveSessionEndedError):
        await _handler().issue_view_token(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, SESSION_ID
        )

    repo["issue_token"].assert_not_awaited()
    repo["record_viewer_activity"].assert_not_awaited()


@pytest.mark.parametrize("connected", [True, False], ids=["live", "disconnected"])
@pytest.mark.asyncio
async def test_view_token_fits_one_viewer_and_one_session(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock], connected: bool
) -> None:
    repo["get_live_session"].return_value = _session(connected=connected)
    handler = _handler()

    result = await handler.issue_view_token(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, SESSION_ID
    )

    check_permissions.assert_awaited_once_with(
        ORGANIZATION_ID, USER_ID, Resource.LIVE_SESSION, Action.READ, ORBIT_ID
    )
    repo["get_relay"].assert_awaited_once_with(RELAY_ID)
    [issued] = _issued(repo)
    assert (issued.kind, issued.session_id, issued.user_id, issued.destination) == (
        SessionTokenKind.VIEW,
        SESSION_ID,
        USER_ID,
        None,
    )
    _assert_lifetime(issued, 300)
    assert (result.token, result.expires_at) == ("opaque-0", issued.expires_at)
    repo["record_viewer_activity"].assert_awaited_once_with(SESSION_ID)
    launch = urlsplit(result.launch_url)
    assert f"{launch.scheme}://{launch.netloc}{launch.path}" == (
        "https://k3f9x2ab.sessions.example/.luml-relay/launch"
    )
    assert parse_qs(launch.query) == {"token": [result.token]}


@pytest.mark.asyncio
async def test_view_token_stores_the_destination_outside_the_launch_address(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    repo["get_live_session"].return_value = _session()

    result = await _handler().issue_view_token(
        USER_ID,
        ORGANIZATION_ID,
        ORBIT_ID,
        SESSION_ID,
        LiveSessionViewTokenIn(destination="/experiments/42?tab=metrics"),
    )

    [issued] = _issued(repo)
    assert issued.destination == "/experiments/42?tab=metrics"
    launch = urlsplit(result.launch_url)
    assert launch.path == "/.luml-relay/launch"
    assert parse_qs(launch.query) == {"token": [result.token]}


@pytest.mark.asyncio
async def test_list_asks_the_repository_for_the_callers_visible_sessions(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    own = _session()
    repo["list_live_sessions"].return_value = [own]

    result = await _handler().list_sessions(USER_ID, ORGANIZATION_ID, ORBIT_ID)

    assert result == [own]
    repo["list_live_sessions"].assert_awaited_once_with(ORBIT_ID, USER_ID)
    check_permissions.assert_awaited_once_with(
        ORGANIZATION_ID, USER_ID, Resource.LIVE_SESSION, Action.LIST, ORBIT_ID
    )


@pytest.mark.parametrize(
    "stored",
    [
        None,
        _session(user_id=OTHER_USER_ID),
        _session().model_copy(
            update={"orbit_id": UUID("0199c337-09f3-753e-9def-b27745e69be7")}
        ),
    ],
    ids=["missing", "another-user", "another-orbit"],
)
@pytest.mark.parametrize("operation", ["get", "heartbeat", "view_token", "end"])
@pytest.mark.asyncio
async def test_a_session_of_someone_else_is_not_found(
    check_permissions: AsyncMock,
    repo: dict[str, AsyncMock],
    stored: LiveSession | None,
    operation: str,
) -> None:
    repo["get_live_session"].return_value = stored
    handler = _handler()
    calls: dict[str, Callable[[], Awaitable[object]]] = {
        "get": lambda: handler.get_session(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, SESSION_ID
        ),
        "heartbeat": lambda: handler.record_heartbeat(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            SESSION_ID,
            LiveSessionHeartbeatIn(connected=True, token_expires_at=datetime.now(UTC)),
        ),
        "view_token": lambda: handler.issue_view_token(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, SESSION_ID
        ),
        "end": lambda: handler.end_session(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, SESSION_ID
        ),
    }

    with pytest.raises(NotFoundError):
        await calls[operation]()

    repo["record_heartbeat"].assert_not_awaited()
    repo["end_live_session"].assert_not_awaited()
    repo["issue_token"].assert_not_awaited()


@pytest.mark.asyncio
async def test_end_session(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    ended = _session(ended_at=datetime.now(UTC))
    repo["get_live_session"].return_value = _session()
    repo["end_live_session"].return_value = ended

    result = await _handler().end_session(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, SESSION_ID
    )

    assert result == ended
    assert result.status == LiveSessionStatus.ENDED
    repo["end_live_session"].assert_awaited_once_with(SESSION_ID)
    check_permissions.assert_awaited_once_with(
        ORGANIZATION_ID, USER_ID, Resource.LIVE_SESSION, Action.DELETE, ORBIT_ID
    )


@pytest.mark.asyncio
async def test_start_in_an_orbit_without_a_relay_is_refused(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    repo["get_orbit_simple"].return_value = _orbit(relay_id=None)

    with pytest.raises(ApplicationError) as error:
        await _handler().start_session(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(label="run")
        )

    assert error.value.status_code == 409
    assert "assign a relay in orbit settings" in error.value.message
    repo["check_session_slot"].assert_not_awaited()
    repo["create_live_session"].assert_not_awaited()


@pytest.mark.asyncio
async def test_start_on_a_draining_relay_is_refused(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    repo["get_relay"].return_value = _relay(status=RelayStatus.DRAINING)

    with pytest.raises(ApplicationError) as error:
        await _handler().start_session(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(label="run")
        )

    assert error.value.status_code == 409
    assert error.value.message == ("Relay 'lab' is draining and takes no new sessions")
    repo["check_session_slot"].assert_not_awaited()
    repo["create_live_session"].assert_not_awaited()


@pytest.mark.parametrize(
    "capabilities",
    [
        {},
        {"sessions": {"version": 2, "api_versions": [2]}},
        {"sessions": {"version": 1, "api_versions": [2]}},
        {"custom.replay": {"version": 1}},
    ],
)
@pytest.mark.asyncio
async def test_start_on_a_relay_without_sessions_is_refused(
    check_permissions: AsyncMock,
    repo: dict[str, AsyncMock],
    capabilities: dict[str, dict[str, Any]],
) -> None:
    repo["get_relay"].return_value = _relay(capabilities=capabilities)

    with pytest.raises(ApplicationError) as error:
        await _handler().start_session(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(label="run")
        )

    assert error.value.status_code == 409
    assert error.value.message == "Relay 'lab' does not support sessions"
    repo["check_session_slot"].assert_not_awaited()
    repo["create_live_session"].assert_not_awaited()


@pytest.mark.asyncio
async def test_start_on_a_managed_relay_counts_toward_the_managed_limit(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    repo["get_relay"].return_value = _relay(organization_id=None)
    repo["create_live_session"].return_value = _session(last_heartbeat_ago=None)

    await _handler().start_session(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(label="run")
    )

    repo["check_session_slot"].assert_awaited_once_with(
        ORGANIZATION_ID, OrganizationResource.MANAGED_RELAY_SESSIONS, None
    )
    assert repo["create_live_session"].await_args is not None
    assert repo["create_live_session"].await_args.args[2] == (
        OrganizationResource.MANAGED_RELAY_SESSIONS
    )


@pytest.mark.asyncio
async def test_start_replacing_a_session_frees_its_slot_and_ends_it_on_create(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    repo["create_live_session"].return_value = _session(last_heartbeat_ago=None)

    await _handler().start_session(
        USER_ID,
        ORGANIZATION_ID,
        ORBIT_ID,
        LiveSessionStartIn(label="run"),
        replacing="oldsession01",
    )

    repo["check_session_slot"].assert_awaited_once_with(
        ORGANIZATION_ID, OrganizationResource.OWN_RELAY_SESSIONS, "oldsession01"
    )
    assert repo["create_live_session"].await_args is not None
    assert repo["create_live_session"].await_args.args[3] == "oldsession01"


@pytest.mark.asyncio
async def test_start_at_the_limit_is_refused_before_anything_is_created(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    repo["check_session_slot"].side_effect = OrganizationLimitReachedError(
        "Organization reached maximum number of sessions on its own relays"
    )

    with pytest.raises(OrganizationLimitReachedError):
        await _handler().start_session(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(label="run")
        )

    repo["create_live_session"].assert_not_awaited()


@pytest.mark.asyncio
async def test_a_session_keeps_its_relay_when_the_orbit_is_reassigned(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    repo["get_orbit_simple"].return_value = _orbit(relay_id=OTHER_RELAY_ID)
    repo["get_live_session"].return_value = _session()
    repo["record_heartbeat"].return_value = _session()
    handler = _handler()

    heartbeat = await handler.record_heartbeat(
        USER_ID,
        ORGANIZATION_ID,
        ORBIT_ID,
        SESSION_ID,
        LiveSessionHeartbeatIn(
            connected=True,
            token_expires_at=datetime.now(UTC) + timedelta(minutes=1),
        ),
    )
    view = await handler.issue_view_token(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, SESSION_ID
    )

    assert heartbeat.expose_token is not None
    assert [issued.session_id for issued in _issued(repo)] == [SESSION_ID] * 2
    assert view.launch_url.startswith("https://k3f9x2ab.sessions.example/")
    repo["get_relay"].assert_awaited_once_with(RELAY_ID)
    repo["get_orbit_simple"].assert_not_awaited()


@pytest.mark.asyncio
async def test_a_draining_relay_keeps_renewing_its_sessions(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    repo["get_relay"].return_value = _relay(status=RelayStatus.DRAINING)
    repo["get_live_session"].return_value = _session()
    repo["record_heartbeat"].return_value = _session()

    result = await _handler().record_heartbeat(
        USER_ID,
        ORGANIZATION_ID,
        ORBIT_ID,
        SESSION_ID,
        LiveSessionHeartbeatIn(
            connected=True,
            token_expires_at=datetime.now(UTC) + timedelta(minutes=1),
        ),
    )

    assert result.status == LiveSessionStatus.LIVE
    assert result.expose_token is not None


@pytest.mark.asyncio
async def test_a_session_whose_relay_was_removed_gets_no_credentials(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    ended = _session(ended_at=datetime.now(UTC), relay_id=None)
    repo["get_live_session"].return_value = ended
    repo["record_heartbeat"].return_value = ended
    handler = _handler()

    heartbeat = await handler.record_heartbeat(
        USER_ID,
        ORGANIZATION_ID,
        ORBIT_ID,
        SESSION_ID,
        LiveSessionHeartbeatIn(connected=True, token_expires_at=datetime.now(UTC)),
    )
    with pytest.raises(LiveSessionEndedError):
        await handler.issue_view_token(USER_ID, ORGANIZATION_ID, ORBIT_ID, SESSION_ID)

    assert heartbeat.status == LiveSessionStatus.ENDED
    assert heartbeat.expose_token is None
    repo["issue_token"].assert_not_awaited()
