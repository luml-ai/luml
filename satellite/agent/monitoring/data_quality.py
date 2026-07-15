import math
from dataclasses import dataclass
from typing import Any

from agent.monitoring.metric import Metric, MetricInput
from agent.monitoring.models import (
    AlertSignal,
    DeploymentContext,
    InferenceEvent,
    MetricComputation,
    Severity,
    worst_severity,
)


@dataclass(frozen=True)
class QualityThreshold:
    """Warning / critical bounds for a data-quality rate (breached when strictly above)."""

    warning: float
    critical: float

    def evaluate(self, rate: float) -> tuple[Severity, float] | None:
        if rate > self.critical:
            return Severity.CRITICAL, self.critical
        if rate > self.warning:
            return Severity.WARNING, self.warning
        return None


# Defaults from the spec: missing/range 1%/5%, type-mismatch/unseen-category 0%/1%.
DEFAULT_THRESHOLDS: dict[str, QualityThreshold] = {
    "missing": QualityThreshold(warning=0.01, critical=0.05),
    "type_mismatch": QualityThreshold(warning=0.0, critical=0.01),
    "range_violation": QualityThreshold(warning=0.01, critical=0.05),
    "unseen_category": QualityThreshold(warning=0.0, critical=0.01),
}


class DataQualityMetric(Metric):
    """Per-feature input health: missing, type-mismatch, range-violation, unseen-category.

    Requires the profile's per-feature summaries, which define each feature's kind
    (numerical vs categorical) and its reference ``min``/``max`` or ``categories``.
    Every rate is measured over all events in the window: a missing observation counts
    only toward the missing rate, a wrong-typed one only toward type-mismatch, and range
    or unseen checks apply only to present, correctly-typed values.
    """

    metric = "data_quality"

    def __init__(self, *, thresholds: dict[str, QualityThreshold] | None = None) -> None:
        self._thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    def applies(self, context: DeploymentContext) -> bool:
        return context.has_events and context.has_feature_summaries

    def compute(self, data: MetricInput) -> MetricComputation:
        summaries = (data.profile or {}).get("feature_summaries") or {}
        numerical = summaries.get("numerical_features") or {}
        categorical = summaries.get("categorical_features") or {}

        features: dict[str, dict[str, Any]] = {}
        signals: list[AlertSignal] = []

        for name, summary in numerical.items():
            checks, total = self._numerical_checks(name, summary, data.events)
            feature_signals = self._signals(name, checks)
            features[name] = _feature_values(total, checks, feature_signals)
            signals.extend(feature_signals)

        for name, summary in categorical.items():
            checks, total = self._categorical_checks(name, summary, data.events)
            feature_signals = self._signals(name, checks)
            features[name] = _feature_values(total, checks, feature_signals)
            signals.extend(feature_signals)

        severity = worst_severity(signal.severity for signal in signals)
        return MetricComputation(values={"features": features}, severity=severity, signals=signals)

    def _numerical_checks(
        self, name: str, summary: dict[str, Any], events: list[InferenceEvent]
    ) -> tuple[dict[str, float], int]:
        ref_min = summary.get("min")
        ref_max = summary.get("max")
        missing = type_mismatch = range_violation = total = 0
        for event in events:
            for value in _observations(event, name):
                total += 1
                if _is_missing(value):
                    missing += 1
                elif not _is_number(value):
                    type_mismatch += 1
                elif (ref_min is not None and value < ref_min) or (
                    ref_max is not None and value > ref_max
                ):
                    range_violation += 1
        checks = {
            "missing": _rate(missing, total),
            "type_mismatch": _rate(type_mismatch, total),
            "range_violation": _rate(range_violation, total),
        }
        return checks, total

    def _categorical_checks(
        self, name: str, summary: dict[str, Any], events: list[InferenceEvent]
    ) -> tuple[dict[str, float], int]:
        categories = set(summary.get("categories") or [])
        missing = type_mismatch = unseen = total = 0
        for event in events:
            for value in _observations(event, name):
                total += 1
                if _is_missing(value):
                    missing += 1
                elif not isinstance(value, str):
                    type_mismatch += 1
                elif value not in categories:
                    unseen += 1
        checks = {
            "missing": _rate(missing, total),
            "type_mismatch": _rate(type_mismatch, total),
            "unseen_category": _rate(unseen, total),
        }
        return checks, total

    def _signals(self, feature: str, checks: dict[str, float]) -> list[AlertSignal]:
        signals: list[AlertSignal] = []
        for check, rate in checks.items():
            evaluated = self._thresholds[check].evaluate(rate)
            if evaluated is None:
                continue
            severity, breached = evaluated
            signals.append(AlertSignal(f"{feature}.{check}", rate, breached, severity))
        return signals


def _feature_values(
    total: int, checks: dict[str, float], signals: list[AlertSignal]
) -> dict[str, Any]:
    status = worst_severity(signal.severity for signal in signals)
    return {
        "count": total,
        "status": status.value,
        **{f"{check}_rate": rate for check, rate in checks.items()},
    }


def _live_value(event: InferenceEvent, name: str) -> Any:  # noqa: ANN401
    return event.inputs.get(name) if event.inputs else None


def _observations(event: InferenceEvent, name: str) -> list[Any]:
    """Per-observation values for a feature; one event may carry a batch (scalar => one)."""
    raw = _live_value(event, name)
    return raw if isinstance(raw, list) else [raw]


def _is_missing(value: Any) -> bool:  # noqa: ANN401
    return value is None or (isinstance(value, float) and math.isnan(value))


def _is_number(value: Any) -> bool:  # noqa: ANN401
    return isinstance(value, int | float) and not isinstance(value, bool)


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0
