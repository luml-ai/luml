from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from luml_satellite.monitoring.compute.metric import MetricInput
from luml_satellite.monitoring.compute.models import (
    AlertSignal,
    AlertState,
    DeploymentContext,
    InferenceEvent,
    MetricComputation,
    MonitoredDeployment,
    Severity,
    TimeWindow,
)
from luml_satellite.monitoring.compute.output_drift import OutputDriftMetric
from luml_satellite.monitoring.compute.registry import default_registry
from luml_satellite.monitoring.compute.worker import MonitoringWorker
from luml_satellite.monitoring.storage.store import InMemoryMonitoringStore

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 1, 1, 12, 5, tzinfo=UTC)
WINDOW = TimeWindow(
    start=datetime(2026, 1, 1, 11, 55, tzinfo=UTC),
    end=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
)

NUM_OUT = {
    "type": "numerical",
    "summary": {"bin_edges": [0, 10, 20, 30, 40], "probabilities": [0.25] * 4},
}
CAT_OUT = {"type": "categorical", "summary": {"probabilities": {"cat": 0.5, "dog": 0.5}}}


def _profile(
    output_summary: dict[str, Any] | None, *, task_type: str = "regression"
) -> dict[str, Any]:
    profile: dict[str, Any] = {"task_type": task_type, "profile_status": "ready"}
    if output_summary is not None:
        profile["output_summary"] = output_summary
    return profile


def _event(output: Any) -> InferenceEvent:  # noqa: ANN401
    return InferenceEvent(
        event_id="e",
        deployment_id="dep",
        status="success",
        status_code=200,
        latency_ms=10.0,
        output=output,
    )


def _events(outputs: list[Any]) -> list[InferenceEvent]:
    return [_event(output) for output in outputs]


def _compute(events: list[InferenceEvent], profile: dict[str, Any]) -> MetricComputation:
    context = DeploymentContext("dep", profile=profile, has_events=bool(events))
    return OutputDriftMetric().compute(MetricInput(context=context, events=events, window=WINDOW))


def _signal(result: MetricComputation, key: str) -> AlertSignal:
    return next(signal for signal in result.signals if signal.key == key)


def _worker(
    store: InMemoryMonitoringStore, provider: Callable[[], list[MonitoredDeployment]]
) -> MonitoringWorker:
    return MonitoringWorker(
        store=store,
        registry=default_registry(),
        provider=provider,
        window_seconds=300.0,
        interval_seconds=60.0,
    )


