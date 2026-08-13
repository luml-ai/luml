from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field, computed_field

from luml.schemas.base import BaseOrmConfig

TagList = Annotated[list[Annotated[str, Field(max_length=64)]], Field(max_length=50)]


class DeploymentStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    FAILED = "failed"
    DELETION_PENDING = "deletion_pending"
    DELETION_FAILED = "deletion_failed"
    NOT_RESPONDING = "not_responding"


class MonitoringMode(StrEnum):
    OFF = "off"
    FULL = "full"


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
    monitoring_mode: MonitoringMode = MonitoringMode.OFF
    satellite_parameters: dict[str, bool | int | str] = Field(default_factory=dict)
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


class DeploymentCreateBase(BaseModel):
    satellite_id: UUID
    artifact_id: UUID
    name: str = Field(max_length=100)
    monitoring_mode: MonitoringMode = MonitoringMode.OFF
    satellite_parameters: dict[str, bool | int | str] = Field(default_factory=dict)
    description: str | None = Field(default=None, max_length=1000)
    env_variables: dict[str, str] = Field(default_factory=dict)
    tags: TagList | None = None


class DeploymentCreateIn(DeploymentCreateBase):
    dynamic_attributes_secrets: dict[str, UUID] = Field(default_factory=dict)
    env_variables_secrets: dict[str, UUID] = Field(default_factory=dict)


class DeploymentCreate(DeploymentCreateBase, BaseOrmConfig):
    orbit_id: UUID
    status: DeploymentStatus = DeploymentStatus.PENDING
    created_by_user: str | None = None
    dynamic_attributes_secrets: dict[str, str] = Field(default_factory=dict)
    env_variables_secrets: dict[str, str] = Field(default_factory=dict)


class DeploymentUpdateIn(BaseModel):
    inference_url: str | None = Field(default=None, max_length=2048)
    status: DeploymentStatus | None = None
    tags: TagList | None = None
    schemas: dict[str, Any] | None = None
    error_message: dict[str, Any] | None = None


class DeploymentUpdate(DeploymentUpdateIn, BaseOrmConfig):
    id: UUID


class InferenceAccessIn(BaseModel):
    api_key: str = Field(max_length=255)


class InferenceAccessOut(BaseModel):
    authorized: bool


class DeploymentDetailsUpdateBase(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    monitoring_mode: MonitoringMode | None = None
    schemas: dict[str, Any] | None = None
    error_message: dict[str, Any] | None = None
    tags: TagList | None = None


class DeploymentDetailsUpdateIn(DeploymentDetailsUpdateBase):
    dynamic_attributes_secrets: dict[str, UUID] | None = None


class DeploymentDetailsUpdate(DeploymentDetailsUpdateBase):
    dynamic_attributes_secrets: dict[str, str] | None = None


class DeploymentStatusUpdateIn(BaseModel):
    status: DeploymentStatus
