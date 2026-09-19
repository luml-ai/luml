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
    # Legacy no-op: drift always measures against the training reference — same as "off".
    OFF = "off"
    REFERENCE = "reference"
    PREVIOUS = "previous"
    CUSTOM = "custom"


class TraceSort(StrEnum):
    TS = "ts"
    LATENCY = "latency"
    STATUS = "status"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


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
    ABSENT = "absent"
    UNSUPPORTED = "unsupported"


class SeriesPoint(BaseModel):
    t: datetime
    value: float | None


class Series(BaseModel):
    key: str
    label: str
    unit: str | None = None
    points: list[SeriesPoint]
    # Comparison-period series, time-shifted onto this axis; compare mode only.
    baseline: list[SeriesPoint] | None = None


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
    # Cards that summarize a scored metric carry its severity so the UI can tone them.
    severity: Severity | None = None


class DriftedFeature(BaseModel):
    feature: str
    psi: float
    severity: Severity
    # Compare mode: typical PSI over the comparison period, and the move from it.
    baseline_psi: float | None = None
    psi_delta: float | None = None


class ModelKind(StrEnum):
    TABULAR = "tabular"
    LLM = "llm"
    UNKNOWN = "unknown"


class HeaderResponse(BaseModel):
    state: SectionState
    deployment_id: UUID
    name: str | None = None
    status: str | None = None
    task_type: str | None = None
    model_kind: ModelKind = ModelKind.UNKNOWN
    model_name: str | None = None
    environment: str | None = None
    satellite: str | None = None
    inference_url: str | None = None
    last_prediction_at: datetime | None = None
    last_monitored_at: datetime | None = None
    profile_status: ProfileStatus = ProfileStatus.ABSENT


class OverviewResponse(BaseModel):
    state: SectionState
    profile_status: ProfileStatus = ProfileStatus.ABSENT
    cards: list[Card] = []
    alert_banners: list[AlertBanner] = []
    series: list[Series] = []
    top_drifted_features: list[DriftedFeature] = []


class RuntimeBaseline(BaseModel):
    """The comparison period's rollup, so every runtime card can show its delta."""

    start: datetime
    end: datetime
    request_count: int
    success_rate: float
    error_rate: float
    latency_p50_ms: float | None = None
    latency_p95_ms: float | None = None
    latency_max_ms: float | None = None
    timeout_count: int
    failed_inference_count: int


class StatusBreakdownRow(BaseModel):
    """How the window's calls ended, one row per outcome and HTTP code.

    The counters above say how many calls failed; this says how they failed, which is what
    separates a saturated model server (504) from a caller sending bad payloads (422).
    """

    status: str
    status_code: int | None = None
    count: int = 0
    share: float = 0.0


class RuntimeResponse(BaseModel):
    state: SectionState
    profile_status: ProfileStatus = ProfileStatus.ABSENT
    request_count: int = 0
    success_count: int = 0
    success_rate: float = 0.0
    error_count: int = 0
    error_rate: float = 0.0
    latency_p50_ms: float | None = None
    latency_p95_ms: float | None = None
    latency_max_ms: float | None = None
    timeout_count: int = 0
    failed_inference_count: int = 0
    status_breakdown: list[StatusBreakdownRow] = []
    baseline: RuntimeBaseline | None = None
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
    # Only one of the two applies per feature; both rates travel for the detail panel.
    range_unseen_rate: float | None = None
    range_violation_rate: float | None = None
    unseen_category_rate: float | None = None
    checked: int | None = None
    status: Severity = Severity.OK
    # None when nothing was rejected in this window.
    invalid: InvalidValueSummary | None = None
    # Compare mode: current rate minus the comparison period's mean, per check.
    missing_delta: float | None = None
    type_error_delta: float | None = None
    range_unseen_delta: float | None = None


