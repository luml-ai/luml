from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class Window(StrEnum):
    H24 = "24h"
    D7 = "7d"
    D30 = "30d"


class Compare(StrEnum):
    REFERENCE = "reference"
    PREVIOUS = "previous"


class SeverityFilter(StrEnum):
    ALL = "all"
    WARNING = "warning"
    CRITICAL = "critical"


class Granularity(StrEnum):
    AUTO = "auto"
    HOUR = "hour"
    DAY = "day"


class Severity(StrEnum):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


class SectionState(StrEnum):
    """Per-section data state, so one GreptimeDB blip degrades a section, not the dashboard."""

    OK = "ok"
    EMPTY = "empty"  # the worker has not materialized this group/window yet
    UNAVAILABLE = "unavailable"  # the underlying store could not be reached


class ProfileStatus(StrEnum):
    READY = "ready"
    PLACEHOLDER = "placeholder"


class SeriesPoint(BaseModel):
    t: datetime
    value: float | None


class Series(BaseModel):
    key: str
    label: str
    unit: str | None = None
    points: list[SeriesPoint]


class AlertBanner(BaseModel):
    group: str
    metric: str
    feature: str | None = None
    severity: Severity
    current_value: float | None = None
    threshold: float | None = None
    message: str
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    # What fired, phrased for a reader: "PSI", "Missing rate", "Latency p95".
    label: str = ""
    unit: str = "score"
    value_label: str = ""
    threshold_label: str = ""
    state: str = "open"
    # How long it has been firing, from first to last confirmation.
    duration_seconds: float | None = None
    # Where the threshold came from; today every metric uses its built-in default.
    threshold_source: str = "default"
    # The alert's own metric across the materialized windows, for the detail panel.
    history: Series | None = None


class Card(BaseModel):
    key: str
    label: str
    value: int | float | None = None
    unit: str | None = None
    delta: int | float | None = None
    delta_kind: Compare | None = None
    critical_count: int | None = None
    feature_names: list[str] | None = None


class DriftedFeature(BaseModel):
    feature: str
    psi: float
    severity: Severity


class HeaderResponse(BaseModel):
    state: SectionState
    deployment_id: UUID
    name: str | None = None
    status: str | None = None
    task_type: str | None = None
    model_name: str | None = None
    environment: str | None = None
    satellite: str | None = None
    inference_url: str | None = None
    last_prediction_at: datetime | None = None
    last_monitored_at: datetime | None = None
    profile_status: ProfileStatus = ProfileStatus.READY


class OverviewResponse(BaseModel):
    state: SectionState
    profile_status: ProfileStatus = ProfileStatus.READY
    cards: list[Card] = []
    alert_banners: list[AlertBanner] = []
    series: list[Series] = []
    top_drifted_features: list[DriftedFeature] = []


class RuntimeResponse(BaseModel):
    state: SectionState
    profile_status: ProfileStatus = ProfileStatus.READY
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0
    error_rate: float = 0.0
    latency_p50_ms: float | None = None
    latency_p95_ms: float | None = None
    latency_max_ms: float | None = None
    timeout_count: int = 0
    failed_inference_count: int = 0
    series: list[Series] = []
    alerts: list[AlertBanner] = []


class UnseenCategoryCount(BaseModel):
    value: str
    count: int


class InvalidValueSummary(BaseModel):
    """What was wrong with the values a feature's rates counted.

    The rates say how broken the input is; this says broken how — which categories arrived
    unseen, how far past the reference bounds the numbers went, what types came instead.
    """

    missing_count: int = 0
    type_mismatch_count: int = 0
    observed_types: dict[str, int] = {}
    type_examples: list[str] = []
    range_violation_count: int = 0
    below_min: int = 0
    above_max: int = 0
    observed_min: float | None = None
    observed_max: float | None = None
    reference_min: float | None = None
    reference_max: float | None = None
    unseen_category_count: int = 0
    unseen_distinct: int = 0
    reference_categories: int | None = None
    unseen_categories: list[UnseenCategoryCount] = []


class DataQualityFeatureRow(BaseModel):
    feature: str
    kind: str | None = None  # "numeric" | "categorical"
    missing_rate: float | None = None
    type_error_rate: float | None = None
    # The table shows one "range / unseen" column — a feature is either numerical or
    # categorical, so only one of the two applies — but both rates travel for detail.
    range_unseen_rate: float | None = None
    range_violation_rate: float | None = None
    unseen_category_rate: float | None = None
    checked: int | None = None
    status: Severity = Severity.OK
    # None when nothing was rejected in this window — the panel then has nothing to explain.
    invalid: InvalidValueSummary | None = None


class DataQualityResponse(BaseModel):
    state: SectionState
    profile_status: ProfileStatus = ProfileStatus.READY
    features: list[DataQualityFeatureRow] = []
    # One series per check of the selected feature; empty when no feature is asked for.
    trends: list[Series] = []
    alerts: list[AlertBanner] = []


class DistributionBin(BaseModel):
    label: str
    reference: float | None = None
    current: float | None = None


class FeatureDistribution(BaseModel):
    kind: str  # "numeric" | "categorical"
    bins: list[DistributionBin] = []


class FeatureDriftDetail(BaseModel):
    """Per-selected-feature drift detail: the reference-vs-current shape and PSI over time."""

    feature: str
    psi: float | None = None
    status: Severity = Severity.OK
    distribution: FeatureDistribution | None = None
    psi_over_time: Series | None = None


