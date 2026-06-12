from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, computed_field

from luml.schemas.base import BaseOrmConfig


class DeploymentStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    FAILED = "failed"
    DELETION_PENDING = "deletion_pending"
    DELETION_FAILED = "deletion_failed"
    NOT_RESPONDING = "not_responding"


class DeploymentBase(BaseModel, BaseOrmConfig):
    id: UUID
    name: str
    status: DeploymentStatus
    orbit_id: UUID


class Deployment(DeploymentBase):
    id: UUID
    orbit_id: UUID
    satellite_id: UUID
    satellite_name: str
    name: str
    artifact_id: UUID
    artifact_name: str
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

    @computed_field(deprecated=True)  # type: ignore[prop-decorator]
    @property
    def model_id(self) -> UUID:
        return self.artifact_id

    @computed_field(deprecated=True)  # type: ignore[prop-decorator]
    @property
    def model_artifact_name(self) -> str:
        return self.artifact_name


class DeploymentCreateIn(BaseModel):
    satellite_id: UUID
    artifact_id: UUID
    name: str
    satellite_parameters: dict[str, int | str] = Field(default_factory=dict)
    description: str | None = None
    dynamic_attributes_secrets: dict[str, UUID] = Field(default_factory=dict)
    env_variables_secrets: dict[str, UUID] = Field(default_factory=dict)
    env_variables: dict[str, str] = Field(default_factory=dict)
    tags: list[str] | None = None


class DeploymentCreate(DeploymentCreateIn, BaseOrmConfig):
    orbit_id: UUID
    status: DeploymentStatus = DeploymentStatus.PENDING
    created_by_user: str | None = None


class DeploymentUpdateIn(BaseModel):
    inference_url: str | None = None
    status: DeploymentStatus | None = None
    tags: list[str] | None = None
    schemas: dict[str, Any] | None = None
    error_message: dict[str, Any] | None = None


class DeploymentUpdate(DeploymentUpdateIn, BaseOrmConfig):
    id: UUID


class InferenceAccessIn(BaseModel):
    api_key: str


class InferenceAccessOut(BaseModel):
    authorized: bool


# TODO leave only one class DeploymentDetailsUpdate
class DeploymentDetailsUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    dynamic_attributes_secrets: dict[str, UUID] | None = None
    schemas: dict[str, Any] | None = None
    error_message: dict[str, Any] | None = None
    tags: list[str] | None = None


class DeploymentDetailsUpdate(DeploymentDetailsUpdateIn):
    name: str | None = None
    description: str | None = None
    dynamic_attributes_secrets: dict[str, str] | None = None
    schemas: dict[str, Any] | None = None
    error_message: dict[str, Any] | None = None
    tags: list[str] | None = None


class DeploymentStatusUpdateIn(BaseModel):
    status: DeploymentStatus
