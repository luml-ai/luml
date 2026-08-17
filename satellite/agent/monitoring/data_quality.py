import math
from collections import Counter
from typing import Any

from agent.monitoring import thresholds
from agent.monitoring.metric import Metric, MetricInput
from agent.monitoring.models import (
    AlertSignal,
    DeploymentContext,
    InferenceEvent,
    MetricComputation,
    worst_severity,
)
from agent.monitoring.thresholds import Threshold

# How much evidence the detail panel gets: enough to name the culprits, small enough to
# store in every window's payload.
EXAMPLE_LIMIT = 3
UNSEEN_LIMIT = 5


class InvalidValues:
    """Aggregates *what* was wrong with the rejected values, not just how many.

    The rates answer "is the input broken"; this answers "broken how" — which categories
    arrived unseen, how far past the reference bounds the numbers went, what types came
    instead of the expected one.
    """

    def __init__(
        self,
        *,
        reference_min: float | None = None,
        reference_max: float | None = None,
        reference_categories: int | None = None,
    ) -> None:
        self._reference_min = reference_min
        self._reference_max = reference_max
        self._reference_categories = reference_categories
        self.missing = 0
        self.type_mismatch = 0
        self.range_violation = 0
        self.unseen_category = 0
        self._types: Counter[str] = Counter()
        self._examples: list[str] = []
        self._values: Counter[str] = Counter()
        self._below_min = 0
        self._above_max = 0
        self._observed_min: float | None = None
        self._observed_max: float | None = None

    def missing_value(self) -> None:
        self.missing += 1

    def wrong_type(self, value: Any) -> None:  # noqa: ANN401
        self.type_mismatch += 1
        self._types[type(value).__name__] += 1
        example = repr(value)
        if len(self._examples) < EXAMPLE_LIMIT and example not in self._examples:
            self._examples.append(example)

    def out_of_range(self, value: float, *, below: bool) -> None:
        self.range_violation += 1
        if below:
            self._below_min += 1
        else:
            self._above_max += 1
        self._observed_min = value if self._observed_min is None else min(self._observed_min, value)
        self._observed_max = value if self._observed_max is None else max(self._observed_max, value)

    def unseen(self, value: str) -> None:
        self.unseen_category += 1
        self._values[value] += 1

    def payload(self) -> dict[str, Any] | None:
        """The evidence as stored in the window, or None when nothing was wrong."""
        detail: dict[str, Any] = {}
        if self.missing:
            detail["missing"] = {"count": self.missing}
        if self.type_mismatch:
            detail["type_mismatch"] = {
                "count": self.type_mismatch,
                "types": dict(self._types.most_common()),
                "examples": list(self._examples),
            }
        if self.range_violation:
            detail["range_violation"] = {
                "count": self.range_violation,
                "below_min": self._below_min,
                "above_max": self._above_max,
                "observed_min": self._observed_min,
                "observed_max": self._observed_max,
                "reference_min": self._reference_min,
                "reference_max": self._reference_max,
            }
        if self.unseen_category:
            detail["unseen_category"] = {
                "count": self.unseen_category,
                "distinct": len(self._values),
                "reference_categories": self._reference_categories,
                "values": [
                    {"value": value, "count": count}
                    for value, count in self._values.most_common(UNSEEN_LIMIT)
                ],
            }
        return detail or None


# Defaults from the spec: missing/range 1%/5%, type-mismatch/unseen-category 0%/1%.
DEFAULT_THRESHOLDS: dict[str, Threshold] = {
    "missing": Threshold(warning=0.01, critical=0.05),
    "type_mismatch": Threshold(warning=0.0, critical=0.01),
    "range_violation": Threshold(warning=0.01, critical=0.05),
    "unseen_category": Threshold(warning=0.0, critical=0.01),
}

# The profile names its rules after the rate they bound.
_PROFILE_KEYS = {check: f"{check}_rate" for check in DEFAULT_THRESHOLDS}


