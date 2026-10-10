import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from luml.handlers.relay_worker import RelayWorkerHandler
from luml.infra.exceptions import NotFoundError
from luml.schemas.live_session import (
    LiveSession,
    LiveSessionToken,
    LiveSessionVisibility,
    SessionTokenKind,
)
from luml.schemas.relay import (
    Relay,
    RelayReportIn,
    RelayStatus,
    SessionTokenValidateIn,
    SessionTokenVerdict,
    ViewerGrantVerdict,
)
from luml.settings import config

RELAY_ID = UUID("0199c337-09f4-7a3b-8c1d-2e3f4a5b6c7d")
OTHER_RELAY_ID = UUID("0199c337-09f4-7a3b-8c1d-2e3f4a5b6c7e")
USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ORBIT_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")
TOKEN_ID = UUID("0199c337-09f6-7a3b-8c1d-2e3f4a5b6c7d")
SESSION_ID = "k3f9x2ab"
TOKEN = "opaque-token"

MODULE = "luml.handlers.relay_worker"


def _handler() -> RelayWorkerHandler:
    return RelayWorkerHandler(
        config.model_copy(
            update={
                "CORS_ORIGINS": "https://app.luml.ai, https://dev.luml.ai",
                "APP_EMAIL_URL": "https://app.luml.ai/",
            }
        )
    )


def _session(**overrides: Any) -> LiveSession:  # noqa: ANN401
    now = datetime.now(UTC)
    fields: dict[str, Any] = {
        "id": SESSION_ID,
        "orbit_id": ORBIT_ID,
        "user_id": USER_ID,
        "label": "run",
        "visibility": LiveSessionVisibility.OWNER,
        "relay_id": RELAY_ID,
        "started_at": now - timedelta(minutes=10),
        "last_heartbeat_at": now - timedelta(seconds=5),
        "connected": True,
    }
    return LiveSession(**{**fields, **overrides})


def _token(
    kind: SessionTokenKind = SessionTokenKind.VIEW,
    **overrides: Any,  # noqa: ANN401
) -> LiveSessionToken:
    fields: dict[str, Any] = {
        "id": TOKEN_ID,
        "kind": kind,
        "session_id": SESSION_ID,
        "user_id": USER_ID,
        "expires_at": datetime.now(UTC) + timedelta(minutes=5),
        "destination": "/experiments/42?tab=metrics",
    }
    return LiveSessionToken(**{**fields, **overrides})


@pytest.fixture
def repo() -> Iterator[dict[str, AsyncMock]]:
    targets = {
        "get_relay": f"{MODULE}.RelayRepository.get_relay",
        "record_report": f"{MODULE}.RelayRepository.record_report",
        "record_viewer_activity": (
            f"{MODULE}.LiveSessionRepository.record_viewer_activity"
        ),
        "get_token_with_session": (
            f"{MODULE}.LiveSessionTokenRepository.get_token_with_session"
        ),
        "get_grant_with_session": (
            f"{MODULE}.LiveSessionTokenRepository.get_grant_with_session"
        ),
        "launch_view_token": f"{MODULE}.LiveSessionTokenRepository.launch_view_token",
    }
    patches = {
        name: patch(target, new_callable=AsyncMock) for name, target in targets.items()
    }
    mocks = {name: p.start() for name, p in patches.items()}
    yield mocks
    for p in patches.values():
        p.stop()


@pytest.mark.parametrize("status", [RelayStatus.ENABLED, RelayStatus.DRAINING])
@pytest.mark.asyncio
async def test_describe_answers_the_relay_and_the_app(
    repo: dict[str, AsyncMock], status: RelayStatus
) -> None:
    repo["get_relay"].return_value = Relay(
        id=RELAY_ID,
        organization_id=None,
        label="lab",
        base_domain="sessions.example",
        agent_url="wss://sessions.example/connect",
        status=status,
        created_at=datetime.now(UTC),
    )

    description = await _handler().describe(RELAY_ID)

    repo["get_relay"].assert_awaited_once_with(RELAY_ID)
    assert description.model_dump() == {
        "id": RELAY_ID,
        "label": "lab",
        "base_domain": "sessions.example",
        "agent_url": "wss://sessions.example/connect",
        "status": status,
        "app_origins": ["https://app.luml.ai", "https://dev.luml.ai"],
        "app_url": "https://app.luml.ai",
    }


@pytest.mark.asyncio
async def test_describe_a_removed_relay_is_not_found(
    repo: dict[str, AsyncMock],
) -> None:
    repo["get_relay"].return_value = None

    with pytest.raises(NotFoundError):
        await _handler().describe(RELAY_ID)


