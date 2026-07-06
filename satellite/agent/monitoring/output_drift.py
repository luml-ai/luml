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
from agent.monitoring.runtime_health import quantile

_EMPTY = MetricComputation(values={}, severity=Severity.NORMAL, signals=[])


class OutputDriftMetric(Metric):
    """PSI on live predictions against the reference output summary.

    A numerical output summary (regression) scores the predicted values with the same
    binning as feature drift and adds a mean/median/p05/p95 trend of the live
    predictions; a categorical output summary (classification) scores the predicted-class
    proportions. Requires the output summary and a task type.
    """

    metric = "output_drift"

    def applies(self, context: DeploymentContext) -> bool:
        return context.has_events and context.has_output_summary and context.task_type is not None

    def compute(self, data: MetricInput) -> MetricComputation:
        output_summary = (data.profile or {}).get("output_summary") or {}
        summary = output_summary.get("summary") or {}
        summary_type = output_summary.get("type")

        if summary_type == "numerical" and psi.has_numerical_reference(summary):
            return self._numerical(summary, data.events)
        if summary_type == "categorical" and psi.has_categorical_reference(summary):
            return self._categorical(summary, data.events)
        return _EMPTY

    def _numerical(self, summary: dict, events: list[InferenceEvent]) -> MetricComputation:
        predictions = _numeric_outputs(events)
        if not predictions:
            return _EMPTY
        score = psi.numerical_psi(predictions, summary["bin_edges"], summary["probabilities"])
        values: dict[str, Any] = {
            "psi": score,
            "count": len(predictions),
            "trend": _trend(predictions),
        }
        return _computation(score, values)

    def _categorical(self, summary: dict, events: list[InferenceEvent]) -> MetricComputation:
        predictions = _categorical_outputs(events)
        if not predictions:
            return _EMPTY
        score = psi.categorical_psi(predictions, summary["probabilities"])
        return _computation(score, {"psi": score, "count": len(predictions)})


def _computation(score: float, values: dict[str, Any]) -> MetricComputation:
    signals: list[AlertSignal] = []
    evaluated = psi.psi_severity(score)
    if evaluated is not None:
        severity, threshold = evaluated
        signals.append(AlertSignal("prediction", score, threshold, severity))
    return MetricComputation(
        values=values, severity=worst_severity(s.severity for s in signals), signals=signals
    )


def _trend(predictions: list[float]) -> dict[str, float]:
    ordered = sorted(predictions)
    return {
        "mean": sum(ordered) / len(ordered),
        "median": quantile(ordered, 0.50),
        "p05": quantile(ordered, 0.05),
        "p95": quantile(ordered, 0.95),
    }


def _numeric_outputs(events: list[InferenceEvent]) -> list[float]:
    values: list[float] = []
    for event in events:
        value = event.output
        if isinstance(value, bool) or not isinstance(value, int | float):
            continue
        if not math.isnan(value):
            values.append(float(value))
    return values


def _categorical_outputs(events: list[InferenceEvent]) -> list[str]:
    return [event.output for event in events if isinstance(event.output, str)]
