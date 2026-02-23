from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PaginatedResponse[T]:
    items: list[T]
    cursor: str | None


@dataclass
class Group:
    id: str
    name: str
    description: str | None
    created_at: datetime
    tags: list[str] = field(default_factory=list)
    last_modified: datetime | None = None


@dataclass
class Model:
    id: str
    name: str
    created_at: datetime
    tags: list[str] = field(default_factory=list)
    path: str | None = None
    experiment_id: str | None = None


@dataclass
class Experiment:
    id: str
    name: str
    status: str
    created_at: datetime
    tags: list[str] = field(default_factory=list)
    models: list[Model] = field(default_factory=list)
    duration: float | None = None
    description: str | None = None
    group_id: str | None = None
    static_params: dict[str, Any] | None = None
    dynamic_params: dict[str, Any] | None = None


@dataclass
class ExperimentMetaData:
    name: str
    created_at: datetime
    status: str
    group_id: str
    tags: list[str] = field(default_factory=list)
    duration: float | None = None
    description: str | None = None


@dataclass
class ExperimentData:
    experiment_id: str
    metadata: ExperimentMetaData
    static_params: dict[str, Any] = field(default_factory=dict)
    dynamic_metrics: dict[str, Any] = field(default_factory=dict)
    attachments: dict[str, Any] = field(default_factory=dict)


@dataclass
class SpanRecord:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    kind: int
    dfs_span_type: int
    start_time_unix_nano: int
    end_time_unix_nano: int
    status_code: int | None
    status_message: str | None
    attributes: dict[str, Any] | None
    events: list[dict[str, Any]] | None
    links: list[dict[str, Any]] | None
    trace_flags: int | None


@dataclass
class TraceRecord:
    trace_id: str
    spans: list[SpanRecord] = field(default_factory=list)
