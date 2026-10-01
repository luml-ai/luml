"""Inference traffic for the demo deployments: backdated history and live requests.

History is written through the satellite's own pipeline: inference events are
exported as OTLP spans with past timestamps to the stack's collector, exactly as
the agent emits them, and the monitoring worker materializes the windows.
"""

from __future__ import annotations

import contextlib
import json
import math
import random
import sys
import tarfile
import tempfile
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

import cloudpickle
import httpx
import pandas as pd
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from luml_demo.shell import say, wait_for

EVENTS_SERVICE = "satellite-agent.events"
SEED_METRIC = "luml-demo-seed"
WINDOW_SECONDS = 300

CHURN_FEATURES = [
    "plan", "billing_cycle", "region", "tenure_months", "seats", "monthly_spend",
    "events_per_day_k", "dashboards_created", "api_calls_30d", "support_tickets_90d",
    "nps_score", "integrations_count",
]
PARAPHRASES = [
    "{q}", "{q}", "Quick question: {q}", "Hi! {q}", "{q} Thanks!", "Customer asks: {q}",
    "{q} (urgent)", "Could you help: {q}",
]


class Traffic(Protocol):
    def sample(self, *, drift: float, quality_issues: bool) -> tuple[dict[str, Any], str | None]: ...

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class HistoryEvent:
    at: datetime
    inputs: dict[str, Any]
    output: Any
    status: str
    status_code: int
    latency_ms: float
    error: str | None = None


class ArtifactRuntime:
    """Runs a packaged model locally so history carries the real model's outputs."""

    def __init__(self, artifact_path: Path) -> None:
        self._dir = tempfile.TemporaryDirectory()
        root = Path(self._dir.name)
        with tarfile.open(artifact_path) as tar:
            tar.extractall(root, filter="data")
        modules = root / "variant_artifacts" / "extra_modules"
        if modules.is_dir() and str(modules) not in sys.path:
            sys.path.insert(0, str(modules))
        self.files = root / "variant_artifacts" / "extra_files"
        self.extra_values = self._manifest_extra_values(root)

    @staticmethod
    def _manifest_extra_values(root: Path) -> dict[str, Any]:
        manifest = json.loads((root / "manifest.json").read_text())
        values = manifest.get("extra_values") or {}
        return dict(values) if isinstance(values, dict) else {}

    def estimator(self) -> Any:
        with (self.files / "estimator.pkl").open("rb") as handle:
            return cloudpickle.load(handle)

    def graph(self) -> Any:
        with (self.files / "graph_creator_callable.pkl").open("rb") as handle:
            return cloudpickle.load(handle)()


class ChurnTraffic:
    def __init__(self, csv_path: Path, artifact_path: Path, seed: int = 7) -> None:
        self.frame = pd.read_csv(csv_path)[CHURN_FEATURES]
        self.rng = random.Random(seed)
        self.estimator = ArtifactRuntime(artifact_path).estimator()

    def sample(self, *, drift: float, quality_issues: bool) -> tuple[dict[str, Any], str | None]:
        """One request body's inputs; returns (inputs, data quality problem or None)."""
        row = self.frame.iloc[self.rng.randrange(len(self.frame))].to_dict()
        row = {key: (value.item() if hasattr(value, "item") else value) for key, value in row.items()}
        if drift > 0:
            if self.rng.random() < 0.55 * drift:
                row["plan"] = "starter"
                row["billing_cycle"] = "monthly"
            row["tenure_months"] = max(1, int(row["tenure_months"] * (1 - 0.55 * drift)))
            row["support_tickets_90d"] = int(row["support_tickets_90d"]) + self._poisson(1.6 * drift)
            row["nps_score"] = max(0, int(row["nps_score"]) - round(2.5 * drift))
            if self.rng.random() < 0.2 * drift:
                row["region"] = "apac"
            row["events_per_day_k"] = round(float(row["events_per_day_k"]) * (1 - 0.3 * drift), 1)
        problem: str | None = None
        if quality_issues:
            roll = self.rng.random()
            if roll < 0.04:
                row["nps_score"] = None
                problem = "missing"
            elif roll < 0.06:
                row["seats"] = 0
                problem = "range"
            elif roll < 0.08:
                row["plan"] = "trial"
                problem = "unseen"
            elif roll < 0.09:
                row["monthly_spend"] = "n/a"
                problem = "type"
        return {name: [row[name]] for name in CHURN_FEATURES}, problem

    def _poisson(self, lam: float) -> int:
        if lam <= 0:
            return 0
        threshold, count, product = math.exp(-lam), 0, self.rng.random()
        while product > threshold:
            count += 1
            product *= self.rng.random()
        return count

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        frame = pd.DataFrame(dict(inputs))
        frame = frame.astype(self.frame.dtypes.to_dict())
        proba = self.estimator.predict_proba(frame)
        labels = self.estimator.predict(frame)
        return {
            "y": [int(v) for v in labels],
            "y_score": [round(float(max(p)), 6) for p in proba],
            "y_proba": [[round(float(v), 6) for v in p] for p in proba],
        }


