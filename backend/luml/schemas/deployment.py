from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from luml.schemas.base import BaseOrmConfig


class DeploymentStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    FAILED = "failed"
    DELETION_PENDING = "deletion_pending"
    DELETION_FAILED = "deletion_failed"
    NOT_RESPONDING = "not_responding"


class Deployment(BaseModel, BaseOrmConfig):
    id: UUID
    orbit_id: UUID
    satellite_id: UUID
    satellite_name: str
    name: str
    model_id: UUID
    model_artifact_name: str
    collection_id: UUID
    inference_url: str | None = None
    status: DeploymentStatus
    satellite_parameters: dict[str, int | str] = Field(default_factory=dict)
    description: str | None = None
    dynamic_attributes_secrets: dict[str, str] = Field(default_factory=dict)
    env_variables_secrets: dict[str, str] = Field(default_factory=dict)
    env_variables: dict[str, str] = Field(default_factory=dict)
    schemas: dict[str, Any] | None = None
    error_message: dict[str, Any] | None = None
    created_by_user: str | None = None
    tags: list[str] | None = None
    created_at: datetime
    updated_at: datetime | None = None


class DeploymentCreate(BaseModel, BaseOrmConfig):
    orbit_id: UUID
    satellite_id: UUID
    model_id: UUID
    name: str
    satellite_parameters: dict[str, int | str] = Field(default_factory=dict)
    description: str | None = None
    dynamic_attributes_secrets: dict[str, str] = Field(default_factory=dict)
    env_variables_secrets: dict[str, str] = Field(default_factory=dict)
    env_variables: dict[str, str] = Field(default_factory=dict)
    status: DeploymentStatus = DeploymentStatus.PENDING
    created_by_user: str | None = None
    tags: list[str] | None = None


class DeploymentCreateIn(BaseModel):
    satellite_id: UUID
    model_artifact_id: UUID
    name: str
    satellite_parameters: dict[str, int | str] = Field(default_factory=dict)
    description: str | None = None
    dynamic_attributes_secrets: dict[str, UUID] = Field(default_factory=dict)
    env_variables_secrets: dict[str, UUID] = Field(default_factory=dict)
    env_variables: dict[str, str] = Field(default_factory=dict)
    tags: list[str] | None = None


class DeploymentUpdate(BaseModel, BaseOrmConfig):
    id: UUID
    inference_url: str | None = None
    status: DeploymentStatus | None = None
    tags: list[str] | None = None
    schemas: dict[str, Any] | None = None
    error_message: dict[str, Any] | None = None


class DeploymentUpdateIn(BaseModel):
    inference_url: str | None = None
    status: DeploymentStatus | None = None
    tags: list[str] | None = None
    schemas: dict[str, Any] | None = None
    error_message: dict[str, Any] | None = None


class InferenceAccessIn(BaseModel):
    api_key: str


class InferenceAccessOut(BaseModel):
    authorized: bool


class DeploymentDetailsUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    dynamic_attributes_secrets: dict[str, UUID] | None = None
    schemas: dict[str, Any] | None = None
    error_message: dict[str, Any] | None = None
    tags: list[str] | None = None


class DeploymentDetailsUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    dynamic_attributes_secrets: dict[str, str] | None = None
    schemas: dict[str, Any] | None = None
    error_message: dict[str, Any] | None = None
    tags: list[str] | None = None


class DeploymentStatusUpdateIn(BaseModel):
    status: DeploymentStatus
