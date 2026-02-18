from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import AliasChoices, BaseModel, Field

from lumlflow.schemas.base import BaseOrmConfig
from lumlflow.schemas.models import Model


class Experiment(BaseModel, BaseOrmConfig):
    id: str
    name: str
    status: str
    group_id: str
    created_at: datetime
    duration: float | None = None
    description: str | None = None
    tags: list[str] | None = None
    static_params: dict[str, Any] | None = None
    dynamic_params: dict[str, Any] | None = None


class ExperimentMetaData(BaseModel, BaseOrmConfig):
    name: str
    created_at: datetime
    status: str
    group_id: str
    tags: list[str] | None = None
    duration: float | None = None
    description: str | None = None


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


class ExperimentListed(BaseModel, BaseOrmConfig):
    id: str
    name: str
    created_at: datetime
    tags: list[str] | None = None
    models: list[Model] | None = None
    duration: float | None = None
    description: str | None = None
    static_params: dict[str, Any] | None = None
    dynamic_metrics: dict[str, Any] | None = Field(
        None, validation_alias=AliasChoices("dynamic_metrics", "dynamic_params")
    )


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
