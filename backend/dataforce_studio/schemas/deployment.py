from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from dataforce_studio.schemas.base import BaseOrmConfig


class DeploymentStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    FAILED = "failed"
    DELETED = "deleted"
    DELETION_PENDING = "deletion_pending"


class Deployment(BaseModel, BaseOrmConfig):
    id: int
    orbit_id: int
    satellite_id: int
    satellite_name: str
    name: str
    model_id: int
    model_artifact_name: str
    collection_id: int
    inference_url: str | None = None
    status: DeploymentStatus
    satellite_parameters: dict[str, int | str] = Field(default_factory=dict)
    description: str | None = None
    dynamic_attributes_secrets: dict[str, int] = Field(default_factory=dict)
    env_variables_secrets: dict[str, int] = Field(default_factory=dict)
    env_variables: dict[str, str] = Field(default_factory=dict)
    created_by_user: str | None = None
    tags: list[str] | None = None
    created_at: datetime
    updated_at: datetime | None = None


class DeploymentCreate(BaseModel, BaseOrmConfig):
    orbit_id: int
    satellite_id: int
    model_id: int
    name: str
    satellite_parameters: dict[str, int | str] = Field(default_factory=dict)
    description: str | None = None
    dynamic_attributes_secrets: dict[str, int] = Field(default_factory=dict)
    env_variables_secrets: dict[str, int] = Field(default_factory=dict)
    env_variables: dict[str, str] = Field(default_factory=dict)
    status: DeploymentStatus = DeploymentStatus.PENDING
    created_by_user: str | None = None
    tags: list[str] | None = None


class DeploymentCreateIn(BaseModel):
    satellite_id: int
    model_artifact_id: int
    name: str
    satellite_parameters: dict[str, int | str] = Field(default_factory=dict)
    description: str | None = None
    dynamic_attributes_secrets: dict[str, int] = Field(default_factory=dict)
    env_variables_secrets: dict[str, int] = Field(default_factory=dict)
    env_variables: dict[str, str] = Field(default_factory=dict)
    tags: list[str] | None = None


class DeploymentUpdate(BaseModel, BaseOrmConfig):
    id: int
    inference_url: str | None = None
    status: DeploymentStatus | None = None
    tags: list[str] | None = None


class DeploymentUpdateIn(BaseModel):
    inference_url: str
    tags: list[str] | None = None


class InferenceAccessIn(BaseModel):
    api_key: str


class InferenceAccessOut(BaseModel):
    authorized: bool


class DeploymentDetailsUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    dynamic_attributes_secrets: dict[str, int] | None = None
    tags: list[str] | None = None


class DeploymentStatusUpdateIn(BaseModel):
    status: DeploymentStatus
