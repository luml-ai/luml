import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from opentelemetry.sdk.trace.export import SpanExporter

from luml_demo import monitoring


class StubTraffic:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def sample(self, *, drift: float, quality_issues: bool) -> tuple[dict[str, Any], str | None]:
        self.calls.append(drift)
        return {"x": [1.0]}, ("type" if quality_issues and len(self.calls) % 50 == 0 else None)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {"y": [1], "y_score": [0.9], "y_proba": [[0.1, 0.9]]}


def test_fill_envelope_replaces_named_outputs_at_depth() -> None:
    template = {"outputs": {"y": [0], "y_score": [0.1], "y_proba": [[0.9, 0.1]]}, "event_id": "e1"}
    filled = monitoring.fill_envelope(template, {"y": [1], "y_score": [0.8], "y_proba": [[0.2, 0.8]]})
    assert filled == {"outputs": {"y": [1], "y_score": [0.8], "y_proba": [[0.2, 0.8]]}, "event_id": "e1"}


def test_history_covers_the_window_with_drift_and_incident() -> None:
    now = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    plan = monitoring.HistoryPlan(hours=6, base_per_hour=120, base_latency_ms=30,
                                  drift_onset_hours_ago=2, quality_issue_hours=1, incident_hours_ago=3)
    traffic = StubTraffic()
    events = list(monitoring.generate_history(traffic, plan, now=now, envelope={"y": None}, seed=1))
    assert 400 < len(events) < 1200
    assert all(now - timedelta(hours=6) <= e.at < now for e in events)
    assert events == sorted(events, key=lambda e: e.at)
    drifted = [d for d in traffic.calls if d > 0]
    assert drifted and max(drifted) == 1.0
    incident_start = now - timedelta(hours=3)
    incident = [e for e in events if incident_start <= e.at <= incident_start + timedelta(minutes=12)]
    assert sum(e.status == "error" for e in incident) / len(incident) > 0.15
    assert any(e.status_code == 400 for e in events)
    successes = [e for e in events if e.status == "success"]
    assert successes[0].output == {"y": [1]}


def test_history_is_deterministic_for_a_seed() -> None:
    now = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    plan = monitoring.CANDIDATE_PLAN
    first = [e.at for e in monitoring.generate_history(StubTraffic(), plan, now=now, envelope={}, seed=5)]
    second = [e.at for e in monitoring.generate_history(StubTraffic(), plan, now=now, envelope={}, seed=5)]
    assert first == second


class CapturingExporter(SpanExporter):
    def __init__(self) -> None:
        self.spans: list[Any] = []

    def export(self, spans: Any) -> Any:
        self.spans.extend(spans)
        from opentelemetry.sdk.trace.export import SpanExportResult

        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


def test_export_events_emits_agent_shaped_spans(monkeypatch: pytest.MonkeyPatch) -> None:
    exporter = CapturingExporter()
    monkeypatch.setattr(monitoring, "OTLPSpanExporter", lambda **_: exporter)
    at = datetime(2026, 10, 1, 11, 0, tzinfo=UTC)
    events = iter([
        monitoring.HistoryEvent(at, {"x": [1]}, {"y": [1]}, "success", 200, 12.5),
        monitoring.HistoryEvent(at + timedelta(seconds=5), {"x": [2]}, None, "error", 502, 40.0, "timeout"),
    ])
    assert monitoring.export_events("dep-1", 4317, events) == 2
    first, second = exporter.spans
    assert first.name == "inference_event"
    assert first.resource.attributes["service.name"] == "satellite-agent.events"
    assert first.attributes["inference.deployment_id"] == "dep-1"
    assert first.start_time == int(at.timestamp() * 1_000_000_000)
    assert first.end_time == first.start_time + 12_500_000
    recorded_inputs = json.loads(first.attributes["inference.inputs"])
    assert recorded_inputs == {"inputs": {"x": [1]}, "dynamic_attributes": {}}
    assert json.loads(first.attributes["inference.output"]) == {"y": [1]}
    assert second.attributes["inference.status"] == "error"
    assert second.attributes["inference.error"] == "timeout"
    assert "inference.output" not in second.attributes


def test_aligned_window_end_snaps_to_five_minutes() -> None:
    moment = datetime(2026, 10, 1, 11, 7, 30, tzinfo=UTC)
    assert monitoring.aligned_window_end(moment) == datetime(2026, 10, 1, 11, 5, tzinfo=UTC)


def test_churn_traffic_samples_match_the_bundle_input_shape() -> None:
    pytest.importorskip("sklearn")
    scenario_csv = Path(__file__).resolve().parents[3] / (
        "prisma/src/luml_prisma/demo/scenarios/churn/repo/data/customers.csv"
    )
    traffic = monitoring.ChurnTraffic.__new__(monitoring.ChurnTraffic)
    import random

    import pandas as pd

    traffic.frame = pd.read_csv(scenario_csv)[monitoring.CHURN_FEATURES]
    traffic.rng = random.Random(1)
    clean, problem = traffic.sample(drift=0.0, quality_issues=False)
    assert problem is None
    assert set(clean) == set(monitoring.CHURN_FEATURES)
    assert all(len(values) == 1 for values in clean.values())
    problems = {traffic.sample(drift=1.0, quality_issues=True)[1] for _ in range(400)}
    assert {"missing", "range", "unseen", "type"} <= problems
