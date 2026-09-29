from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from luml_satellite.wire._base import PlatformModel


class DeploymentStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    FAILED = "failed"
    DELETION_FAILED = "deletion_failed"
    DELETION_PENDING = "deletion_pending"
    NOT_RESPONDING = "not_responding"


class ErrorMessage(PlatformModel):
    reason: str
    error: str


class DeploymentUpdate(PlatformModel):
    status: DeploymentStatus | None = None
    inference_url: str | None = None
    monitoring_url: str | None = None
    schemas: dict[str, Any] | None = None
    error_message: ErrorMessage | dict[str, Any] | None = None
    provider_ref: str | None = None
    progress_note: str | None = None


class Deployment(PlatformModel):
    id: str
    orbit_id: str
    satellite_id: str
    satellite_name: str
    orbit_name: str | None = None
    name: str
    artifact_id: str
    artifact_name: str
    collection_id: str
    inference_url: str | None = None
    monitoring_url: str | None = None
    status: str
    monitoring_mode: str = "off"
    satellite_parameters: dict[str, bool | int | str] | None = Field(default_factory=dict)
    description: str | None = None
    dynamic_attributes_secrets: dict[str, str] | None = Field(default_factory=dict)
    env_variables_secrets: dict[str, str] | None = Field(default_factory=dict)
    env_variables: dict[str, str] | None = Field(default_factory=dict)
    schemas: dict[str, Any] | None = None
    error_message: dict[str, Any] | None = None
    provider_ref: str | None = None
    progress_note: str | None = None
    created_by_user: str | None = None
    tags: list[str] | None = None
    created_at: str
    updated_at: str | None = None


class Secret(PlatformModel):
    name: str
    value: str


class InferenceAccessIn(PlatformModel):
    api_key: str


class InferenceAccessOut(PlatformModel):
    authorized: bool


class DeploymentInfo(PlatformModel):
    deployment_id: str
    name: str | None = None
    status: str | None = None
    monitoring_mode: str | None = None
    last_monitored_at: datetime | None = None


class ArtifactDownload(PlatformModel):
    url: str
    artifact_id: str
    expires_at: datetime | None = None


class Healthz(PlatformModel):
    status: str = "healthy"
