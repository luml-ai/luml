from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

_SUCCESS_STATUSES = frozenset({"success", "ok", "succeeded", "completed"})
_ERROR_STATUSES = frozenset({"error", "failed", "failure"})
_FAILED_INFERENCE_STATUSES = frozenset({"failed", "failure"})


class Severity(StrEnum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertState(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


_SEVERITY_RANK: dict[Severity, int] = {
    Severity.NORMAL: 0,
    Severity.WARNING: 1,
    Severity.CRITICAL: 2,
}


def worst_severity(severities: Iterable[Severity]) -> Severity:
    """Return the highest-ranked severity, or ``NORMAL`` when there are none."""
    return max(severities, key=_SEVERITY_RANK.__getitem__, default=Severity.NORMAL)


@dataclass(frozen=True)
class TimeWindow:
    start: datetime
    end: datetime

    def contains(self, timestamp: datetime | None) -> bool:
        if timestamp is None:
            return True
        return self.start <= timestamp < self.end


@dataclass(frozen=True)
class InferenceEvent:
    """One collected inference request, parsed from the ``inference_events`` table."""

    event_id: str
    deployment_id: str
    status: str
    status_code: int | None = None
    latency_ms: float | None = None
    inputs: dict[str, Any] | None = None
    output: Any = None
    timestamp: datetime | None = None

    def _normalized_status(self) -> str:
        return (self.status or "").strip().lower()

    @property
    def is_success(self) -> bool:
        status = self._normalized_status()
        if status in _SUCCESS_STATUSES:
            return True
        if status in _ERROR_STATUSES:
            return False
        if self.status_code is not None:
            return 200 <= self.status_code < 400
        return False

    @property
    def is_error(self) -> bool:
        return not self.is_success

    @property
    def is_failed_inference(self) -> bool:
        """Whether the inference itself did not complete (vs. a client-side 4xx)."""
        status = self._normalized_status()
        if status in _FAILED_INFERENCE_STATUSES:
            return True
        if status in _SUCCESS_STATUSES:
            return False
        return self.status_code is not None and self.status_code >= 500


@dataclass(frozen=True)
class DeploymentContext:
    """What a deployment offers a metric this window: its profile parts and data."""

    deployment_id: str
    profile: dict | None
    has_events: bool

    @property
    def has_profile(self) -> bool:
        return self.profile is not None

    @property
    def task_type(self) -> str | None:
        return self.profile.get("task_type") if self.profile else None

    @property
    def has_feature_summaries(self) -> bool:
        summaries = (self.profile or {}).get("feature_summaries") or {}
        return bool(summaries.get("numerical_features") or summaries.get("categorical_features"))

    @property
    def has_output_summary(self) -> bool:
        return bool((self.profile or {}).get("output_summary"))

    @property
    def has_pca_profile(self) -> bool:
        return bool((self.profile or {}).get("pca_profile"))


@dataclass(frozen=True)
class AlertSignal:
    """A threshold breach a metric raises for the window; reconciled into an alert."""

    key: str
    current_value: float
    threshold: float
    severity: Severity


@dataclass(frozen=True)
class MetricComputation:
    """The output of a metric for one window: values, a severity, and any breaches."""

    values: dict[str, Any]
    severity: Severity
    signals: list[AlertSignal]


@dataclass(frozen=True)
class MetricResult:
    deployment_id: str
    metric: str
    window_start: datetime
    window_end: datetime
    values: dict[str, Any]
    severity: Severity
    profile_status: str


@dataclass
class Alert:
    deployment_id: str
    metric: str
    current_value: float
    threshold: float
    severity: Severity
    state: AlertState
    first_seen: datetime
    last_seen: datetime


@dataclass(frozen=True)
class MonitoredDeployment:
    deployment_id: str
    profile: dict | None = None
