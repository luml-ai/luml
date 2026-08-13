import math
from typing import Any

from agent.monitoring import psi
from agent.monitoring.metric import Metric, MetricInput
from agent.monitoring.models import (
    AlertSignal,
    DeploymentContext,
    InferenceEvent,
    MetricComputation,
    Severity,
    worst_severity,
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

        features: dict[str, dict[str, Any]] = {}
        signals: list[AlertSignal] = []

        for name, summary in numerical.items():
            if not psi.has_numerical_reference(summary):
                continue
            values = _numeric_inputs(data.events, name)
            if not values:
                continue
            score = psi.numerical_psi(values, summary["bin_edges"], summary["probabilities"])
            self._record(name, score, len(values), features, signals)

        for name, summary in categorical.items():
            if not psi.has_categorical_reference(summary):
                continue
            values = _categorical_inputs(data.events, name)
            if not values:
                continue
            score = psi.categorical_psi(values, summary["probabilities"])
            self._record(name, score, len(values), features, signals)

        severity = worst_severity(signal.severity for signal in signals)
        return MetricComputation(values={"features": features}, severity=severity, signals=signals)

    @staticmethod
    def _record(
        feature: str,
        score: float,
        count: int,
        features: dict[str, dict[str, Any]],
        signals: list[AlertSignal],
    ) -> None:
        evaluated = psi.psi_severity(score)
        status = evaluated[0] if evaluated is not None else Severity.NORMAL
        features[feature] = {"psi": score, "count": count, "status": status.value}
        if evaluated is not None:
            severity, threshold = evaluated
            signals.append(AlertSignal(feature, score, threshold, severity))


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
