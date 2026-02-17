from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from lumlflow.schemas.base import BaseOrmConfig
from lumlflow.schemas.models import ModelSimple


class Experiment(BaseModel, BaseOrmConfig):
    id: str
    name: str
    status: str
    group_id: str
    created_at: datetime
    tags: list[str] | None = None
    static_params: dict[str, Any] | None = None
    dynamic_params: dict[str, Any] | None = None
    model_id: str | None = None


class ExperimentMetaData(BaseModel, BaseOrmConfig):
    name: str
    created_at: datetime
    status: str
    group_id: str
    tags: list[str] | None = None


class ExperimentData(BaseModel, BaseOrmConfig):
    experiment_id: str
    metadata: ExperimentMetaData
    static_params: dict[str, Any] | None = None
    dynamic_metrics: dict[str, Any] | None = None
    attachments: dict[str, Any] | None = None


class ExperimentsSortBy(StrEnum):
    NAME = "name"
    CREATED_AT = "created_at"


class ExperimentSimple(BaseModel, BaseOrmConfig):
    id: str
    name: str
    status: str
    created_at: datetime
    tags: list[str] | None = None
    models: list[ModelSimple] | None = None


class PaginatedExperiments(BaseModel):
    items: list[ExperimentSimple]
    cursor: str | None = None
