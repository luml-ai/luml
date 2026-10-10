from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from luml.schemas.base import BaseOrmConfig
from luml.schemas.live_session import LiveSessionStartOut, LiveSessionStatus


class FlowSession(BaseModel, BaseOrmConfig):
    id: str
    status: LiveSessionStatus
    started_at: datetime
    last_heartbeat_at: datetime | None = None


class Flow(BaseModel):
    id: UUID
    orbit_id: UUID
    user_id: UUID
    name: str
    session: FlowSession
    created_at: datetime


class FlowCreate(BaseModel):
    orbit_id: UUID
    user_id: UUID
    name: str
    session_id: str


class FlowExposeIn(BaseModel):
    name: str = Field(min_length=1)


class FlowExposeOut(BaseModel):
    flow: Flow
    session: LiveSessionStartOut
    app_url: str