class AssistantTraffic:
    def __init__(self, eval_path: Path, artifact_path: Path, seed: int = 11) -> None:
        self.questions = [q["question"] for q in json.loads(eval_path.read_text())["questions"]]
        self.rng = random.Random(seed)
        self.graph = ArtifactRuntime(artifact_path).graph()
        self._cache: dict[str, dict[str, Any]] = {}

    def sample(self, *, drift: float, quality_issues: bool) -> tuple[dict[str, Any], str | None]:
        question = self.rng.choice(self.questions)
        template = self.rng.choice(PARAPHRASES)
        if quality_issues and self.rng.random() < 0.03:
            return {"payload": {"graph_input": {"question": ""}}}, "type"
        return {"payload": {"graph_input": {"question": template.format(q=question)}}}, None

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        question = str(inputs["payload"]["graph_input"]["question"])
        if question not in self._cache:
            state = self.graph.invoke({"question": question})
            self._cache[question] = {"result": _jsonable(state), "interrupts": None}
        return {"graph_output": self._cache[question]}


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, bool | int | float | str) or value is None:
        return value
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def fill_envelope(template: Any, values: dict[str, Any]) -> Any:
    """Replace, at any depth of a recorded response, the values of the given output names."""
    if isinstance(template, dict):
        return {
            key: values[key] if key in values else fill_envelope(child, values)
            for key, child in template.items()
        }
    if isinstance(template, list):
        return [fill_envelope(child, values) for child in template]
    return template


@dataclass(frozen=True)
class HistoryPlan:
    hours: int
    base_per_hour: float
    base_latency_ms: float
    drift_onset_hours_ago: float
    quality_issue_hours: float
    incident_hours_ago: float
    incident_minutes: float = 12.0


CHURN_PLAN = HistoryPlan(hours=24, base_per_hour=60, base_latency_ms=38, drift_onset_hours_ago=6,
                         quality_issue_hours=2.5, incident_hours_ago=3)
ASSISTANT_PLAN = HistoryPlan(hours=24, base_per_hour=45, base_latency_ms=140,
                             drift_onset_hours_ago=0, quality_issue_hours=1.5, incident_hours_ago=9)
CANDIDATE_PLAN = HistoryPlan(hours=6, base_per_hour=25, base_latency_ms=42, drift_onset_hours_ago=0,
                             quality_issue_hours=0, incident_hours_ago=0)


def _diurnal(at: datetime) -> float:
    hour = at.hour + at.minute / 60
    return 0.45 + 0.55 * (1 + math.cos((hour - 14) / 24 * 2 * math.pi)) / 2


