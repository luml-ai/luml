from datetime import datetime
from enum import IntEnum, StrEnum
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
    annotation_count: int = 0


class TraceDetails(BaseModel):
    trace_id: str
    spans: list[Span]


class TracesSortBy(StrEnum):
    EXECUTION_TIME = "execution_time"
    SPAN_COUNT = "span_count"
    CREATED_AT = "created_at"


class TraceState(IntEnum):
    STATE_UNSPECIFIED = 0
    OK = 1
    ERROR = 2
    IN_PROGRESS = 3


class Trace(BaseModel, BaseOrmConfig):
    trace_id: str
    execution_time: float  # seconds
    span_count: int
    created_at: datetime
    state: TraceState = TraceState.STATE_UNSPECIFIED
    evals: list[str] = []


class PaginatedTraces(BaseModel):
    items: list[Trace]
    cursor: str | None = None


class EvalsSortBy(StrEnum):
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    DATASET_ID = "dataset_id"


class Eval(BaseModel, BaseOrmConfig):
    id: str
    dataset_id: str
    inputs: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    outputs: dict[str, Any] | None = None
    refs: dict[str, Any] | None = None
    scores: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    trace_ids: list[str] = []


class PaginatedEvals(BaseModel):
    items: list[Eval]
    cursor: str | None = None


class EvalColumns(BaseModel, BaseOrmConfig):
    inputs: list[str]
    outputs: list[str]
    refs: list[str]
    scores: list[str]
