from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, computed_field

from luml.schemas.base import BaseOrmConfig

LIVE_SESSION_DISCONNECTED_AFTER = timedelta(seconds=90)
LIVE_SESSION_ENDED_AFTER = timedelta(hours=1)
LIVE_SESSION_LIST_RETENTION = timedelta(hours=24)
LIVE_SESSION_HEARTBEAT_INTERVAL_SECONDS = 30


class LiveSessionStatus(StrEnum):
    LIVE = "live"
    DISCONNECTED = "disconnected"
    ENDED = "ended"


class LiveSession(BaseModel, BaseOrmConfig):
    id: str
    orbit_id: UUID
    user_id: UUID
    name: str
    relay_id: UUID | None = None
    started_at: datetime
    last_heartbeat_at: datetime | None = None
    connected: bool
    ended_at: datetime | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> LiveSessionStatus:
        if self.ended_at is not None:
            return LiveSessionStatus.ENDED
        # Before the first heartbeat, silence is counted from the start.
        silent_for = datetime.now(UTC) - (self.last_heartbeat_at or self.started_at)
        if silent_for > LIVE_SESSION_ENDED_AFTER:
            return LiveSessionStatus.ENDED
        if silent_for > LIVE_SESSION_DISCONNECTED_AFTER or not self.connected:
            return LiveSessionStatus.DISCONNECTED
        return LiveSessionStatus.LIVE


class LiveSessionCreate(BaseModel):
    orbit_id: UUID
    user_id: UUID
    name: str
    relay_id: UUID


class LiveSessionStartIn(BaseModel):
    name: str = Field(min_length=1)


class LiveSessionStartOut(BaseModel):
    id: str
    public_url: str
    app_url: str
    agent_url: str
    expose_token: str
    token_expires_at: datetime
    heartbeat_interval: int = LIVE_SESSION_HEARTBEAT_INTERVAL_SECONDS


class LiveSessionHeartbeatIn(BaseModel):
    connected: bool
    token_expires_at: datetime


class LiveSessionHeartbeatOut(BaseModel):
    status: LiveSessionStatus
    expose_token: str | None = None
    token_expires_at: datetime | None = None


class LiveSessionViewTokenOut(BaseModel):
    token: str
    launch_url: str
    expires_at: datetime
