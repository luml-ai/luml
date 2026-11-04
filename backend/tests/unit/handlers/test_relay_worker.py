import logging
from datetime import UTC, datetime, timedelta
from typing import Any

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

from tests.support.ids import (
    LIVE_SESSION_ID,
    ORBIT_ID,
    OTHER_RELAY_ID,
    RELAY_ID,
    TOKEN_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks, mock_collaborators

TOKEN = "opaque-token"

MODULE = "luml.handlers.relay_worker"


@pytest.fixture
def mocks() -> CollaboratorMocks[RelayWorkerHandler]:
    return mock_collaborators(
        RelayWorkerHandler(
            config.model_copy(
                update={
                    "CORS_ORIGINS": "https://app.luml.ai, https://dev.luml.ai",
                    "APP_EMAIL_URL": "https://app.luml.ai/",
                }
            )
        )
    )


def _session(**overrides: Any) -> LiveSession:  # noqa: ANN401
    now = datetime.now(UTC)
    fields: dict[str, Any] = {
        "id": LIVE_SESSION_ID,
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
        "session_id": LIVE_SESSION_ID,
        "user_id": USER_ID,
        "expires_at": datetime.now(UTC) + timedelta(minutes=5),
        "destination": "/experiments/42?tab=metrics",
    }
    return LiveSessionToken(**{**fields, **overrides})


def _grant(**overrides: Any) -> LiveSessionToken:  # noqa: ANN401
    launched_at = datetime.now(UTC) - timedelta(minutes=10)
    fields: dict[str, Any] = {
        "launched_at": launched_at,
        "expires_at": launched_at + timedelta(hours=12),
    }
    return _token(**{**fields, **overrides})


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


class TestRelayWorkerHandler:
    @pytest.mark.parametrize("status", [RelayStatus.ENABLED, RelayStatus.DRAINING])
    async def test_describe_answers_the_relay_and_the_app(
        self, mocks: CollaboratorMocks[RelayWorkerHandler], status: RelayStatus
    ) -> None:
        mocks.relay_repo.get_relay.return_value = Relay(
            id=RELAY_ID,
            organization_id=None,
            label="lab",
            base_domain="sessions.example",
            agent_url="wss://sessions.example/connect",
            status=status,
            created_at=datetime.now(UTC),
        )

        description = await mocks.handler.describe(RELAY_ID)

        mocks.relay_repo.get_relay.assert_awaited_once_with(RELAY_ID)
        assert description.model_dump() == {
            "id": RELAY_ID,
            "label": "lab",
            "base_domain": "sessions.example",
            "agent_url": "wss://sessions.example/connect",
            "status": status,
            "app_origins": ["https://app.luml.ai", "https://dev.luml.ai"],
            "app_url": "https://app.luml.ai",
        }

    async def test_describe_a_removed_relay_is_not_found(
        self, mocks: CollaboratorMocks[RelayWorkerHandler]
    ) -> None:
        mocks.relay_repo.get_relay.return_value = None

        with pytest.raises(NotFoundError):
            await mocks.handler.describe(RELAY_ID)

    async def test_a_view_token_in_the_header_answers_its_claims_and_is_not_consumed(
        self, mocks: CollaboratorMocks[RelayWorkerHandler]
    ) -> None:
        token = _token()
        mocks.token_repo.get_token_with_session.return_value = (token, _session())

        verdict = await mocks.handler.validate_token(
            RELAY_ID, SessionTokenValidateIn(token=TOKEN)
        )

        mocks.token_repo.get_token_with_session.assert_awaited_once_with(TOKEN)
        assert verdict == SessionTokenVerdict(
            active=True,
            kind=SessionTokenKind.VIEW,
            session_id=LIVE_SESSION_ID,
            user_id=USER_ID,
            expires_at=token.expires_at,
        )
        mocks.token_repo.launch_view_token.assert_not_awaited()
        mocks.session_repo.record_viewer_activity.assert_awaited_once_with(
            LIVE_SESSION_ID
        )

    async def test_an_expose_token_answers_its_claims_without_viewer_activity(
        self, mocks: CollaboratorMocks[RelayWorkerHandler]
    ) -> None:
        token = _token(SessionTokenKind.EXPOSE, destination=None)
        mocks.token_repo.get_token_with_session.return_value = (token, _session())

        verdict = await mocks.handler.validate_token(
            RELAY_ID, SessionTokenValidateIn(token=TOKEN)
        )

        assert (verdict.active, verdict.kind) == (True, SessionTokenKind.EXPOSE)
        mocks.session_repo.record_viewer_activity.assert_not_awaited()

    async def test_a_draining_relays_session_is_still_validated(
        self, mocks: CollaboratorMocks[RelayWorkerHandler]
    ) -> None:
        mocks.token_repo.get_token_with_session.return_value = (_token(), _session())

        verdict = await mocks.handler.validate_token(
            RELAY_ID, SessionTokenValidateIn(token=TOKEN)
        )

        assert verdict.active
        mocks.relay_repo.get_relay.assert_not_awaited()

    @pytest.mark.parametrize("launch", [False, True], ids=["header", "launch"])
    @pytest.mark.parametrize(
        "found", INACTIVE_TOKENS.values(), ids=list(INACTIVE_TOKENS.keys())
    )
    async def test_an_inactive_token_answers_inactive_without_a_reason(
        self,
        mocks: CollaboratorMocks[RelayWorkerHandler],
        caplog: pytest.LogCaptureFixture,
        found: tuple[LiveSessionToken, LiveSession] | None,
        launch: bool,
    ) -> None:
        mocks.token_repo.get_token_with_session.return_value = found

        with caplog.at_level(logging.INFO, logger=MODULE):
            verdict = await mocks.handler.validate_token(
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
        mocks.token_repo.launch_view_token.assert_not_awaited()
        mocks.session_repo.record_viewer_activity.assert_not_awaited()

    async def test_a_launch_consumes_the_view_token_and_answers_the_grant(
        self, mocks: CollaboratorMocks[RelayWorkerHandler]
    ) -> None:
        grant_expires_at = datetime.now(UTC) + timedelta(hours=12)
        mocks.token_repo.get_token_with_session.return_value = (_token(), _session())
        mocks.token_repo.launch_view_token.return_value = _token(
            launched_at=datetime.now(UTC), expires_at=grant_expires_at
        )

        verdict = await mocks.handler.validate_token(
            RELAY_ID, SessionTokenValidateIn(token=TOKEN, launch=True)
        )

        assert mocks.token_repo.launch_view_token.await_args is not None
        token_id, requested_expiry = mocks.token_repo.launch_view_token.await_args.args
        assert token_id == TOKEN_ID
        assert (
            timedelta(hours=12) - timedelta(seconds=5)
            < requested_expiry - datetime.now(UTC)
            <= timedelta(hours=12)
        )
        assert verdict == SessionTokenVerdict(
            active=True,
            kind=SessionTokenKind.VIEW,
            session_id=LIVE_SESSION_ID,
            user_id=USER_ID,
            expires_at=grant_expires_at,
            grant_id=TOKEN_ID,
            destination="/experiments/42?tab=metrics",
        )
        mocks.session_repo.record_viewer_activity.assert_awaited_once_with(
            LIVE_SESSION_ID
        )

    async def test_a_launch_lost_to_a_concurrent_launch_is_inactive(
        self, mocks: CollaboratorMocks[RelayWorkerHandler]
    ) -> None:
        mocks.token_repo.get_token_with_session.return_value = (_token(), _session())
        mocks.token_repo.launch_view_token.return_value = None

        verdict = await mocks.handler.validate_token(
            RELAY_ID, SessionTokenValidateIn(token=TOKEN, launch=True)
        )

        assert verdict == SessionTokenVerdict(active=False)
        mocks.session_repo.record_viewer_activity.assert_not_awaited()

    async def test_an_expose_token_never_launches(
        self, mocks: CollaboratorMocks[RelayWorkerHandler]
    ) -> None:
        mocks.token_repo.get_token_with_session.return_value = (
            _token(SessionTokenKind.EXPOSE),
            _session(),
        )

        verdict = await mocks.handler.validate_token(
            RELAY_ID, SessionTokenValidateIn(token=TOKEN, launch=True)
        )

        assert verdict == SessionTokenVerdict(active=False)
        mocks.token_repo.launch_view_token.assert_not_awaited()

    async def test_a_grant_outlives_the_view_tokens_lifetime(
        self, mocks: CollaboratorMocks[RelayWorkerHandler]
    ) -> None:
        grant = _grant()
        mocks.token_repo.get_grant_with_session.return_value = (grant, _session())

        verdict = await mocks.handler.check_grant(RELAY_ID, TOKEN_ID)

        mocks.token_repo.get_grant_with_session.assert_awaited_once_with(TOKEN_ID)
        assert verdict == ViewerGrantVerdict(
            active=True,
            session_id=LIVE_SESSION_ID,
            user_id=USER_ID,
            expires_at=grant.expires_at,
        )
        mocks.session_repo.record_viewer_activity.assert_awaited_once_with(
            LIVE_SESSION_ID
        )

    @pytest.mark.parametrize(
        "found", INACTIVE_GRANTS.values(), ids=list(INACTIVE_GRANTS.keys())
    )
    async def test_an_inactive_grant_answers_inactive_without_a_reason(
        self,
        mocks: CollaboratorMocks[RelayWorkerHandler],
        caplog: pytest.LogCaptureFixture,
        found: tuple[LiveSessionToken, LiveSession] | None,
    ) -> None:
        mocks.token_repo.get_grant_with_session.return_value = found

        with caplog.at_level(logging.INFO, logger=MODULE):
            verdict = await mocks.handler.check_grant(RELAY_ID, TOKEN_ID)

        assert verdict.model_dump() == {
            "active": False,
            "session_id": None,
            "user_id": None,
            "expires_at": None,
        }
        assert f"Relay {RELAY_ID}: grant is inactive" in caplog.text
        mocks.session_repo.record_viewer_activity.assert_not_awaited()

    async def test_report_records_the_connected_agents_and_capabilities(
        self, mocks: CollaboratorMocks[RelayWorkerHandler]
    ) -> None:
        capabilities = {"sessions": {"version": 1, "api_versions": [1]}}

        await mocks.handler.report(
            RELAY_ID, RelayReportIn(connected_agents=3, capabilities=capabilities)
        )

        mocks.relay_repo.record_report.assert_awaited_once_with(
            RELAY_ID, 3, capabilities
        )
