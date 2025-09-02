from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, HttpUrl

from dataforce_studio.schemas.base import BaseOrmConfig


class SatelliteCapability(StrEnum):
    DEPLOY = "deploy"


class SatelliteTaskType(StrEnum):
    PAIRING = "pairing"
    DEPLOY = "deploy"


class SatelliteTaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Satellite(BaseModel, BaseOrmConfig):
    id: int
    orbit_id: int
    name: str | None = None
    base_url: str | None = None
    paired: bool
    capabilities: dict[SatelliteCapability, dict[str, Any] | None]
    created_at: datetime
    updated_at: datetime | None = None
    last_seen_at: datetime | None = None


class SatelliteCreateIn(BaseModel, BaseOrmConfig):
    name: str | None = None


class SatelliteCreate(BaseModel, BaseOrmConfig):
    orbit_id: int
    api_key_hash: str
    name: str | None = None


class SatellitePairIn(BaseModel):
    base_url: HttpUrl
    capabilities: dict[SatelliteCapability, dict[str, Any] | None]


class SatelliteQueueTask(BaseModel, BaseOrmConfig):
    id: int
    satellite_id: int
    orbit_id: int
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
    task: SatelliteQueueTask


class SatelliteTaskUpdateIn(BaseModel):
    status: SatelliteTaskStatus
    result: dict[str, Any] | None = None