class DataQualityMetric(Metric):
    """Per-feature input health: missing, type-mismatch, range-violation, unseen-category.

    Requires the profile's per-feature summaries, which define each feature's kind
    (numerical vs categorical) and its reference ``min``/``max`` or ``categories``.
    Every rate is measured over all events in the window: a missing observation counts
    only toward the missing rate, a wrong-typed one only toward type-mismatch, and range
    or unseen checks apply only to present, correctly-typed values.
    """

    metric = "data_quality"

    def __init__(self, *, thresholds: dict[str, Threshold] | None = None) -> None:
        self._thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    def _resolved(self, profile: dict[str, Any] | None) -> dict[str, Threshold]:
        """This deployment's bounds: its profile's rules over the metric's own."""
        return {
            check: thresholds.resolve(profile, _PROFILE_KEYS[check], default)
            for check, default in self._thresholds.items()
        }

    def applies(self, context: DeploymentContext) -> bool:
        return context.has_events and context.has_feature_summaries

    def compute(self, data: MetricInput) -> MetricComputation:
        summaries = (data.profile or {}).get("feature_summaries") or {}
        numerical = summaries.get("numerical_features") or {}
        categorical = summaries.get("categorical_features") or {}

        bounds = self._resolved(data.profile)
        features: dict[str, dict[str, Any]] = {}
        signals: list[AlertSignal] = []

        for name, summary in numerical.items():
            checks, total, invalid = self._numerical_checks(name, summary, data.events)
            feature_signals = self._signals(name, checks, bounds)
            features[name] = _feature_values(total, checks, feature_signals, "numeric", invalid)
            signals.extend(feature_signals)

        for name, summary in categorical.items():
            checks, total, invalid = self._categorical_checks(name, summary, data.events)
            feature_signals = self._signals(name, checks, bounds)
            features[name] = _feature_values(total, checks, feature_signals, "categorical", invalid)
            signals.extend(feature_signals)

        severity = worst_severity(signal.severity for signal in signals)
        return MetricComputation(values={"features": features}, severity=severity, signals=signals)

    def _numerical_checks(
        self, name: str, summary: dict[str, Any], events: list[InferenceEvent]
    ) -> tuple[dict[str, float], int, InvalidValues]:
        ref_min = summary.get("min")
        ref_max = summary.get("max")
        invalid = InvalidValues(reference_min=ref_min, reference_max=ref_max)
        total = 0
        for event in events:
            for value in _observations(event, name):
                total += 1
                if _is_missing(value):
                    invalid.missing_value()
                elif not _is_number(value):
                    invalid.wrong_type(value)
                elif ref_min is not None and value < ref_min:
                    invalid.out_of_range(value, below=True)
                elif ref_max is not None and value > ref_max:
                    invalid.out_of_range(value, below=False)
        checks = {
            "missing": _rate(invalid.missing, total),
            "type_mismatch": _rate(invalid.type_mismatch, total),
            "range_violation": _rate(invalid.range_violation, total),
        }
        return checks, total, invalid

    def _categorical_checks(
        self, name: str, summary: dict[str, Any], events: list[InferenceEvent]
    ) -> tuple[dict[str, float], int, InvalidValues]:
        categories = set(summary.get("categories") or [])
        invalid = InvalidValues(reference_categories=len(categories))
        total = 0
        for event in events:
            for value in _observations(event, name):
                total += 1
                if _is_missing(value):
                    invalid.missing_value()
                elif not isinstance(value, str):
                    invalid.wrong_type(value)
                elif value not in categories:
                    invalid.unseen(value)
        checks = {
            "missing": _rate(invalid.missing, total),
            "type_mismatch": _rate(invalid.type_mismatch, total),
            "unseen_category": _rate(invalid.unseen_category, total),
        }
        return checks, total, invalid

    def _signals(
        self, feature: str, checks: dict[str, float], bounds: dict[str, Threshold]
    ) -> list[AlertSignal]:
        signals: list[AlertSignal] = []
        for check, rate in checks.items():
            evaluated = bounds[check].evaluate(rate)
            if evaluated is None:
                continue
            severity, breached = evaluated
            signals.append(AlertSignal(f"{feature}.{check}", rate, breached, severity))
        return signals


def _feature_values(
    total: int,
    checks: dict[str, float],
    signals: list[AlertSignal],
    kind: str,
    invalid: InvalidValues,
) -> dict[str, Any]:
    status = worst_severity(signal.severity for signal in signals)
    values: dict[str, Any] = {
        "kind": kind,
        "count": total,
        "status": status.value,
        **{f"{check}_rate": rate for check, rate in checks.items()},
    }
    evidence = invalid.payload()
    if evidence is not None:
        values["invalid"] = evidence
    return values


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
