from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, HttpUrl, computed_field

from luml.schemas.base import BaseOrmConfig


class SatelliteCapability(StrEnum):
    DEPLOY = "deploy"


class SatelliteTaskType(StrEnum):
    DEPLOY = "deploy"
    UNDEPLOY = "undeploy"


class SatelliteTaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class SatelliteStatus(StrEnum):
    ACTIVE = "active"  # green
    INACTIVE = "inactive"  # red
    ERROR = "error"  # orange


class Satellite(BaseModel, BaseOrmConfig):
    id: UUID
    orbit_id: UUID
    name: str | None = None
    description: str | None = None
    base_url: str | None = None
    paired: bool
    capabilities: dict[SatelliteCapability, dict[str, Any] | None]
    slug: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    last_seen_at: datetime | None = None

    @computed_field
    def status(self) -> SatelliteStatus:
        if not self.paired or self.last_seen_at is None:
            return SatelliteStatus.INACTIVE

        if self.last_seen_at is None:
            return SatelliteStatus.ERROR

        time_diff = datetime.now(UTC) - self.last_seen_at
        if time_diff > timedelta(minutes=20):
            return SatelliteStatus.ERROR

        return SatelliteStatus.ACTIVE


class SatelliteCreateIn(BaseModel, BaseOrmConfig):
    name: str | None = None
    description: str | None = None


class SatelliteCreate(BaseModel, BaseOrmConfig):
    orbit_id: UUID
    api_key_hash: str
    name: str | None = None
    description: str | None = None


class SatellitePairIn(BaseModel):
    base_url: HttpUrl
    capabilities: dict[SatelliteCapability, dict[str, Any] | None]
    slug: str | None = None


class SatellitePair(BaseModel, BaseOrmConfig):
    id: UUID
    base_url: str
    capabilities: dict[SatelliteCapability, dict[str, Any] | None]
    slug: str | None = None
    paired: bool = True
    last_seen_at: datetime


class SatelliteUpdateIn(BaseModel, BaseOrmConfig):
    name: str | None = None
    description: str | None = None


class SatelliteUpdate(BaseModel, BaseOrmConfig):
    id: UUID
    name: str | None = None
    description: str | None = None


class SatelliteRegenerateApiKey(BaseModel, BaseOrmConfig):
    id: UUID
    api_key_hash: str


class SatelliteQueueTask(BaseModel, BaseOrmConfig):
    id: UUID
    satellite_id: UUID
    orbit_id: UUID
    type: SatelliteTaskType
    payload: dict[str, Any]
    status: SatelliteTaskStatus
    scheduled_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime | None = None


class SatelliteCreateOut(BaseModel, BaseOrmConfig):
    satellite: Satellite
    api_key: str


class SatelliteTaskUpdateIn(BaseModel):
    status: SatelliteTaskStatus
    result: dict[str, Any] | None = None
