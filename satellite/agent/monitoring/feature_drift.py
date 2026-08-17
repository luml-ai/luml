import math
from typing import Any

from agent.monitoring import psi, thresholds
from agent.monitoring.metric import Metric, MetricInput
from agent.monitoring.models import (
    AlertSignal,
    DeploymentContext,
    InferenceEvent,
    MetricComputation,
    Severity,
    worst_severity,
)
from agent.monitoring.thresholds import Threshold

# The spec puts PSI 0.1 itself in the warning band, hence the inclusive bound.
DEFAULT_PSI = Threshold(
    warning=psi.PSI_WARNING, critical=psi.PSI_CRITICAL, warning_inclusive=True
)


class FeatureDriftMetric(Metric):
    """Univariate PSI per input feature against its reference distribution.

    Numerical features are binned with the reference ``bin_edges`` and scored against
    the reference bin ``probabilities``; categorical features are scored against the
    reference category ``probabilities`` (unseen categories inflate the score). Requires
    the profile's per-feature summaries; a feature without a usable reference
    distribution, or with no valid live values this window, is skipped.
    """

    metric = "feature_drift"

    def applies(self, context: DeploymentContext) -> bool:
        return context.has_events and context.has_feature_summaries

    def compute(self, data: MetricInput) -> MetricComputation:
        summaries = (data.profile or {}).get("feature_summaries") or {}
        numerical = summaries.get("numerical_features") or {}
        categorical = summaries.get("categorical_features") or {}

        # PSI bounds are a property of the deployment: the profile's rule wins when it
        # has one, the spec default stands in otherwise.
        bounds = thresholds.resolve(data.profile, thresholds.PSI, DEFAULT_PSI)
        features: dict[str, dict[str, Any]] = {}
        signals: list[AlertSignal] = []

        for name, summary in numerical.items():
            if not psi.has_numerical_reference(summary):
                continue
            values = _numeric_inputs(data.events, name)
            if not values:
                continue
            score = psi.numerical_psi(values, summary["bin_edges"], summary["probabilities"])
            self._record(
                name,
                score,
                len(values),
                features,
                signals,
                bounds,
                distribution=_numerical_distribution(summary, values),
            )

        for name, summary in categorical.items():
            if not psi.has_categorical_reference(summary):
                continue
            values = _categorical_inputs(data.events, name)
            if not values:
                continue
            score = psi.categorical_psi(values, summary["probabilities"])
            self._record(
                name,
                score,
                len(values),
                features,
                signals,
                bounds,
                distribution=_categorical_distribution(summary, values),
            )

        severity = worst_severity(signal.severity for signal in signals)
        return MetricComputation(values={"features": features}, severity=severity, signals=signals)

    @staticmethod
    def _record(
        feature: str,
        score: float,
        count: int,
        features: dict[str, dict[str, Any]],
        signals: list[AlertSignal],
        bounds: Threshold,
        *,
        distribution: dict[str, Any] | None = None,
    ) -> None:
        evaluated = bounds.evaluate(score)
        status = evaluated[0] if evaluated is not None else Severity.NORMAL
        features[feature] = {
            "psi": score,
            "count": count,
            "status": status.value,
            # The two halves the PSI score compares, kept so the dashboard can draw them
            # side by side instead of only showing the number they collapse into.
            "distribution": distribution,
        }
        if evaluated is not None:
            severity, threshold = evaluated
            signals.append(AlertSignal(feature, score, threshold, severity))


def _numerical_distribution(summary: dict, values: list[float]) -> dict[str, Any]:
    """Reference vs live share per reference bin, labelled by the bin's range."""
    edges = summary["bin_edges"]
    reference = summary["probabilities"]
    current = psi.numerical_proportions(values, edges)
    bins = [
        {
            "label": f"{_short(edges[i])}–{_short(edges[i + 1])}",
            "reference": reference[i],
            "current": current[i],
        }
        for i in range(len(reference))
    ]
    return {"kind": "numeric", "bins": bins}


def _categorical_distribution(summary: dict, values: list[str]) -> dict[str, Any]:
    """Reference vs live share per category, including categories only seen live."""
    reference: dict[str, float] = summary["probabilities"]
    unseen = sorted({value for value in values if value not in reference})
    categories = list(reference) + unseen
    current = psi.categorical_proportions(values, categories)
    bins = [
        {
            "label": category,
            "reference": reference.get(category, 0.0),
            "current": current[index],
        }
        for index, category in enumerate(categories)
    ]
    return {"kind": "categorical", "bins": bins}


def _short(value: float) -> str:
    """Bin edge trimmed to something that fits an axis label."""
    if value == int(value) and abs(value) < 1e6:
        return str(int(value))
    return f"{value:.3g}"


def _iter_values(raw: Any) -> list[Any]:  # noqa: ANN401
    """One event may carry a batch of observations per feature; a scalar is a batch of one."""
    return raw if isinstance(raw, list) else [raw]


def _numeric_inputs(events: list[InferenceEvent], name: str) -> list[float]:
    values: list[float] = []
    for event in events:
        raw = event.inputs.get(name) if event.inputs else None
        for value in _iter_values(raw):
            if isinstance(value, bool) or not isinstance(value, int | float):
                continue
            if not math.isnan(value):
                values.append(float(value))
    return values


def _categorical_inputs(events: list[InferenceEvent], name: str) -> list[str]:
    values: list[str] = []
    for event in events:
        raw = event.inputs.get(name) if event.inputs else None
        for value in _iter_values(raw):
            if isinstance(value, str):
                values.append(value)
    return values
