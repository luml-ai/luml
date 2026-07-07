from datetime import datetime
from enum import StrEnum
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


class DataQualityFeatureRow(BaseModel):
    feature: str
    missing_rate: float | None = None
    type_error_rate: float | None = None
    range_unseen_rate: float | None = None
    status: Severity = Severity.OK


class DataQualityResponse(BaseModel):
    state: SectionState
    profile_status: ProfileStatus = ProfileStatus.READY
    features: list[DataQualityFeatureRow] = []
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
