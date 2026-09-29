import math
from typing import Any

from luml_satellite.monitoring.compute import psi, thresholds
from luml_satellite.monitoring.compute.feature_drift import (
    _categorical_distribution,
    _numerical_distribution,
)
from luml_satellite.monitoring.compute.metric import Metric, MetricInput
from luml_satellite.monitoring.compute.models import (
    AlertSignal,
    DeploymentContext,
    InferenceEvent,
    MetricComputation,
    Severity,
    worst_severity,
)
from luml_satellite.monitoring.compute.runtime_health import quantile
from luml_satellite.monitoring.compute.thresholds import Threshold

DEFAULT_PSI = Threshold(warning=psi.PSI_WARNING, critical=psi.PSI_CRITICAL, warning_inclusive=True)

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
        self._profile = data.profile
        forecast = (data.profile or {}).get("forecast_summary") or {}
        if (data.profile or {}).get("task_type") == "forecasting" and forecast.get("horizons"):
            bounds = thresholds.resolve(data.profile, thresholds.PSI, DEFAULT_PSI)
            return self._forecast(forecast, data.events, bounds)
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
        self,
        summary: dict[str, Any],
        events: list[InferenceEvent],
        name: str | None,
        bounds: Threshold,
    ) -> MetricComputation:
        predictions = _numeric_outputs(events, name)
        if not predictions:
            return _EMPTY
        score = psi.numerical_psi(predictions, summary["bin_edges"], summary["probabilities"])
        values: dict[str, Any] = {
            "psi": score,
            "count": len(predictions),
            "name": name,
            "kind": "numeric",
            "trend": _trend(predictions),
            "distribution": _numerical_distribution(summary, predictions),
        }
        return _computation(score, values, bounds)

    def _categorical(
        self,
        summary: dict[str, Any],
        events: list[InferenceEvent],
        name: str | None,
        bounds: Threshold,
    ) -> MetricComputation:
        predictions = _categorical_outputs(events, name)
        if not predictions:
            return _EMPTY
        score = psi.categorical_psi(predictions, summary["probabilities"])
        values: dict[str, Any] = {
            "psi": score,
            "count": len(predictions),
            "name": name,
            "kind": "categorical",
            "distribution": _categorical_distribution(summary, predictions),
        }
        computation = _computation(score, values, bounds)
        signals = list(computation.signals)
        confidence = _confidence(self._confidence_reference(), events, bounds)
        if confidence is not None:
            block, signal = confidence
            values["confidence"] = block
            if signal is not None:
                signals.append(signal)
        probabilities = _probabilities(
            (self._profile or {}).get("probability_summary"), events, bounds
        )
        if probabilities is not None:
            block, signal = probabilities
            values["probabilities"] = block
            if signal is not None:
                signals.append(signal)
        severity = worst_severity(s.severity for s in signals)
        values["status"] = severity.value
        return MetricComputation(values=values, severity=severity, signals=signals)

    def _forecast(
        self, forecast: dict[str, Any], events: list[InferenceEvent], bounds: Threshold
    ) -> MetricComputation:
        """Per-horizon drift: each horizon of the forecast scored against its baseline.

        A forecast that holds for tomorrow can already be drifting a month out, so every
        horizon gets its own PSI; the headline and the alert ride on the worst one, and
        the materialized distribution is the worst horizon's — the one worth looking at.
        """
        horizons = [str(h) for h in forecast.get("horizons") or []]
        name = forecast.get("name") or "y"
        summaries = ((self._profile or {}).get("output_summaries") or {}).get(
            "numerical_outputs"
        ) or {}
        columns = _horizon_columns(events, name, len(horizons))

        per_horizon: list[dict[str, Any]] = []
        worst: tuple[int, float] | None = None
        for index, horizon in enumerate(horizons):
            summary = summaries.get(horizon) or {}
            values = columns[index]
            if not values or not psi.has_numerical_reference(summary):
                continue
            score = psi.numerical_psi(values, summary["bin_edges"], summary["probabilities"])
            per_horizon.append(
                {
                    "label": horizon,
                    "psi": score,
                    "mean": sum(values) / len(values),
                    "count": len(values),
                }
            )
            if worst is None or score > worst[1]:
                worst = (index, score)
        if not per_horizon or worst is None:
            return _EMPTY

        worst_index, worst_score = worst
        worst_label = horizons[worst_index]
        values_block: dict[str, Any] = {
            "psi": worst_score,
            "count": sum(entry["count"] for entry in per_horizon),
            "name": f"{name}[{worst_label}]",
            "kind": "forecast",
            "horizons": per_horizon,
            "distribution": _numerical_distribution(summaries[worst_label], columns[worst_index]),
        }
        signals: list[AlertSignal] = []
        evaluated = bounds.evaluate(worst_score)
        if evaluated is not None:
            severity, breached = evaluated
            signals.append(AlertSignal(f"horizon.{worst_label}", worst_score, breached, severity))
        computed = worst_severity(s.severity for s in signals)
        values_block["status"] = computed.value
        return MetricComputation(values=values_block, severity=computed, signals=signals)

    def _confidence_reference(self) -> dict[str, Any] | None:
        """The training-time confidence summary, when the profile carries one.

        Written by the SDK when the classifier exposes ``predict_proba``: a numerical
        summary of the per-row top class probability, under ``y_score``.
        """
        outputs = (self._profile or {}).get("output_summaries") or {}
        summary = (outputs.get("numerical_outputs") or {}).get(_CONFIDENCE_OUTPUT)
        if isinstance(summary, dict) and psi.has_numerical_reference(summary):
            return summary
        return None