@pytest.mark.asyncio
async def test_a_view_token_in_the_header_answers_its_claims_and_is_not_consumed(
    repo: dict[str, AsyncMock],
) -> None:
    token = _token()
    repo["get_token_with_session"].return_value = (token, _session())

    verdict = await _handler().validate_token(
        RELAY_ID, SessionTokenValidateIn(token=TOKEN)
    )

    repo["get_token_with_session"].assert_awaited_once_with(TOKEN)
    assert verdict == SessionTokenVerdict(
        active=True,
        kind=SessionTokenKind.VIEW,
        session_id=SESSION_ID,
        user_id=USER_ID,
        expires_at=token.expires_at,
    )
    repo["launch_view_token"].assert_not_awaited()
    repo["record_viewer_activity"].assert_awaited_once_with(SESSION_ID)


@pytest.mark.asyncio
async def test_an_expose_token_answers_its_claims_without_viewer_activity(
    repo: dict[str, AsyncMock],
) -> None:
    token = _token(SessionTokenKind.EXPOSE, destination=None)
    repo["get_token_with_session"].return_value = (token, _session())

    verdict = await _handler().validate_token(
        RELAY_ID, SessionTokenValidateIn(token=TOKEN)
    )

    assert (verdict.active, verdict.kind) == (True, SessionTokenKind.EXPOSE)
    repo["record_viewer_activity"].assert_not_awaited()


@pytest.mark.asyncio
async def test_a_draining_relays_session_is_still_validated(
    repo: dict[str, AsyncMock],
) -> None:
    repo["get_token_with_session"].return_value = (_token(), _session())

    verdict = await _handler().validate_token(
        RELAY_ID, SessionTokenValidateIn(token=TOKEN)
    )

    assert verdict.active
    repo["get_relay"].assert_not_awaited()


INACTIVE_TOKENS: dict[str, tuple[LiveSessionToken, LiveSession] | None] = {
    "unknown": None,
    "expired": (
        _token(expires_at=datetime.now(UTC) - timedelta(seconds=1)),
        _session(),
    ),
    "another-relay": (_token(), _session(relay_id=OTHER_RELAY_ID)),
    "relay-removed": (_token(), _session(relay_id=None)),
    "ended": (_token(), _session(ended_at=datetime.now(UTC))),
    "silent-for-an-hour": (
        _token(),
        _session(last_heartbeat_at=datetime.now(UTC) - timedelta(hours=1, seconds=1)),
    ),
    "no-viewer-for-the-idle-period": (
        _token(),
        _session(started_at=datetime.now(UTC) - timedelta(days=8)),
    ),
    "launched": (
        _token(
            launched_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=12),
        ),
        _session(),
    ),
}


@pytest.mark.parametrize("launch", [False, True], ids=["header", "launch"])
@pytest.mark.parametrize(
    "found", INACTIVE_TOKENS.values(), ids=list(INACTIVE_TOKENS.keys())
)
@pytest.mark.asyncio
async def test_an_inactive_token_answers_inactive_without_a_reason(
    repo: dict[str, AsyncMock],
    caplog: pytest.LogCaptureFixture,
    found: tuple[LiveSessionToken, LiveSession] | None,
    launch: bool,
) -> None:
    repo["get_token_with_session"].return_value = found

    with caplog.at_level(logging.INFO, logger=MODULE):
        verdict = await _handler().validate_token(
            RELAY_ID, SessionTokenValidateIn(token=TOKEN, launch=launch)
        )

    assert verdict.model_dump() == {
        "active": False,
        "kind": None,
        "session_id": None,
        "user_id": None,
        "expires_at": None,
        "grant_id": None,
        "destination": None,
    }
    assert f"Relay {RELAY_ID}: token is inactive" in caplog.text
    repo["launch_view_token"].assert_not_awaited()
    repo["record_viewer_activity"].assert_not_awaited()


@pytest.mark.asyncio
async def test_a_launch_consumes_the_view_token_and_answers_the_grant(
    repo: dict[str, AsyncMock],
) -> None:
    grant_expires_at = datetime.now(UTC) + timedelta(hours=12)
    repo["get_token_with_session"].return_value = (_token(), _session())
    repo["launch_view_token"].return_value = _token(
        launched_at=datetime.now(UTC), expires_at=grant_expires_at
    )

    verdict = await _handler().validate_token(
        RELAY_ID, SessionTokenValidateIn(token=TOKEN, launch=True)
    )

    assert repo["launch_view_token"].await_args is not None
    token_id, requested_expiry = repo["launch_view_token"].await_args.args
    assert token_id == TOKEN_ID
    assert (
        timedelta(hours=12) - timedelta(seconds=5)
        < requested_expiry - datetime.now(UTC)
        <= timedelta(hours=12)
    )
    assert verdict == SessionTokenVerdict(
        active=True,
        kind=SessionTokenKind.VIEW,
        session_id=SESSION_ID,
        user_id=USER_ID,
        expires_at=grant_expires_at,
        grant_id=TOKEN_ID,
        destination="/experiments/42?tab=metrics",
    )
    repo["record_viewer_activity"].assert_awaited_once_with(SESSION_ID)


