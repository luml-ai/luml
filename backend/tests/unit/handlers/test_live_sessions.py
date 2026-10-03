from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from luml.handlers.live_sessions import LiveSessionHandler
from luml.infra.exceptions import (
    ApplicationError,
    InsufficientPermissionsError,
    LiveSessionEndedError,
    LiveSessionsNotConfiguredError,
    NotFoundError,
    OrganizationLimitReachedError,
)
from luml.repositories.limits import OrganizationResource
from luml.schemas.live_session import (
    LiveSession,
    LiveSessionHeartbeatIn,
    LiveSessionStartIn,
    LiveSessionStatus,
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
BASE_DOMAIN = "tunnel.example"
AGENT_URL = "wss://tunnel.example/connect"

REPO = "luml.handlers.live_sessions.LiveSessionRepository"
ORBIT_REPO = "luml.handlers.live_sessions.OrbitRepository"
RELAY_REPO = "luml.handlers.live_sessions.RelayRepository"
CHECK_PERMISSIONS = "luml.handlers.live_sessions.PermissionsHandler.check_permissions"


def _private_key_pem() -> str:
    private_key = ec.generate_private_key(ec.SECP256R1())
    return private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


SIGNING_KEY = _private_key_pem()
ENABLED_SETTINGS: dict[str, Any] = {
    "LIVE_SESSION_SIGNING_KEY": SIGNING_KEY,
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
) -> Relay:
    return Relay(
        id=relay_id,
        organization_id=organization_id,
        label="lab",
        base_domain=base_domain,
        agent_url=agent_url,
        status=status,
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
) -> LiveSession:
    now = datetime.now(UTC)
    return LiveSession(
        id=SESSION_ID,
        orbit_id=ORBIT_ID,
        user_id=user_id,
        name="training run",
        relay_id=relay_id,
        started_at=now - timedelta(hours=2),
        last_heartbeat_at=now - last_heartbeat_ago if last_heartbeat_ago else None,
        connected=connected,
        ended_at=ended_at,
    )


def _decode(handler: LiveSessionHandler, token: str) -> dict[str, Any]:
    """Check a token against the published keys the way the relay does."""
    key_id = jwt.get_unverified_header(token)["kid"]
    keys = {key["kid"]: key for key in handler.public_keys()["keys"]}
    claims: dict[str, Any] = jwt.decode(
        token,
        jwt.PyJWK(keys[key_id], algorithm="ES256").key,
        algorithms=["ES256"],
        issuer="luml",
        audience=str(RELAY_ID),
        options={
            "require": ["iss", "aud", "sub", "exp", "jti", "sid", "kind"],
            "strict_aud": True,
        },
    )
    return claims


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
    }
    patches = {
        name: patch(target, new_callable=AsyncMock) for name, target in targets.items()
    }
    mocks = {name: p.start() for name, p in patches.items()}
    mocks["get_orbit_simple"].return_value = _orbit()
    mocks["get_relay"].return_value = _relay()
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
        USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(name="training run")
    )

    check_permissions.assert_awaited_once_with(
        ORGANIZATION_ID, USER_ID, Resource.LIVE_SESSION, Action.CREATE, ORBIT_ID
    )
    repo["get_orbit_simple"].assert_awaited_once_with(ORBIT_ID, ORGANIZATION_ID)
    repo["get_relay"].assert_awaited_once_with(RELAY_ID)
    repo["check_session_slot"].assert_awaited_once_with(
        ORGANIZATION_ID, OrganizationResource.OWN_RELAY_SESSIONS
    )
    assert repo["create_live_session"].await_args is not None
    created, organization_id, limit = repo["create_live_session"].await_args.args
    assert (created.orbit_id, created.user_id, created.name, created.relay_id) == (
        ORBIT_ID,
        USER_ID,
        "training run",
        RELAY_ID,
    )
    assert (organization_id, limit) == (
        ORGANIZATION_ID,
        OrganizationResource.OWN_RELAY_SESSIONS,
    )
    assert result.id == SESSION_ID
    assert result.public_url == "https://k3f9x2ab.tunnel.example"
    assert result.app_url == (
        f"https://app.luml.ai/organization/{ORGANIZATION_ID}"
        f"/orbit/{ORBIT_ID}/flow/{SESSION_ID}"
    )
    assert result.agent_url == AGENT_URL
    assert result.heartbeat_interval == 30
    claims = _decode(handler, result.expose_token)
    assert claims["kind"] == "expose"
    assert claims["sid"] == SESSION_ID
    assert claims["sub"] == str(USER_ID)
    assert claims["exp"] - claims["iat"] == 600
    assert datetime.fromtimestamp(claims["exp"], UTC) == result.token_expires_at