def generate_history(
    traffic: Traffic,
    plan: HistoryPlan,
    *,
    now: datetime,
    envelope: Any,
    seed: int = 3,
) -> Iterator[HistoryEvent]:
    rng = random.Random(seed)
    start = now - timedelta(hours=plan.hours)
    at = start
    drift_onset = now - timedelta(hours=plan.drift_onset_hours_ago) if plan.drift_onset_hours_ago else None
    incident_start = now - timedelta(hours=plan.incident_hours_ago) if plan.incident_hours_ago else None
    incident_end = incident_start + timedelta(minutes=plan.incident_minutes) if incident_start else None
    quality_from = now - timedelta(hours=plan.quality_issue_hours) if plan.quality_issue_hours else None
    while at < now - timedelta(seconds=90):
        rate = plan.base_per_hour * _diurnal(at)
        at = at + timedelta(seconds=rng.expovariate(rate / 3600))
        if at >= now - timedelta(seconds=90):
            break
        drift = 0.0
        if drift_onset and at >= drift_onset:
            drift = min(1.0, (at - drift_onset).total_seconds() / 7200 + 0.15)
        quality = bool(quality_from and at >= quality_from)
        inputs, problem = traffic.sample(drift=drift, quality_issues=quality)
        in_incident = bool(incident_start and incident_end and incident_start <= at <= incident_end)
        latency = rng.lognormvariate(math.log(plan.base_latency_ms), 0.35) * (4.0 if in_incident else 1.0)
        if problem == "type":
            yield HistoryEvent(at, inputs, None, "error", 400, latency,
                               "Input validation failed: monthly_spend expects a number")
            continue
        if in_incident and rng.random() < 0.35:
            yield HistoryEvent(at, inputs, None, "error", 502, latency * 3, "upstream timeout")
            continue
        if rng.random() < 0.004:
            yield HistoryEvent(at, inputs, None, "error", 500, latency, "model worker restarted")
            continue
        try:
            prediction = traffic.predict(inputs)
        except Exception as error:  # noqa: BLE001 — bad inputs become error events, as in production
            yield HistoryEvent(at, inputs, None, "error", 500, latency, str(error)[:200])
            continue
        yield HistoryEvent(at, inputs, fill_envelope(envelope, prediction), "success", 200, latency)


def export_events(deployment_id: str, otlp_port: int, events: Iterator[HistoryEvent]) -> int:
    provider = TracerProvider(resource=Resource.create({"service.name": EVENTS_SERVICE}))
    exporter = OTLPSpanExporter(endpoint=f"localhost:{otlp_port}", insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter, max_export_batch_size=256))
    tracer = provider.get_tracer("inference.events")
    count = 0
    for event in events:
        start_ns = int(event.at.timestamp() * 1_000_000_000)
        attributes: dict[str, Any] = {
            "inference.event_id": str(uuid.uuid4()),
            "inference.deployment_id": deployment_id,
            "inference.status": event.status,
            "inference.latency_ms": round(event.latency_ms, 3),
            "inference.timestamp": event.at.isoformat(),
            "inference.bodies_sampled": True,
            "inference.status_code": event.status_code,
            "inference.inputs": json.dumps({"inputs": event.inputs, "dynamic_attributes": {}}),
            "inference.trace_id": uuid.uuid4().hex,
            "inference.span_id": uuid.uuid4().hex[:16],
        }
        if event.output is not None:
            attributes["inference.output"] = json.dumps(event.output)
        if event.error is not None:
            attributes["inference.error"] = event.error
        span = tracer.start_span("inference_event", attributes=attributes, start_time=start_ns)
        span.end(end_time=start_ns + int(event.latency_ms * 1_000_000))
        count += 1
    provider.force_flush()
    provider.shutdown()
    return count


