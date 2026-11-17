from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Any, Literal


class ColumnType(StrEnum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    UNKNOWN = "unknown"


class TraceState(IntEnum):
    STATE_UNSPECIFIED = 0
    OK = 1
    ERROR = 2
    IN_PROGRESS = 3


@dataclass
class PaginationCursor:
    id: str
    value: str | None


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
    size: int | None = None
    experiment_id: str | None = None
    source: str | None = None
    description: str | None = None


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
    group_name: str | None = None
    static_params: dict[str, Any] = field(default_factory=dict)
    dynamic_params: dict[str, Any] = field(default_factory=dict)
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    upload_status: str = "not_uploaded"


@dataclass
class ExperimentMetaData:
    name: str
    created_at: datetime
    status: str
    group_id: str
    tags: list[str] = field(default_factory=list)
    duration: float | None = None
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    upload_status: str = "not_uploaded"


@dataclass
class AttachmentRecord:
    id: str | None
    name: str
    file_path: str
    created_at: datetime
    size: int | None = None


@dataclass
class FileNode:
    name: str
    type: Literal["file", "folder"]
    path: str | None = None
    size: int | None = None


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
    annotation_count: int = 0


@dataclass
class TraceRecord:
    trace_id: str
    execution_time: float  # nanoseconds
    span_count: int
    created_at: datetime  # when the first span written to DB
    state: TraceState = TraceState.STATE_UNSPECIFIED
    evals: list[str] = field(default_factory=list)
    annotations: "AnnotationSummary | None" = None


@dataclass
class TraceDetails:
    trace_id: str
    spans: list[SpanRecord] = field(default_factory=list)


@dataclass
class EvalRecord:
    id: str
    dataset_id: str
    inputs: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    outputs: dict[str, Any] | None = None
    refs: dict[str, Any] | None = None
    scores: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    trace_ids: list[str] = field(default_factory=list)
    annotations: "AnnotationSummary | None" = None


@dataclass
class BatchEvalRecord:
    experiment_id: str
    id: str
    dataset_id: str
    inputs: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    outputs: dict[str, Any] | None = None
    refs: dict[str, Any] | None = None
    scores: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    trace_ids: list[str] = field(default_factory=list)
    annotations: "AnnotationSummary | None" = None


@dataclass
class ColumnField:
    name: str
    type: ColumnType


@dataclass
class EvalColumns:
    inputs: list[str]
    outputs: list[str]
    refs: list[str]
    scores: list[str]
    metadata: list[str]


@dataclass
class EvalTypedColumns:
    inputs: list[ColumnField]
    outputs: list[ColumnField]
    refs: list[ColumnField]
    scores: list[ColumnField]
    metadata: list[ColumnField]
    annotations_feedback: list[ColumnField] = field(default_factory=list)
    annotations_expectations: list[ColumnField] = field(default_factory=list)


@dataclass
class TraceColumns:
    attributes: list[str]


@dataclass
class TraceTypedColumns:
    attributes: list[ColumnField]
    annotations_feedback: list[ColumnField] = field(default_factory=list)
    annotations_expectations: list[ColumnField] = field(default_factory=list)


class AnnotationKind(StrEnum):
    FEEDBACK = "feedback"
    EXPECTATION = "expectation"


class AnnotationValueType(StrEnum):
    INT = "int"
    BOOL = "bool"
    STRING = "string"


@dataclass
class AnnotationRecord:
    id: str
    name: str
    annotation_kind: AnnotationKind
    value_type: AnnotationValueType
    value: int | bool | str
    user: str
    created_at: datetime
    rationale: str | None = None


@dataclass
class FeedbackSummaryItem:
    name: str
    total: int
    counts: dict[str, int]


@dataclass
class ExpectationSummaryItem:
    name: str
    total: int
    positive: int = 0
    negative: int = 0
    value: int | str | None = None


@dataclass
class AnnotationSummary:
    feedback: list[FeedbackSummaryItem]
    expectations: list[ExpectationSummaryItem]


@dataclass
class MetricSummary:
    """`min` and `max` cover numeric values, infinities included.

    `count`, `min` and `max` are None below schema revision 3, where only the
    (key, step) index is read.
    """

    key: str
    first_step: int
    last_step: int
    count: int | None
    min: float | None
    max: float | None


@dataclass
class MetricCatalog:
    """The stored bucket levels are None below schema revision 3.

    `skipped_rows` counts the rows of revisions 0-2 that the catalog and the buckets
    leave out: a key that is not text or a NULL, text or BLOB step. Rows with a
    fractional REAL step are left out too but not counted here: the bucket reads
    count them, except for a text key without any integer step, whose REAL-step
    rows are counted here as it is not listed.
    """

    revision: int
    metrics: list[MetricSummary]
    bucket_min_level: int | None = None
    bucket_max_level: int | None = None
    skipped_rows: int = 0


@dataclass
class MetricBucket:
    """`sum` covers finite values only, so the average is `sum / finite_count`."""

    bucket: int
    first_step: int
    last_step: int
    count: int
    finite_count: int
    min: float | None
    max: float | None
    sum: float | None


@dataclass
class MetricBuckets:
    """`first_step` and `last_step` span the whole metric; None for an unknown key.

    `skipped_rows` counts the rows of revisions 0-2 with a fractional REAL step in the
    requested step range, unbounded on a side given as None, which the buckets leave
    out. The catalog's `skipped_rows` does not include them.
    """

    key: str
    level: int
    first_step: int | None
    last_step: int | None
    buckets: list[MetricBucket] = field(default_factory=list)
    skipped_rows: int = 0