@pytest.mark.asyncio
async def test_public_url_keeps_the_scheme_and_port_of_the_agent_address(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    repo["create_live_session"].return_value = _session(last_heartbeat_ago=None)
    repo["get_relay"].return_value = _relay(
        base_domain="tunnel.localhost", agent_url="ws://tunnel.localhost:8090/connect"
    )
    handler = _handler()

    result = await handler.start_session(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(name="dev")
    )

    assert result.public_url == "http://k3f9x2ab.tunnel.localhost:8090"


@pytest.mark.asyncio
async def test_signing_key_with_escaped_newlines_is_accepted(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    repo["create_live_session"].return_value = _session(last_heartbeat_ago=None)
    handler = _handler(LIVE_SESSION_SIGNING_KEY=SIGNING_KEY.replace("\n", "\\n"))

    result = await handler.start_session(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(name="run")
    )

    assert _decode(handler, result.expose_token)["sid"] == SESSION_ID


def test_signing_key_on_another_curve_is_refused() -> None:
    other_curve_key = (
        ec.generate_private_key(ec.SECP384R1())
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        .decode()
    )

    with pytest.raises(ValueError, match="P-256"):
        _handler(LIVE_SESSION_SIGNING_KEY=other_curve_key)


@pytest.mark.parametrize("unset_value", [None, ""], ids=["none", "empty"])
@pytest.mark.parametrize(
    "operation",
    ["start", "list", "get", "heartbeat", "view_token", "end"],
)
@pytest.mark.asyncio
async def test_every_operation_fails_the_same_way_when_the_feature_is_off(
    check_permissions: AsyncMock,
    repo: dict[str, AsyncMock],
    unset_value: str | None,
    operation: str,
) -> None:
    handler = _handler(LIVE_SESSION_SIGNING_KEY=unset_value)
    calls: dict[str, Callable[[], Awaitable[object]]] = {
        "start": lambda: handler.start_session(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(name="run")
        ),
        "list": lambda: handler.list_sessions(USER_ID, ORGANIZATION_ID, ORBIT_ID),
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

    with pytest.raises(LiveSessionsNotConfiguredError) as error:
        await calls[operation]()

    assert error.value.status_code == 501
    assert error.value.message == "Live sessions are not set up in this deployment"
    for mock in repo.values():
        mock.assert_not_awaited()


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
            LiveSessionStartIn(name="run"),
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
    assert result.expose_token is not None
    claims = _decode(handler, result.expose_token)
    assert (claims["kind"], claims["sid"]) == ("expose", SESSION_ID)
    assert datetime.fromtimestamp(claims["exp"], UTC) == result.token_expires_at


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


@pytest.mark.parametrize(
    "stored",
    [
        _session(ended_at=datetime.now(UTC) - timedelta(minutes=1)),
        _session(last_heartbeat_ago=timedelta(hours=1, minutes=1)),
    ],
    ids=["ended", "silent-for-an-hour"],
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


@pytest.mark.asyncio
async def test_view_token_is_refused_for_an_ended_session(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    repo["get_live_session"].return_value = _session(ended_at=datetime.now(UTC))

    with pytest.raises(LiveSessionEndedError):
        await _handler().issue_view_token(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, SESSION_ID
        )


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
    claims = _decode(handler, result.token)
    repo["get_relay"].assert_awaited_once_with(RELAY_ID)
    assert claims["kind"] == "view"
    assert claims["sid"] == SESSION_ID
    assert claims["aud"] == str(RELAY_ID)
    assert claims["sub"] == str(USER_ID)
    assert claims["exp"] - claims["iat"] == 300
    launch = urlsplit(result.launch_url)
    assert f"{launch.scheme}://{launch.netloc}{launch.path}" == (
        "https://k3f9x2ab.tunnel.example/.luml-tunnel/launch"
    )
    assert parse_qs(launch.query) == {"token": [result.token]}


@pytest.mark.asyncio
async def test_list_contains_only_the_callers_sessions(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    own = _session()
    repo["list_live_sessions"].return_value = [own, _session(user_id=OTHER_USER_ID)]

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


def test_public_keys_carry_an_identifier() -> None:
    keys = _handler().public_keys()["keys"]

    assert len(keys) == 1
    assert keys[0]["kid"]
    assert keys[0]["kty"] == "EC"
    assert keys[0]["crv"] == "P-256"
    assert "d" not in keys[0]


def test_no_public_keys_without_a_signing_key() -> None:
    assert _handler(LIVE_SESSION_SIGNING_KEY=None).public_keys() == {"keys": []}


@pytest.mark.asyncio
async def test_start_in_an_orbit_without_a_relay_is_refused(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    repo["get_orbit_simple"].return_value = _orbit(relay_id=None)

    with pytest.raises(ApplicationError) as error:
        await _handler().start_session(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(name="run")
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
            USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(name="run")
        )

    assert error.value.status_code == 409
    assert error.value.message == ("Relay 'lab' is draining and takes no new sessions")
    repo["check_session_slot"].assert_not_awaited()
    repo["create_live_session"].assert_not_awaited()


@pytest.mark.asyncio
async def test_start_on_a_managed_relay_counts_toward_the_managed_limit(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    repo["get_relay"].return_value = _relay(organization_id=None)
    repo["create_live_session"].return_value = _session(last_heartbeat_ago=None)

    await _handler().start_session(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(name="run")
    )

    repo["check_session_slot"].assert_awaited_once_with(
        ORGANIZATION_ID, OrganizationResource.MANAGED_RELAY_SESSIONS
    )
    assert repo["create_live_session"].await_args is not None
    assert repo["create_live_session"].await_args.args[2] == (
        OrganizationResource.MANAGED_RELAY_SESSIONS
    )


@pytest.mark.asyncio
async def test_start_at_the_limit_is_refused_before_anything_is_created(
    check_permissions: AsyncMock, repo: dict[str, AsyncMock]
) -> None:
    repo["check_session_slot"].side_effect = OrganizationLimitReachedError(
        "Organization reached maximum number of sessions on its own relays"
    )

    with pytest.raises(OrganizationLimitReachedError):
        await _handler().start_session(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(name="run")
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
    assert _decode(handler, heartbeat.expose_token)["aud"] == str(RELAY_ID)
    assert _decode(handler, view.token)["aud"] == str(RELAY_ID)
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
