from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class DeploymentStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    FAILED = "failed"
    DELETION_FAILED = "deletion_failed"
    DELETION_PENDING = "deletion_pending"
    NOT_RESPONDING = "not_responding"


class ErrorMessage(BaseModel):
    reason: str
    error: str


class DeploymentUpdate(BaseModel):
    status: DeploymentStatus | None = None
    inference_url: str | None = None
    schemas: dict[str, Any] | None = None
    error_message: ErrorMessage | None = None


class Deployment(BaseModel):
    id: str
    orbit_id: str
    satellite_id: str
    satellite_name: str
    name: str
    model_id: str
    model_artifact_name: str
    collection_id: str
    inference_url: str | None = None
    status: str
    satellite_parameters: dict[str, int | str] | None = {}
    description: str | None = None
    dynamic_attributes_secrets: dict[str, str] | None = {}
    env_variables_secrets: dict[str, str] | None = {}
    env_variables: dict[str, str] | None = {}
    schemas: dict[str, Any] | None = None
    error_message: dict[str, Any] | None = None
    created_by_user: str | None = None
    tags: list[str] | None = None
    created_at: str
    updated_at: str | None = None


class LocalDeployment(BaseModel):
    deployment_id: str
    dynamic_attributes_secrets: dict[str, str] | None = {}
    manifest: dict | None = None
    openapi_schema: dict | None = None


class Secret(BaseModel):
    name: str
    value: str


class InferenceAccessIn(BaseModel):
    api_key: str


class InferenceAccessOut(BaseModel):
    authorized: bool


class DeploymentInfo(BaseModel):
    deployment_id: str


class Healthz(BaseModel):
    status: str = "healthy"
