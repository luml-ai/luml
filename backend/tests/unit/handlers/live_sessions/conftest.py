from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from luml.handlers.live_sessions import LiveSessionHandler
from luml.schemas.live_session import (
    LiveSession,
    LiveSessionTokenCreate,
    LiveSessionVisibility,
)
from luml.schemas.orbit import Orbit
from luml.schemas.relay import Relay, RelayStatus
from luml.settings import Settings, config

from tests.support.ids import (
    LIVE_SESSION_ID,
    ORBIT_ID,
    ORGANIZATION_ID,
    RELAY_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks, mock_collaborators

BUCKET_SECRET_ID = UUID("0199c337-09f5-7a3b-8c1d-2e3f4a5b6c7d")
BASE_DOMAIN = "sessions.example"
AGENT_URL = "wss://sessions.example/connect"
SESSIONS: dict[str, dict[str, Any]] = {"sessions": {"version": 1, "api_versions": [1]}}

ENABLED_SETTINGS: dict[str, Any] = {
    "LIVE_SESSION_EXPOSE_TOKEN_LIFETIME_SECONDS": 600,
    "LIVE_SESSION_VIEW_TOKEN_LIFETIME_SECONDS": 300,
    "APP_EMAIL_URL": "https://app.luml.ai/",
}


def _settings(**overrides: Any) -> Settings:  # noqa: ANN401
    return config.model_copy(update={**ENABLED_SETTINGS, **overrides})


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
        bucket_secret_id=BUCKET_SECRET_ID,
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
        id=LIVE_SESSION_ID,
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


def _issued(
    mocks: CollaboratorMocks[LiveSessionHandler],
) -> list[LiveSessionTokenCreate]:
    return [call.args[0] for call in mocks.token_repo.issue_token.await_args_list]


def _assert_lifetime(issued: LiveSessionTokenCreate, seconds: int) -> None:
    remaining = issued.expires_at - datetime.now(UTC)
    assert timedelta(seconds=seconds - 5) < remaining <= timedelta(seconds=seconds)


@pytest.fixture
def mocks() -> CollaboratorMocks[LiveSessionHandler]:
    mocks = mock_collaborators(LiveSessionHandler(_settings()))
    mocks.orbit_repo.get_orbit_simple.return_value = _orbit()
    mocks.relay_repo.get_relay.return_value = _relay()
    mocks.token_repo.issue_token.side_effect = [f"opaque-{n}" for n in range(5)]
    return mocks