class DataQualityResponse(BaseModel):
    state: SectionState
    profile_status: ProfileStatus = ProfileStatus.ABSENT
    features: list[DataQualityFeatureRow] = []
    # One series per check of the selected feature; empty when no feature is asked for.
    trends: list[Series] = []
    alerts: list[AlertBanner] = []
    # End of the described window. The table is a snapshot of the last computed window,
    # so an idle stand keeps readings the range no longer covers — see `stale`.
    computed_at: datetime | None = None
    stale: bool = False


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
    profile_status: ProfileStatus = ProfileStatus.ABSENT
    features: list[DriftedFeature] = []  # ranked PSI list with per-feature status
    selected: FeatureDriftDetail | None = None
    multivariate: MultivariatePanel = Field(default_factory=MultivariatePanel)
    alerts: list[AlertBanner] = []
    # End of the window this ranking and the multivariate panel describe.
    computed_at: datetime | None = None
    # True when the window closed before the selected range began; without the flag a
    # stale snapshot reads as current while the in-range trends go empty.
    stale: bool = False


class ClassShift(BaseModel):
    """How far one predicted class moved from its reference share."""

    label: str
    reference: float
    current: float
    delta: float


class ClassProbabilityDrift(BaseModel):
    """One class's probability distribution scored against its training baseline."""

    label: str
    psi: float
    mean: float | None = None


class NearThreshold(BaseModel):
    """How often binary predictions sit in the decision boundary's coin-flip zone."""

    rate: float
    reference_rate: float | None = None
    threshold: float
    positive_class: str | None = None


class ProbabilityBlock(BaseModel):
    """Per-class probability drift, from the full vectors the artifact reports."""

    per_class: list[ClassProbabilityDrift] = []
    near_threshold: NearThreshold | None = None


class HorizonDrift(BaseModel):
    """One forecast horizon scored against its training baseline."""

    label: str
    psi: float
    mean: float | None = None
    count: int = 0


class ConfidenceBlock(BaseModel):
    """How sure the classifier is, against how sure it was on its training data."""

    psi: float | None = None
    mean: float | None = None
    low_confidence_rate: float | None = None
    # The training q05: confidence below it is worse than 95% of what training saw.
    low_confidence_threshold: float | None = None
    distribution: FeatureDistribution | None = None
    mean_over_time: Series | None = None


class OutputDriftResponse(BaseModel):
    """Did the model's outputs shift against the reference output distribution?

    The snapshot half (psi, distribution) reads the latest materialized window; the
    series are assembled from the window history of the selected time range.
    """

    state: SectionState
    profile_status: ProfileStatus = ProfileStatus.ABSENT
    # Which output is monitored and how its values are compared.
    name: str | None = None
    kind: str | None = None  # "numeric" | "categorical"
    psi: float | None = None
    severity: Severity = Severity.OK
    count: int = 0
    # Compare mode: mean PSI over the comparison period, and the move from it.
    baseline_psi: float | None = None
    psi_delta: float | None = None
    distribution: FeatureDistribution | None = None
    psi_over_time: Series | None = None
    # Numerical outputs only: median with its p05–p95 band, and the mean, per window.
    trend: list[Series] = []
    # Categorical outputs only: which classes moved, and their shares across windows.
    top_changed: list[ClassShift] = []
    class_share_trend: list[Series] = []
    # Classifiers whose artifact reports per-row confidence (y_score).
    confidence: ConfidenceBlock | None = None
    # Classifiers whose artifact reports full probability vectors (y_proba).
    probabilities: ProbabilityBlock | None = None
    # Forecasting: each horizon vs its own baseline; the headline describes the worst horizon.
    horizons: list[HorizonDrift] = []
    alerts: list[AlertBanner] = []
    # End of the window the snapshot describes.
    computed_at: datetime | None = None
    # That window closed before the selected range began — the snapshot is a past reading.
    stale: bool = False


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
    profile_status: ProfileStatus = ProfileStatus.ABSENT
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
    profile_status: ProfileStatus = ProfileStatus.ABSENT
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
    profile_status: ProfileStatus = ProfileStatus.ABSENT
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
    profile_status: ProfileStatus = ProfileStatus.ABSENT
    trace: TraceDetail | None = None
