from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from lumlflow.schemas.base import BaseOrmConfig
from lumlflow.schemas.models import Model


class ExperimentStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"


class _ExperimentBase(BaseModel, BaseOrmConfig):
    id: str
    name: str
    status: ExperimentStatus
    duration: float | None = None
    description: str | None = None
    tags: list[str] | None = None
    static_params: dict[str, Any] | None = None
    dynamic_params: dict[str, Any] | None = None
    created_at: datetime


class Experiment(_ExperimentBase):
    group_id: str


class ExperimentListed(_ExperimentBase):
    models: list[Model] | None = None


class ExperimentMetaData(BaseModel, BaseOrmConfig):
    name: str
    status: ExperimentStatus
    group_id: str
    tags: list[str] | None = None
    duration: float | None = None
    description: str | None = None
    created_at: datetime


class ExperimentData(BaseModel, BaseOrmConfig):
    experiment_id: str
    metadata: ExperimentMetaData
    static_params: dict[str, Any] | None = None
    dynamic_metrics: dict[str, Any] | None = None
    attachments: dict[str, Any] | None = None


class ExperimentDetails(Experiment):
    models: list[Model] | None = None


class UpdateExperiment(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class ExperimentsSortBy(StrEnum):
    NAME = "name"
    CREATED_AT = "created_at"
    DURATION = "duration"
    MODELS = "models"


class PaginatedExperiments(BaseModel):
    items: list[ExperimentListed]
    cursor: str | None = None


class MetricPoint(BaseModel):
    value: float
    step: int
    logged_at: datetime | None = None


class ExperimentMetricHistory(BaseModel):
    experiment_id: str
    key: str
    subsampled: bool = False
    history: list[MetricPoint]


class Span(BaseModel, BaseOrmConfig):
    span_id: str
    parent_span_id: str | None = None
    name: str
    kind: int
    dfs_span_type: int
    start_time_unix_nano: int
    end_time_unix_nano: int
    status_code: int | None = None
    status_message: str | None = None
    attributes: dict[str, Any] | None = None
    events: list[dict[str, Any]] | None = None
    links: list[dict[str, Any]] | None = None
    trace_flags: int | None = None


class Trace(BaseModel):
    trace_id: str
    root_span: Span | None = None
    spans: list[Span]


class PaginatedTraces(BaseModel):
    items: list[Trace]
    cursor: str | None = None
