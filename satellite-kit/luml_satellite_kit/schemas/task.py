from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class SatelliteTaskType(StrEnum):
    DEPLOY = "deploy"
    UNDEPLOY = "undeploy"


class SatelliteTaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class SatelliteQueueTask(BaseModel):
    id: str
    satellite_id: str
    orbit_id: str
    type: SatelliteTaskType
    payload: dict[str, Any] | None = None
    status: SatelliteTaskStatus
    scheduled_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime | None = None
