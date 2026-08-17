"""The worker reports on itself: an empty tab and a broken metric must look different."""

import uuid
from datetime import UTC, datetime

from agent.monitoring import MonitoringQueryService, QueryDimensions
from agent.monitoring.health import WorkerHealth
from agent.monitoring.metric import Metric, MetricInput
from agent.monitoring.models import (
    DeploymentContext,
    InferenceEvent,
    MetricComputation,
    MonitoredDeployment,
    Severity,
)
from agent.monitoring.query_store import InMemoryMonitoringStore
from agent.monitoring.registry import MetricRegistry
from agent.monitoring.store import InMemoryMonitoringStore as WorkerStore
from agent.monitoring.worker import MonitoringWorker
from agent.schemas.monitoring_query import SectionState

NOW = datetime(2026, 1, 1, 12, 0, 30, tzinfo=UTC)


class _ExplodingMetric(Metric):
    metric = "exploding"

    def applies(self, context: DeploymentContext) -> bool:
        return True

    def compute(self, data: MetricInput) -> MetricComputation:
        raise RuntimeError("bin edges are missing")


class _QuietMetric(Metric):
    metric = "quiet"

    def applies(self, context: DeploymentContext) -> bool:
        return True

    def compute(self, data: MetricInput) -> MetricComputation:
        return MetricComputation(values={"ok": 1}, severity=Severity.NORMAL, signals=[])


def _event() -> InferenceEvent:
    return InferenceEvent(
        event_id="e", deployment_id="dep", status="success", status_code=200, latency_ms=5.0
    )


def _worker(health: WorkerHealth, *metrics: Metric) -> MonitoringWorker:
    store = WorkerStore()
    store.add_events("dep", [_event()])
    registry = MetricRegistry()
    for metric in metrics:
        registry.register(metric)
    return MonitoringWorker(
        store=store,
        registry=registry,
        provider=lambda: [MonitoredDeployment("dep", profile={})],
        window_seconds=300.0,
        interval_seconds=60.0,
        health=health,
        clock=lambda: NOW,
    )


async def test_a_healthy_tick_records_what_it_did() -> None:
    health = WorkerHealth()

    await _worker(health, _QuietMetric()).tick(now=NOW)

    assert health.ticks == 1
    assert health.last_tick_at == NOW
    state = health.for_deployment("dep")
    assert state.windows_processed == 1
    assert state.last_window_end == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    # the window closed at 12:00 and was materialized at 12:00:30
    assert state.last_lag_seconds == 30.0
    assert state.failures == ()


async def test_a_failing_metric_is_remembered_not_just_logged() -> None:
    health = WorkerHealth()

    await _worker(health, _ExplodingMetric(), _QuietMetric()).tick(now=NOW)

    state = health.for_deployment("dep")
    # the other metric still ran
    assert state.windows_processed == 1
    assert [f.metric for f in state.failures] == ["exploding"]
    assert "bin edges" in state.failures[0].error


async def test_a_metric_that_recovers_clears_its_failure() -> None:
    health = WorkerHealth()
    await _worker(health, _ExplodingMetric()).tick(now=NOW)
    assert health.for_deployment("dep").failures

    # same metric name, this time it works
    class _Fixed(_QuietMetric):
        metric = "exploding"

    await _worker(health, _Fixed()).tick(now=NOW)

    assert health.for_deployment("dep").failures == ()


async def test_the_dashboard_can_read_the_workers_state() -> None:
    health = WorkerHealth()
    await _worker(health, _ExplodingMetric()).tick(now=NOW)
    dep = uuid.uuid4()

    service = MonitoringQueryService(
        InMemoryMonitoringStore(),
        health_source=lambda _: (health.snapshot("dep"), (300.0, 60.0)),
    )
    result = await service.worker_health(dep)

    assert result.state is SectionState.OK
    assert result.windows_processed == 1
    assert result.last_lag_seconds == 30.0
    assert result.window_seconds == 300.0
    assert [f.metric for f in result.failures] == ["exploding"]


async def test_without_a_worker_the_section_is_unavailable() -> None:
    service = MonitoringQueryService(InMemoryMonitoringStore())

    result = await service.worker_health(uuid.uuid4())

    assert result.state is SectionState.UNAVAILABLE


async def test_dimensions_are_not_needed_to_ask_about_the_worker() -> None:
    """Worker health is about the process, not about a time window."""
    health = WorkerHealth()
    service = MonitoringQueryService(
        InMemoryMonitoringStore(),
        health_source=lambda _: (health.snapshot("dep"), (300.0, 60.0)),
    )

    result = await service.worker_health(uuid.uuid4())

    assert result.running is False
    assert QueryDimensions is not None  # the endpoint takes no dimensions at all


async def test_failure_history_survives_the_process() -> None:
    """In-memory counters die with the worker; the incident list is what outlives it."""

    health = WorkerHealth()
    worker = _worker(health, _ExplodingMetric())
    await worker.tick(now=NOW)

    store: WorkerStore = worker._store
    written = store.transitions["dep"]
    assert [(t.metric, t.kind) for t in written] == [("exploding", "failed")]
    assert "bin edges" in written[0].error


async def test_only_transitions_are_written_not_every_tick() -> None:
    """A metric broken all day must cost two rows, not one per minute."""

    health = WorkerHealth()
    worker = _worker(health, _ExplodingMetric())
    await worker.tick(now=NOW)
    await worker.tick(now=NOW)
    await worker.tick(now=NOW)

    store: WorkerStore = worker._store
    assert len(store.transitions["dep"]) == 1


async def test_recovery_closes_the_incident() -> None:
    from agent.monitoring.query_store import InMemoryMonitoringStore as QueryStore

    health = WorkerHealth()
    broken = _worker(health, _ExplodingMetric())
    await broken.tick(now=NOW)

    class _Fixed(_QuietMetric):
        metric = "exploding"

    fixed = MonitoringWorker(
        store=broken._store,
        registry=broken._registry,
        provider=lambda: [MonitoredDeployment("dep", profile={})],
        window_seconds=300.0,
        interval_seconds=60.0,
        health=health,
        clock=lambda: NOW,
    )
    fixed._registry = MetricRegistry()
    fixed._registry.register(_Fixed())
    await fixed.tick(now=NOW)

    kinds = [t.kind for t in broken._store.transitions["dep"]]
    assert kinds == ["failed", "recovered"]

    # and the dashboard reads them as one closed stretch
    query_store = QueryStore()
    query_store.transitions = broken._store.transitions["dep"]
    service = MonitoringQueryService(
        query_store,
        clock=lambda: NOW.timestamp(),
        health_source=lambda _: (health.snapshot("dep"), (300.0, 60.0)),
    )
    result = await service.worker_health(uuid.uuid4())
    assert len(result.incidents) == 1
    assert result.incidents[0].metric == "exploding"
    assert result.incidents[0].ongoing is False
    assert result.incidents[0].ended_at is not None
