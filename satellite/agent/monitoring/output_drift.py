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
from agent.monitoring.runtime_health import quantile
from agent.monitoring.thresholds import Threshold

# The spec puts PSI 0.1 itself in the warning band, hence the inclusive bound.
DEFAULT_PSI = Threshold(
    warning=psi.PSI_WARNING, critical=psi.PSI_CRITICAL, warning_inclusive=True
)

_EMPTY = MetricComputation(values={}, severity=Severity.NORMAL, signals=[])


class OutputDriftMetric(Metric):
    """PSI on live predictions against the reference output summary.

    A numerical output summary (regression) scores the predicted values with the same
    binning as feature drift and adds a mean/median/p05/p95 trend of the live
    predictions; a categorical output summary (classification) scores the predicted-class
    proportions. Requires the output summary and a task type.

    The recorded output is the model's response body, so the monitored prediction is
    addressed by the ``name`` the profile's output summary carries (``y``, ``y_pred``, …)
    and unwrapped from the response envelope before scoring.
    """

    metric = "output_drift"

    def applies(self, context: DeploymentContext) -> bool:
        return context.has_events and context.has_output_summary and context.task_type is not None

    def compute(self, data: MetricInput) -> MetricComputation:
        output_summary = (data.profile or {}).get("output_summary") or {}
        summary = output_summary.get("summary") or {}
        summary_type = output_summary.get("type")
        name = output_summary.get("name")

        bounds = thresholds.resolve(data.profile, thresholds.PSI, DEFAULT_PSI)
        if summary_type == "numerical" and psi.has_numerical_reference(summary):
            return self._numerical(summary, data.events, name, bounds)
        if summary_type == "categorical" and psi.has_categorical_reference(summary):
            return self._categorical(summary, data.events, name, bounds)
        return _EMPTY

    def _numerical(
        self, summary: dict, events: list[InferenceEvent], name: str | None, bounds: Threshold
    ) -> MetricComputation:
        predictions = _numeric_outputs(events, name)
        if not predictions:
            return _EMPTY
        score = psi.numerical_psi(predictions, summary["bin_edges"], summary["probabilities"])
        values: dict[str, Any] = {
            "psi": score,
            "count": len(predictions),
            "trend": _trend(predictions),
        }
        return _computation(score, values, bounds)

    def _categorical(
        self, summary: dict, events: list[InferenceEvent], name: str | None, bounds: Threshold
    ) -> MetricComputation:
        predictions = _categorical_outputs(events, name)
        if not predictions:
            return _EMPTY
        score = psi.categorical_psi(predictions, summary["probabilities"])
        return _computation(score, {"psi": score, "count": len(predictions)}, bounds)


def _computation(score: float, values: dict[str, Any], bounds: Threshold) -> MetricComputation:
    signals: list[AlertSignal] = []
    evaluated = bounds.evaluate(score)
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


def _numeric_outputs(events: list[InferenceEvent], name: str | None) -> list[float]:
    values: list[float] = []
    for event in events:
        for value in _predictions(event.output, name):
            if isinstance(value, bool) or not isinstance(value, int | float):
                continue
            if not math.isnan(value):
                values.append(float(value))
    return values


def _categorical_outputs(events: list[InferenceEvent], name: str | None) -> list[str]:
    return [
        value
        for event in events
        for value in _predictions(event.output, name)
        if isinstance(value, str)
    ]


def _predictions(output: Any, name: str | None) -> list[Any]:  # noqa: ANN401
    """The monitored prediction(s) of one event, unwrapped from the response body.

    The model server answers with ``{output_name: [prediction, ...]}``, so the named
    output is selected and its batch flattened; a single-output response is unambiguous
    and used whatever it is named. Anything else (several outputs, none matching the
    profile) is left alone rather than guessed at. A bare scalar or list — what a
    hand-written store or an older event carries — passes straight through.
    """
    if isinstance(output, dict):
        if name is not None and name in output:
            return _flatten(output[name])
        if len(output) == 1:
            return _flatten(next(iter(output.values())))
        return []
    return _flatten(output)


def _flatten(value: Any) -> list[Any]:  # noqa: ANN401
    if isinstance(value, list):
        return [item for element in value for item in _flatten(element)]
    return [value]
