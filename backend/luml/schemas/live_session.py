from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field, computed_field, field_validator

from luml.schemas.base import BaseOrmConfig
from luml.settings import config

LIVE_SESSION_DISCONNECTED_AFTER = timedelta(seconds=90)
LIVE_SESSION_ENDED_AFTER = timedelta(hours=1)
LIVE_SESSION_LIST_RETENTION = timedelta(hours=24)
LIVE_SESSION_HEARTBEAT_INTERVAL_SECONDS = 30
LIVE_SESSION_GRANT_LIFETIME = timedelta(hours=12)


class LiveSessionStatus(StrEnum):
    LIVE = "live"
    DISCONNECTED = "disconnected"
    ENDED = "ended"


class LiveSessionVisibility(StrEnum):
    OWNER = "owner"


def viewer_idle_period() -> timedelta:
    return timedelta(seconds=config.LIVE_SESSION_VIEWER_IDLE_SECONDS)


class SessionTokenKind(StrEnum):
    EXPOSE = "expose"
    VIEW = "view"


class LiveSession(BaseModel, BaseOrmConfig):
    id: str
    orbit_id: UUID
    user_id: UUID
    label: str | None = None
    visibility: LiveSessionVisibility
    relay_id: UUID | None = None
    started_at: datetime
    last_heartbeat_at: datetime | None = None
    connected: bool
    ended_at: datetime | None = None
    last_viewer_activity_at: datetime | None = None

    @property
    def implied_end(self) -> datetime:
        """When the session ends unless it is ended explicitly.

        Mirrored in SQL by `live_session_implied_end`; both silences are
        counted from the start when nothing has happened yet.
        """
        return min(
            (self.last_heartbeat_at or self.started_at) + LIVE_SESSION_ENDED_AFTER,
            (self.last_viewer_activity_at or self.started_at) + viewer_idle_period(),
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> LiveSessionStatus:
        now = datetime.now(UTC)
        if self.ended_at is not None or now > self.implied_end:
            return LiveSessionStatus.ENDED
        silent_for = now - (self.last_heartbeat_at or self.started_at)
        if silent_for > LIVE_SESSION_DISCONNECTED_AFTER or not self.connected:
            return LiveSessionStatus.DISCONNECTED
        return LiveSessionStatus.LIVE

    def is_visible_to(self, user_id: UUID) -> bool:
        """Mirrored in SQL by `live_session_visible_to`."""
        return self.visibility == LiveSessionVisibility.OWNER and (
            self.user_id == user_id
        )

    def may_be_ended_by(self, user_id: UUID) -> bool:
        return self.user_id == user_id


class LiveSessionCreate(BaseModel):
    orbit_id: UUID
    user_id: UUID
    label: str | None = None
    visibility: LiveSessionVisibility
    relay_id: UUID


class LiveSessionStartIn(BaseModel):
    label: str | None = Field(default=None, min_length=1)


class LiveSessionStartOut(BaseModel):
    id: str
    public_url: str
    agent_url: str
    expose_token: str
    token_expires_at: datetime
    heartbeat_interval: int = LIVE_SESSION_HEARTBEAT_INTERVAL_SECONDS


class LiveSessionHeartbeatIn(BaseModel):
    connected: bool
    token_expires_at: AwareDatetime


class LiveSessionHeartbeatOut(BaseModel):
    status: LiveSessionStatus
    expose_token: str | None = None
    token_expires_at: datetime | None = None


def _validate_destination(value: str) -> str:
    # A single leading slash keeps the redirect on the session's hostname.
    # Browsers drop tabs and newlines and read a backslash as a slash, so
    # "/\host" or "/<tab>/host" would leave it.
    if not value.startswith("/") or value.startswith("//"):
        raise ValueError("Destination must be a path that starts with a single slash")
    if any(char == "\\" or ord(char) < 0x20 or ord(char) == 0x7F for char in value):
        raise ValueError(
            "Destination must not contain backslashes or control characters"
        )
    return value


class LiveSessionViewTokenIn(BaseModel):
    destination: str | None = None

    @field_validator("destination")
    @classmethod
    def validate_destination(cls, value: str | None) -> str | None:
        return None if value is None else _validate_destination(value)


class LiveSessionViewTokenOut(BaseModel):
    token: str
    launch_url: str
    expires_at: datetime


class LiveSessionToken(BaseModel, BaseOrmConfig):
    id: UUID
    kind: SessionTokenKind
    session_id: str
    user_id: UUID
    expires_at: datetime
    launched_at: datetime | None = None
    destination: str | None = None


class LiveSessionTokenCreate(BaseModel):
    kind: SessionTokenKind
    session_id: str
    user_id: UUID
    expires_at: datetime
    destination: str | None = None