class Greptime:
    def __init__(self, port: int) -> None:
        self.url = f"http://localhost:{port}/v1/sql"

    def sql(self, statement: str) -> list[list[Any]]:
        response = httpx.post(self.url, params={"db": "public"}, data={"sql": statement}, timeout=60)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code", 0) != 0:
            raise RuntimeError(f"GreptimeDB error: {payload.get('error', payload)}")
        for item in payload.get("output", []):
            records = item.get("records")
            if records:
                return list(records.get("rows", []))
        return []

    def scalar(self, statement: str) -> Any:
        rows = self.sql(statement)
        return rows[0][0] if rows and rows[0] else None

    def events_count(self, deployment_id: str) -> int:
        try:
            value = self.scalar(
                "SELECT count(*) FROM inference_events WHERE "
                f"json_get_string(span_attributes, '$.\"inference.deployment_id\"') = '{deployment_id}'"
            )
        except (RuntimeError, httpx.HTTPError):
            return 0
        return int(value or 0)

    def results_count(self, deployment_id: str) -> int:
        try:
            value = self.scalar(
                f"SELECT count(*) FROM monitoring_results WHERE deployment_id = '{deployment_id}'"
            )
        except (RuntimeError, httpx.HTTPError):
            return 0
        return int(value or 0)

    def clear_results(self, deployment_id: str) -> None:
        for table in ("monitoring_results", "monitoring_alerts", "monitoring_worker_failures"):
            with contextlib.suppress(RuntimeError, httpx.HTTPError):
                self.sql(f"DELETE FROM {table} WHERE deployment_id = '{deployment_id}'")

    def seed_window(self, deployment_id: str, window_end: datetime) -> None:
        window_start = window_end - timedelta(seconds=WINDOW_SECONDS)
        self.sql(
            "INSERT INTO monitoring_results (deployment_id, metric, window_start, window_end, "
            "metric_values, severity, profile_status) VALUES ("
            f"'{deployment_id}', '{SEED_METRIC}', '{window_start.isoformat()}', "
            f"'{window_end.isoformat()}', '{{}}', 'ok', 'absent')"
        )

    def remove_seed(self, deployment_id: str) -> None:
        self.sql(
            f"DELETE FROM monitoring_results WHERE deployment_id = '{deployment_id}' "
            f"AND metric = '{SEED_METRIC}'"
        )


def aligned_window_end(moment: datetime) -> datetime:
    boundary = math.floor(moment.timestamp() / WINDOW_SECONDS) * WINDOW_SECONDS
    return datetime.fromtimestamp(boundary, UTC)


def probe_envelope(inference_url: str, api_key: str, inputs: dict[str, Any]) -> Any:
    response = httpx.post(
        inference_url, json={"inputs": inputs}, headers={"Authorization": f"Bearer {api_key}"},
        timeout=120,
    )
    if response.status_code != 200:
        raise RuntimeError(f"probe request failed: {response.status_code} {response.text[:300]}")
    return response.json()


def backfill(
    *,
    deployment_id: str,
    traffic: Traffic,
    plan: HistoryPlan,
    otlp_port: int,
    greptime_port: int,
    envelope: Any,
    now: datetime | None = None,
) -> int:
    moment = now or datetime.now(UTC)
    store = Greptime(greptime_port)
    say(f"exporting {plan.hours}h of history for deployment {deployment_id}")
    exported = export_events(
        deployment_id, otlp_port, generate_history(traffic, plan, now=moment, envelope=envelope),
    )
    wait_for(
        "the collector to land the events in GreptimeDB",
        lambda: store.events_count(deployment_id) >= exported,
        timeout=180, interval=3,
    )
    store.clear_results(deployment_id)
    seed_end = aligned_window_end(moment - timedelta(hours=plan.hours))
    store.seed_window(deployment_id, seed_end)
    last_seen = [0, time.monotonic()]

    def materialized() -> bool:
        # The worker materializes every pending window inside one tick; the row count
        # grows while it works and goes quiet once the history is complete.
        count = store.results_count(deployment_id)
        if count != last_seen[0]:
            last_seen[0], last_seen[1] = count, time.monotonic()
        return count > 1 and time.monotonic() - last_seen[1] > 45

    wait_for("the monitoring worker to materialize the history", materialized, timeout=900, interval=5)
    store.remove_seed(deployment_id)
    say(f"history ready: {exported} events, {store.results_count(deployment_id)} result rows")
    return exported


def send_live(
    inference_url: str,
    api_key: str,
    traffic: Traffic,
    *,
    minutes: float,
    per_minute: float,
    drift: bool,
) -> dict[str, int]:
    rng = random.Random()
    deadline = time.monotonic() + minutes * 60
    counts = {"success": 0, "error": 0}
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=120) as client:
        while time.monotonic() < deadline:
            inputs, _ = traffic.sample(drift=1.0 if drift else 0.0, quality_issues=drift)
            try:
                response = client.post(inference_url, json={"inputs": inputs}, headers=headers)
                counts["success" if response.status_code == 200 else "error"] += 1
            except httpx.HTTPError as error:
                counts["error"] += 1
                say(f"request failed: {error}")
            total = counts["success"] + counts["error"]
            if total % 20 == 0:
                say(f"sent {total} requests ({counts['error']} errors)")
            time.sleep(rng.expovariate(per_minute / 60))
    return counts