class PcaPoint(BaseModel):
    x: float
    y: float


class MultivariatePanel(BaseModel):
    state: SectionState = SectionState.EMPTY
    status: Severity = Severity.OK
    shift_value: float | None = None
    shift_metric: str | None = None
    # Unit for shift_value; empty for a unitless measure.
    shift_unit: str = ""
    # Spread of the live cloud over the reference one, per component (1.0 = unchanged).
    dispersion_ratio: float | None = None
    # Share of live rows past the reference's own 99th percentile.
    outlier_rate: float | None = None
    # 95% confidence ellipses of both Gaussians, as closed polygons in PC1 × PC2.
    reference_ellipse: list[PcaPoint] = []
    current_ellipse: list[PcaPoint] = []
    explained_variance: list[float] = []
    feature_psi: list[DriftedFeature] = []
    reference_projection: list[PcaPoint] = []
    current_projection: list[PcaPoint] = []


class FeatureDriftResponse(BaseModel):
    state: SectionState
    profile_status: ProfileStatus = ProfileStatus.READY
    features: list[DriftedFeature] = []  # ranked PSI list with per-feature status
    selected: FeatureDriftDetail | None = None
    multivariate: MultivariatePanel = Field(default_factory=MultivariatePanel)
    alerts: list[AlertBanner] = []


class ReferenceProfileFeature(BaseModel):
    feature: str
    kind: str  # "numeric" | "categorical"
    summary: dict[str, float] = {}
    bin_edges: list[float] | None = None
    histogram: list[float] | None = None
    categories: list[str] | None = None
    category_probabilities: list[float] | None = None


class ReferenceProfileResponse(BaseModel):
    state: SectionState
    profile_status: ProfileStatus = ProfileStatus.READY
    baseline_label: str | None = None
    computed_at: datetime | None = None
    features: list[str] = []  # available feature names to select from
    feature: ReferenceProfileFeature | None = None  # the selected feature's baseline
    # The artifact's profile document itself, for the tab that shows the whole file.
    document: dict[str, Any] | None = None


class MetricFailure(BaseModel):
    metric: str
    error: str
    at: datetime


class MetricIncident(BaseModel):
    """One stretch during which a metric was failing."""

    metric: str
    error: str
    started_at: datetime
    # None while it is still broken.
    ended_at: datetime | None = None
    ongoing: bool = True


class WorkerHealthResponse(BaseModel):
    """Whether the background worker is keeping up for this deployment."""

    state: SectionState
    running: bool = False
    last_tick_at: datetime | None = None
    windows_processed: int = 0
    last_window_end: datetime | None = None
    # Seconds between a window closing and the worker materializing it.
    last_lag_seconds: float | None = None
    window_seconds: float | None = None
    interval_seconds: float | None = None
    failures: list[MetricFailure] = []
    # Failure history from the database, newest first — survives a restart.
    incidents: list[MetricIncident] = []


class AlertGroup(BaseModel):
    """Open alerts for one metric group (runtime, data quality, feature drift)."""

    group: str
    alerts: list[AlertBanner] = []


class AcknowledgeAlertRequest(BaseModel):
    """Which alert a human has seen; the key is the worker's ``group:subject``."""

    metric: str = Field(min_length=1, max_length=200)


class AlertsResponse(BaseModel):
    state: SectionState
    profile_status: ProfileStatus = ProfileStatus.READY
    groups: list[AlertGroup] = []  # read-only; no acknowledge/resolve in this slice


class TraceRow(BaseModel):
    """One recent inference call. Local-only: served only into the same-origin iframe."""

    event_id: str
    ts: datetime
    features_summary: str | None = None
    prediction: str | None = None
    latency_ms: float
    status: str
    status_code: int


class TracesResponse(BaseModel):
    state: SectionState
    profile_status: ProfileStatus = ProfileStatus.READY
    rows: list[TraceRow] = []
    total: int = 0  # matching rows across all pages, so the UI can paginate
    limit: int = 50
    offset: int = 0


class TraceSpan(BaseModel):
    """One span of an inference trace.

    Field-for-field the span shape the Platform's experiment-snapshot viewer renders,
    so the Satellite dashboard can reuse the same tree + waterfall + details screen.
    The tree is built client-side from `parent_span_id`, exactly as the Platform does.
    """

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    name: str
    kind: int
    start_time_unix_nano: int
    end_time_unix_nano: int
    status_code: int | None = None
    status_message: str | None = None
    attributes: dict[str, Any] = {}
    events: list[Any] = []
    links: list[Any] = []
    dfs_span_type: int | None = None
    annotation_count: int = 0  # no annotations on the Satellite; kept for shape parity


class TraceDetail(BaseModel):
    """One inference call, opened from the traces table.

    Unlike :class:`TraceRow`, `inputs` and `output` are the full payloads (decoded
    from their stored JSON when possible), not the truncated table-cell summaries.
    """

    event_id: str
    ts: datetime
    latency_ms: float
    status: str
    status_code: int
    trace_id: str | None = None
    span_id: str | None = None
    inputs: Any = None
    output: Any = None
    spans: list[TraceSpan] = []


class TraceDetailResponse(BaseModel):
    state: SectionState
    profile_status: ProfileStatus = ProfileStatus.READY
    trace: TraceDetail | None = None
