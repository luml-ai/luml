"""Common schemas for LUML Satellite SDK.

This module contains shared Pydantic models and enums used for communication
between satellites and the LUML platform. These schemas ensure consistent
data models across all satellite implementations.
"""

import sys
from datetime import datetime
from typing import Any

from pydantic import BaseModel

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        """Backport of StrEnum for Python <3.11."""

        pass


class SatelliteTaskType(StrEnum):
    """Base task types supported by satellites.

    Satellites can extend this enum to add custom task types
    while maintaining compatibility with the platform.
    """

    DEPLOY = "deploy"
    UNDEPLOY = "undeploy"


class SatelliteTaskStatus(StrEnum):
    """Status values for satellite tasks.

    These statuses track the lifecycle of a task from creation to completion.
    """

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class SatelliteQueueTask(BaseModel):
    """A task queued for satellite execution.

    This schema represents a task message received from the platform's
    task queue. Satellites poll for these tasks and execute them based
    on their registered capabilities.

    Attributes:
        id: Unique identifier for the task.
        satellite_id: ID of the satellite assigned to execute this task.
        orbit_id: ID of the orbit this task belongs to.
        type: The type of task to execute.
        payload: Task-specific data needed for execution.
        status: Current status of the task.
        scheduled_at: When the task was scheduled for execution.
        started_at: When the satellite started executing the task.
        finished_at: When the task completed (successfully or with failure).
        result: Output data from task execution.
        created_at: When the task was created.
        updated_at: When the task was last updated.
    """

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