CONFIDENCE_REF = {
    "bin_edges": [0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    "probabilities": [0.02, 0.03, 0.05, 0.2, 0.7],
    "quantiles": {"q05": 0.88},
}


def _confident_profile() -> dict[str, Any]:
    profile = _profile({**CAT_OUT, "name": "y"}, task_type="classification")
    profile["output_summaries"] = {"numerical_outputs": {"y_score": CONFIDENCE_REF}}
    return profile


def _scored_events(labels: list[str], scores: list[float]) -> list[InferenceEvent]:
    return _events(
        [{"y": [label], "y_score": [score]} for label, score in zip(labels, scores, strict=True)]
    )


PROBA_REF = {
    "name": "y_proba",
    "classes": ["cat", "dog"],
    "per_class": {
        "cat": {"bin_edges": [0.0, 0.25, 0.5, 0.75, 1.0], "probabilities": [0.4, 0.1, 0.1, 0.4]},
        "dog": {"bin_edges": [0.0, 0.25, 0.5, 0.75, 1.0], "probabilities": [0.4, 0.1, 0.1, 0.4]},
    },
    "positive_class": "dog",
    "decision_threshold": 0.5,
    "threshold_band": 0.05,
    "reference_near_threshold_rate": 0.02,
}


def _proba_events(rows: list[list[float]]) -> list[InferenceEvent]:
    return _events([{"y": ["dog" if row[1] >= 0.5 else "cat"], "y_proba": [row]} for row in rows])


def _proba_profile() -> dict[str, Any]:
    profile = _profile({**CAT_OUT, "name": "y"}, task_type="classification")
    profile["probability_summary"] = PROBA_REF
    return profile


FORECAST_PROFILE: dict[str, Any] = {
    "profile_status": "ready",
    "task_type": "forecasting",
    "forecast_summary": {"name": "y", "horizons": ["h1", "h7"]},
    "output_summary": {"name": "h1", "type": "numerical", "summary": {}},
    "output_summaries": {
        "numerical_outputs": {
            "h1": {"bin_edges": [0, 10, 20, 30, 40], "probabilities": [0.25] * 4},
            "h7": {"bin_edges": [0, 10, 20, 30, 40], "probabilities": [0.25] * 4},
        }
    },
}


class TestMonitoringOutputDrift:
    def test_applies_requires_events_output_summary_and_task_type(self) -> None:
        metric = OutputDriftMetric()
        ready = _profile(NUM_OUT)

        assert metric.applies(DeploymentContext("dep", profile=ready, has_events=True))
        assert not metric.applies(DeploymentContext("dep", profile=ready, has_events=False))
        assert not metric.applies(DeploymentContext("dep", profile=None, has_events=True))
        no_task = {"profile_status": "ready", "output_summary": NUM_OUT}
        assert not metric.applies(DeploymentContext("dep", profile=no_task, has_events=True))

    def test_stable_regression_predictions_normal_with_trend(self) -> None:
        outputs = ([5] * 25) + ([15] * 25) + ([25] * 25) + ([35] * 25)

        result = _compute(_events(outputs), _profile(NUM_OUT))

        assert result.severity == Severity.NORMAL
        assert result.signals == []
        assert result.values["psi"] == pytest.approx(0.0, abs=1e-9)
        assert result.values["trend"] == {"mean": 20.0, "median": 20.0, "p05": 5.0, "p95": 35.0}

    def test_shifted_regression_predictions_raise_critical_with_trend(self) -> None:
        result = _compute(_events([5.0] * 100), _profile(NUM_OUT))

        assert result.values["psi"] > 0.25
        assert result.severity == Severity.CRITICAL
        signal = _signal(result, "prediction")
        assert (signal.severity, signal.threshold) == (Severity.CRITICAL, 0.25)
        assert result.values["trend"]["mean"] == 5.0

    def test_stable_classification_predictions_normal(self) -> None:
        outputs = (["cat"] * 50) + (["dog"] * 50)

        result = _compute(_events(outputs), _profile(CAT_OUT, task_type="classification"))

        assert result.severity == Severity.NORMAL
        assert result.values["psi"] == pytest.approx(0.0, abs=1e-9)

    def test_shifted_classification_predictions_raise_critical(self) -> None:
        result = _compute(_events(["cat"] * 100), _profile(CAT_OUT, task_type="classification"))

        assert result.values["psi"] > 0.25
        assert _signal(result, "prediction").severity == Severity.CRITICAL

    def test_no_numeric_predictions_produces_no_signal(self) -> None:
        result = _compute(_events([None, "oops"]), _profile(NUM_OUT))

        assert result.values == {}
        assert result.signals == []

    async def test_worker_materializes_output_drift_and_opens_alert(self) -> None:
        store = InMemoryMonitoringStore()
        profile = _profile(NUM_OUT)
        store.add_events("dep", _events([5.0] * 100))
        worker = _worker(store, lambda: [MonitoredDeployment("dep", profile=profile)])

        await worker.tick(now=NOW)

        result = next(r for r in store.results if r.metric == "output_drift")
        assert result.severity == Severity.CRITICAL
        assert result.values["psi"] > 0.25
        assert "trend" in result.values

        alerts = {alert.metric for alert in await store.active_alerts("dep")}
        assert "output_drift:prediction" in alerts

    async def test_worker_output_drift_alert_resolves_when_data_recovers(self) -> None:
        store = InMemoryMonitoringStore()
        profile = _profile(NUM_OUT)
        store.events["dep"] = _events([5.0] * 100)
        worker = _worker(store, lambda: [MonitoredDeployment("dep", profile=profile)])

        await worker.tick(now=NOW)
        assert "output_drift:prediction" in {a.metric for a in await store.active_alerts("dep")}

        store.events["dep"] = _events(([5.0] * 25) + ([15.0] * 25) + ([25.0] * 25) + ([35.0] * 25))
        await worker.tick(now=LATER)

        assert "output_drift:prediction" not in {a.metric for a in await store.active_alerts("dep")}
        assert store.alerts[("dep", "output_drift:prediction")].state == AlertState.RESOLVED

    async def test_worker_skips_output_drift_without_output_summary(self) -> None:
        store = InMemoryMonitoringStore()
        store.add_events("dep", _events([5.0] * 10))
        worker = _worker(store, lambda: [MonitoredDeployment("dep", profile=_profile(None))])

        await worker.tick(now=NOW)

        groups = {result.metric for result in store.results}
        assert "runtime" in groups
        assert "output_drift" not in groups

    def test_prediction_is_unwrapped_from_the_response_body_by_name(self) -> None:
        """The agent records the model's whole response, not the bare prediction: the model
        server answers ``{"y": [value]}``. Scoring that envelope as-is found nothing numeric
        and output drift silently stayed empty on every real deployment."""
        summary = {**NUM_OUT, "name": "y"}
        values = [5] * 25 + [15] * 25 + [25] * 25 + [35] * 25
        outputs = [{"y": [value], "decision": ["assisted"]} for value in values]

        result = _compute(_events(outputs), _profile(summary))

        assert result.values["count"] == 100
        assert result.values["psi"] == pytest.approx(0.0, abs=1e-9)
        assert result.severity == Severity.NORMAL

    def test_batched_response_contributes_every_prediction(self) -> None:
        summary = {**NUM_OUT, "name": "y"}
        outputs = [{"y": [5, 15, 25, 35]}] * 25

        result = _compute(_events(outputs), _profile(summary))

        assert result.values["count"] == 100
        assert result.values["psi"] == pytest.approx(0.0, abs=1e-9)

    def test_single_output_response_needs_no_name(self) -> None:
        result = _compute(_events([{"prediction": 5.0}] * 100), _profile(NUM_OUT))

        assert result.values["count"] == 100
        assert result.severity == Severity.CRITICAL

    def test_ambiguous_response_without_a_matching_name_is_not_guessed_at(self) -> None:
        summary = {**NUM_OUT, "name": "y"}
        outputs = [{"score": 5.0, "confidence": 0.9}] * 100

        result = _compute(_events(outputs), _profile(summary))

        assert result.values == {}
        assert result.severity == Severity.NORMAL

    def test_classification_predictions_are_unwrapped_too(self) -> None:
        summary = {**CAT_OUT, "name": "label"}
        outputs = [{"label": [value]} for value in (["cat"] * 50 + ["dog"] * 50)]

        result = _compute(_events(outputs), _profile(summary, task_type="classification"))

        assert result.values["count"] == 100
        assert result.values["psi"] == pytest.approx(0.0, abs=1e-9)

    def test_bare_scalar_output_still_scores(self) -> None:
        result = _compute(_events([5] * 25 + [15] * 25 + [25] * 25 + [35] * 25), _profile(NUM_OUT))

        assert result.values["count"] == 100
        assert result.values["psi"] == pytest.approx(0.0, abs=1e-9)

    def test_numerical_window_carries_the_distribution_and_identity(self) -> None:
        """The two halves the PSI compares ride in the window, same shape as feature drift."""
        summary = {**NUM_OUT, "name": "y_pred"}
        outputs = [{"y_pred": [5.0]}, {"y_pred": [15.0]}, {"y_pred": [25.0]}]

        result = _compute(_events(outputs), _profile(summary))

        assert result.values["name"] == "y_pred"
        assert result.values["kind"] == "numeric"
        assert result.values["status"] in ("normal", "warning", "critical")
        distribution = result.values["distribution"]
        assert distribution["kind"] == "numeric"
        shares = [entry["current"] for entry in distribution["bins"]]
        assert sum(shares) == pytest.approx(1.0)
        assert all("reference" in entry and "label" in entry for entry in distribution["bins"])

    def test_categorical_window_carries_the_distribution_with_unseen_classes(self) -> None:
        summary = {**CAT_OUT, "name": "decision"}
        outputs = [{"decision": ["approve"]}] * 3 + [{"decision": ["escalate"]}]

        result = _compute(_events(outputs), _profile(summary))

        assert result.values["kind"] == "categorical"
        labels = [entry["label"] for entry in result.values["distribution"]["bins"]]
        # a class the reference never saw still shows up, with reference share zero
        assert "escalate" in labels
        escalate = next(
            entry for entry in result.values["distribution"]["bins"] if entry["label"] == "escalate"
        )
        assert escalate["reference"] == 0.0
        assert escalate["current"] == pytest.approx(0.25)

    def test_confident_predictions_keep_the_confidence_block_quiet(self) -> None:
        """Scores shaped like the training data's: PSI small, low-confidence share small."""
        # mirror the reference proportions across the bins: 2/3/5/20/70 out of 100
        scores = [0.55] * 2 + [0.65] * 3 + [0.75] * 5 + [0.85] * 20 + [0.95] * 70
        events = _scored_events(["cat", "dog"] * 50, scores)

        result = _compute(events, _confident_profile())

        confidence = result.values["confidence"]
        assert confidence["psi"] < 0.1
        # exactly the rows below the training q05 of 0.88
        assert confidence["low_confidence_rate"] == pytest.approx(0.3)
        assert confidence["low_confidence_threshold"] == 0.88
        assert confidence["distribution"]["kind"] == "numeric"
        assert not any(s.key == "confidence" for s in result.signals)

    def test_sagging_confidence_raises_its_own_signal(self) -> None:
        """The model still answers the same classes, but it is guessing now."""
        events = _scored_events(["cat", "dog"] * 10, [0.55, 0.52] * 10)

        result = _compute(events, _confident_profile())

        confidence = result.values["confidence"]
        assert confidence["psi"] > 0.25
        # every row is below the training q05: worse than 95% of what training saw
        assert confidence["low_confidence_rate"] == 1.0
        signal = next(s for s in result.signals if s.key == "confidence")
        assert signal.severity is Severity.CRITICAL
        assert result.severity is Severity.CRITICAL

    def test_a_profile_without_a_confidence_reference_changes_nothing(self) -> None:
        """Old artifacts and regressions: the block simply is not there."""
        events = _scored_events(["cat", "dog"], [0.9, 0.9])
        profile = _profile({**CAT_OUT, "name": "y"}, task_type="classification")

        result = _compute(events, profile)

        assert "confidence" not in result.values

    def test_events_without_scores_leave_the_block_out(self) -> None:
        """A new profile serving events from before the redeploy: labels only."""
        events = _events([{"y": ["cat"]}, {"y": ["dog"]}])

        result = _compute(events, _confident_profile())

        assert "confidence" not in result.values
        assert result.values["psi"] is not None  # labels still scored

    def test_per_class_probability_drift_names_the_worst_class(self) -> None:
        # every dog probability crowds 0.5–0.75 while the reference lived at the extremes
        rows = [[0.4, 0.6]] * 20
        result = _compute(_proba_events(rows), _proba_profile())

        block = result.values["probabilities"]
        assert [entry["label"] for entry in block["per_class"]][0] in ("cat", "dog")
        assert all(entry["psi"] > 0.25 for entry in block["per_class"])
        signal = next(s for s in result.signals if s.key.startswith("probability."))
        assert signal.severity is Severity.CRITICAL

    def test_the_coin_flip_zone_is_measured_against_training(self) -> None:
        """Predictions huddling at the decision boundary are decisions in name only."""
        rows = [[0.48, 0.52]] * 10 + [[0.1, 0.9]] * 10
        result = _compute(_proba_events(rows), _proba_profile())

        near = result.values["probabilities"]["near_threshold"]
        assert near["rate"] == pytest.approx(0.5)
        assert near["reference_rate"] == pytest.approx(0.02)
        assert near["threshold"] == 0.5
        assert near["positive_class"] == "dog"

    def test_label_only_events_leave_probabilities_out(self) -> None:
        result = _compute(_events([{"y": ["cat"]}, {"y": ["dog"]}]), _proba_profile())

        assert "probabilities" not in result.values

    def test_forecasting_scores_every_horizon_and_leads_with_the_worst(self) -> None:
        """h1 stays на месте, h7 уехал: заголовок и алерт — про h7."""
        rows = [[5.0, 35.0], [15.0, 36.0], [25.0, 38.0], [35.0, 39.0]] * 5
        events = _events([{"y": [row]} for row in rows])

        result = _compute(events, FORECAST_PROFILE)

        assert result.values["kind"] == "forecast"
        horizons = {entry["label"]: entry["psi"] for entry in result.values["horizons"]}
        assert horizons["h1"] < 0.1  # spread like the reference
        assert horizons["h7"] > 0.25  # crowded into one bin
        assert result.values["name"] == "y[h7]"
        assert result.values["psi"] == pytest.approx(horizons["h7"])
        signal = next(s for s in result.signals if s.key == "horizon.h7")
        assert signal.severity is Severity.CRITICAL
        assert result.values["distribution"]["kind"] == "numeric"

    def test_a_forecast_without_usable_columns_is_empty(self) -> None:
        events = _events([{"y": ["not-a-number"]}])

        result = _compute(events, FORECAST_PROFILE)

        assert result.values == {}