def _computation(score: float, values: dict[str, Any], bounds: Threshold) -> MetricComputation:
    signals: list[AlertSignal] = []
    evaluated = bounds.evaluate(score)
    if evaluated is not None:
        severity, threshold = evaluated
        signals.append(AlertSignal("prediction", score, threshold, severity))
    computed = worst_severity(s.severity for s in signals)
    values["status"] = computed.value
    return MetricComputation(values=values, severity=computed, signals=signals)


# The forecast response is one output whose columns are the horizons.
def _horizon_columns(events: list[InferenceEvent], name: str, count: int) -> list[list[float]]:
    columns: list[list[float]] = [[] for _ in range(count)]
    for event in events:
        raw = event.output.get(name) if isinstance(event.output, dict) else event.output
        rows = raw if isinstance(raw, list) else [raw]
        for row in rows:
            if not isinstance(row, list) or len(row) != count:
                continue
            for index, value in enumerate(row):
                is_number = isinstance(value, int | float) and not isinstance(value, bool)
                if is_number and not math.isnan(value):
                    columns[index].append(float(value))
    return columns


def _proba_columns(events: list[InferenceEvent], count: int) -> list[list[float]]:
    return _horizon_columns(events, _PROBABILITY_OUTPUT, count)


_PROBABILITY_OUTPUT = "y_proba"


def _probabilities(
    reference: dict[str, Any] | None,
    events: list[InferenceEvent],
    bounds: Threshold,
) -> tuple[dict[str, Any], AlertSignal | None] | None:
    """Per-class probability drift, from the full vectors the artifact reports.

    Each class's live probability distribution is scored against its training baseline;
    the alert rides on the worst class. A binary task also compares how often live
    predictions sit in the decision boundary's coin-flip zone against the training rate.
    """
    if not reference:
        return None
    classes = reference.get("classes") or []
    per_class_ref = reference.get("per_class") or {}
    if not classes or not per_class_ref:
        return None
    columns = _proba_columns(events, len(classes))
    if not any(columns):
        return None

    per_class: list[dict[str, Any]] = []
    worst: tuple[str, float] | None = None
    for index, label in enumerate(classes):
        summary = per_class_ref.get(label) or {}
        values = columns[index]
        if not values or not psi.has_numerical_reference(summary):
            continue
        score = psi.numerical_psi(values, summary["bin_edges"], summary["probabilities"])
        per_class.append({"label": label, "psi": score, "mean": sum(values) / len(values)})
        if worst is None or score > worst[1]:
            worst = (label, score)
    if not per_class:
        return None
    per_class.sort(key=lambda entry: entry["psi"], reverse=True)

    block: dict[str, Any] = {"per_class": per_class}
    threshold = reference.get("decision_threshold")
    band = reference.get("threshold_band")
    if threshold is not None and band is not None and len(classes) == 2:
        positive = columns[1]
        if positive:
            near = sum(1 for value in positive if abs(value - threshold) < band)
            block["near_threshold"] = {
                "rate": near / len(positive),
                "reference_rate": reference.get("reference_near_threshold_rate"),
                "threshold": threshold,
                "positive_class": reference.get("positive_class"),
            }

    signal = None
    if worst is not None:
        evaluated = bounds.evaluate(worst[1])
        if evaluated is not None:
            severity, breached = evaluated
            signal = AlertSignal(f"probability.{worst[0]}", worst[1], breached, severity)
    return block, signal


_CONFIDENCE_OUTPUT = "y_score"


def _confidence(
    reference: dict[str, Any] | None,
    events: list[InferenceEvent],
    bounds: Threshold,
) -> tuple[dict[str, Any], AlertSignal | None] | None:
    """How sure the model is, against how sure it was on its training data.

    Confidence usually sags before the answers themselves go wrong, which makes this the
    early warning of the classification adapter. ``low_confidence_rate`` counts rows whose
    confidence is below the training q05 — worse than 95 percent of what training saw —
    so the threshold calibrates itself to the model instead of being a magic constant.
    """
    if reference is None:
        return None
    scores = _numeric_outputs(events, _CONFIDENCE_OUTPUT)
    if not scores:
        return None
    score_psi = psi.numerical_psi(scores, reference["bin_edges"], reference["probabilities"])
    threshold = (reference.get("quantiles") or {}).get("q05")
    low_rate = (
        sum(1 for value in scores if value < threshold) / len(scores)
        if threshold is not None
        else None
    )
    block: dict[str, Any] = {
        "psi": score_psi,
        "mean": sum(scores) / len(scores),
        "count": len(scores),
        "low_confidence_rate": low_rate,
        "low_confidence_threshold": threshold,
        "distribution": _numerical_distribution(reference, scores),
    }
    evaluated = bounds.evaluate(score_psi)
    signal = None
    if evaluated is not None:
        severity, breached = evaluated
        signal = AlertSignal("confidence", score_psi, breached, severity)
    return block, signal


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