@pytest.mark.asyncio
async def test_a_launch_lost_to_a_concurrent_launch_is_inactive(
    repo: dict[str, AsyncMock],
) -> None:
    repo["get_token_with_session"].return_value = (_token(), _session())
    repo["launch_view_token"].return_value = None

    verdict = await _handler().validate_token(
        RELAY_ID, SessionTokenValidateIn(token=TOKEN, launch=True)
    )

    assert verdict == SessionTokenVerdict(active=False)
    repo["record_viewer_activity"].assert_not_awaited()


@pytest.mark.asyncio
async def test_an_expose_token_never_launches(repo: dict[str, AsyncMock]) -> None:
    repo["get_token_with_session"].return_value = (
        _token(SessionTokenKind.EXPOSE),
        _session(),
    )

    verdict = await _handler().validate_token(
        RELAY_ID, SessionTokenValidateIn(token=TOKEN, launch=True)
    )

    assert verdict == SessionTokenVerdict(active=False)
    repo["launch_view_token"].assert_not_awaited()


def _grant(**overrides: Any) -> LiveSessionToken:  # noqa: ANN401
    # Launched ten minutes ago, so the view token's own five minutes are over.
    launched_at = datetime.now(UTC) - timedelta(minutes=10)
    fields: dict[str, Any] = {
        "launched_at": launched_at,
        "expires_at": launched_at + timedelta(hours=12),
    }
    return _token(**{**fields, **overrides})


@pytest.mark.asyncio
async def test_a_grant_outlives_the_view_tokens_lifetime(
    repo: dict[str, AsyncMock],
) -> None:
    grant = _grant()
    repo["get_grant_with_session"].return_value = (grant, _session())

    verdict = await _handler().check_grant(RELAY_ID, TOKEN_ID)

    repo["get_grant_with_session"].assert_awaited_once_with(TOKEN_ID)
    assert verdict == ViewerGrantVerdict(
        active=True,
        session_id=SESSION_ID,
        user_id=USER_ID,
        expires_at=grant.expires_at,
    )
    repo["record_viewer_activity"].assert_awaited_once_with(SESSION_ID)


INACTIVE_GRANTS: dict[str, tuple[LiveSessionToken, LiveSession] | None] = {
    "unknown": None,
    "not-launched": (_token(), _session()),
    "expired": (
        _grant(expires_at=datetime.now(UTC) - timedelta(seconds=1)),
        _session(),
    ),
    "another-relay": (_grant(), _session(relay_id=OTHER_RELAY_ID)),
    "ended": (_grant(), _session(ended_at=datetime.now(UTC))),
    "no-viewer-for-the-idle-period": (
        _grant(),
        _session(
            started_at=datetime.now(UTC) - timedelta(days=20),
            last_viewer_activity_at=datetime.now(UTC) - timedelta(days=8),
        ),
    ),
}


@pytest.mark.parametrize(
    "found", INACTIVE_GRANTS.values(), ids=list(INACTIVE_GRANTS.keys())
)
@pytest.mark.asyncio
async def test_an_inactive_grant_answers_inactive_without_a_reason(
    repo: dict[str, AsyncMock],
    caplog: pytest.LogCaptureFixture,
    found: tuple[LiveSessionToken, LiveSession] | None,
) -> None:
    repo["get_grant_with_session"].return_value = found

    with caplog.at_level(logging.INFO, logger=MODULE):
        verdict = await _handler().check_grant(RELAY_ID, TOKEN_ID)

    assert verdict.model_dump() == {
        "active": False,
        "session_id": None,
        "user_id": None,
        "expires_at": None,
    }
    assert f"Relay {RELAY_ID}: grant is inactive" in caplog.text
    repo["record_viewer_activity"].assert_not_awaited()


@pytest.mark.asyncio
async def test_report_records_the_connected_agents_and_capabilities(
    repo: dict[str, AsyncMock],
) -> None:
    capabilities = {"sessions": {"version": 1, "api_versions": [1]}}

    await _handler().report(
        RELAY_ID, RelayReportIn(connected_agents=3, capabilities=capabilities)
    )

    repo["record_report"].assert_awaited_once_with(RELAY_ID, 3, capabilities)
