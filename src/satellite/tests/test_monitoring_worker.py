from collections.abc import Callable
from datetime import UTC, datetime

from agent.monitoring.metric import Metric, MetricInput
from agent.monitoring.models import (
    AlertSignal,
    AlertState,
    DeploymentContext,
    InferenceEvent,
    MetricComputation,
    MonitoredDeployment,
    Severity,
)
from agent.monitoring.registry import MetricRegistry, default_registry
from agent.monitoring.runtime_health import RuntimeHealthMetric
from agent.monitoring.store import InMemoryMonitoringStore
from agent.monitoring.worker import MonitoringWorker, monitored_deployments
from agent.schemas import LocalDeployment

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 1, 1, 12, 5, tzinfo=UTC)


class FakeMetric(Metric):
    """A registry entry with configurable applicability and output, for engine tests."""

    def __init__(
        self,
        metric: str,
        *,
        applies: Callable[[DeploymentContext], bool],
        computation: MetricComputation | None = None,
        raises: bool = False,
    ) -> None:
        self.metric = metric
        self._applies = applies
        self._computation = computation or MetricComputation({}, Severity.NORMAL, [])
        self._raises = raises
        self.compute_calls = 0

    def applies(self, context: DeploymentContext) -> bool:
        return self._applies(context)

    def compute(self, data: MetricInput) -> MetricComputation:
        self.compute_calls += 1
        if self._raises:
            raise RuntimeError("boom")
        return self._computation


def _ok_event(latency: float = 10.0) -> InferenceEvent:
    return InferenceEvent(
        event_id="e", deployment_id="dep", status="success", status_code=200, latency_ms=latency
    )


def _error_event() -> InferenceEvent:
    return InferenceEvent(
        event_id="e", deployment_id="dep", status="error", status_code=500, latency_ms=10.0
    )


def _worker(store: InMemoryMonitoringStore, registry: MetricRegistry) -> MonitoringWorker:
    return MonitoringWorker(
        store=store,
        registry=registry,
        provider=lambda: [MonitoredDeployment(deployment_id="dep", profile=None)],
        window_seconds=300.0,
        interval_seconds=60.0,
    )


async def test_latest_window_is_most_recent_completed() -> None:
    worker = _worker(InMemoryMonitoringStore(), default_registry())
    window = worker.latest_window(datetime(2026, 1, 1, 12, 3, 30, tzinfo=UTC))

    assert window.end == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert window.start == datetime(2026, 1, 1, 11, 55, tzinfo=UTC)


async def test_only_provided_deployments_are_processed() -> None:
    store = InMemoryMonitoringStore()
    store.add_events("dep", [_ok_event()])
    store.add_events("other", [_ok_event()])
    worker = _worker(store, default_registry())

    await worker.tick(now=NOW)

    processed = {result.deployment_id for result in store.results}
    assert processed == {"dep"}


def test_monitored_deployments_filters_disabled() -> None:
    deployments = [
        LocalDeployment(deployment_id="on", monitoring_enabled=True),
        LocalDeployment(deployment_id="off", monitoring_enabled=False),
    ]

    selected = monitored_deployments(deployments)

    assert [d.deployment_id for d in selected] == ["on"]


async def test_selection_runs_runtime_health_and_skips_profile_metrics() -> None:
    store = InMemoryMonitoringStore()
    store.add_events("dep", [_ok_event()])
    needs_profile = FakeMetric("needs_profile", applies=lambda ctx: ctx.has_profile)
    registry = MetricRegistry([RuntimeHealthMetric(), needs_profile])
    worker = _worker(store, registry)

    await worker.tick(now=NOW)

    groups = {result.metric for result in store.results}
    assert "runtime" in groups
    assert "needs_profile" not in groups
    assert needs_profile.compute_calls == 0


async def test_no_events_produces_no_runtime_result() -> None:
    store = InMemoryMonitoringStore()
    worker = _worker(store, default_registry())

    await worker.tick(now=NOW)

    assert store.results == []


async def test_results_and_alerts_are_materialized() -> None:
    store = InMemoryMonitoringStore()
    store.add_events("dep", [_ok_event() for _ in range(9)] + [_error_event()])
    worker = _worker(store, default_registry())

    await worker.tick(now=NOW)

    result = next(r for r in store.results if r.metric == "runtime")
    assert result.severity == Severity.CRITICAL
    assert result.values["error_rate"] == 0.1
    assert result.profile_status == "absent"

    alerts = await store.active_alerts("dep")
    error_alert = next(a for a in alerts if a.metric == "runtime:error_rate")
    assert error_alert.state == AlertState.OPEN
    assert error_alert.severity == Severity.CRITICAL
    assert error_alert.first_seen == error_alert.last_seen


async def test_profile_status_ready_when_profile_present() -> None:
    store = InMemoryMonitoringStore()
    store.add_events("dep", [_ok_event()])
    worker = MonitoringWorker(
        store=store,
        registry=default_registry(),
        provider=lambda: [MonitoredDeployment("dep", profile={"task_type": "regression"})],
        window_seconds=300.0,
        interval_seconds=60.0,
    )

    await worker.tick(now=NOW)

    assert store.results[0].profile_status == "ready"


async def test_alert_opens_then_resolves() -> None:
    store = InMemoryMonitoringStore()
    store.events["dep"] = [_ok_event() for _ in range(9)] + [_error_event()]
    worker = _worker(store, default_registry())

    await worker.tick(now=NOW)
    opened = await store.active_alerts("dep")
    assert any(a.metric == "runtime:error_rate" and a.state == AlertState.OPEN for a in opened)

    store.events["dep"] = [_ok_event() for _ in range(10)]
    await worker.tick(now=LATER)

    assert await store.active_alerts("dep") == []
    resolved = store.alerts[("dep", "runtime:error_rate")]
    assert resolved.state == AlertState.RESOLVED
    assert resolved.last_seen == worker.latest_window(LATER).end


async def test_alert_updates_while_it_persists() -> None:
    store = InMemoryMonitoringStore()
    store.events["dep"] = [_ok_event() for _ in range(9)] + [_error_event()]
    worker = _worker(store, default_registry())

    await worker.tick(now=NOW)
    first = store.alerts[("dep", "runtime:error_rate")]
    first_seen = first.first_seen

    await worker.tick(now=LATER)
    updated = store.alerts[("dep", "runtime:error_rate")]

    assert updated.state == AlertState.OPEN
    assert updated.first_seen == first_seen
    assert updated.last_seen == worker.latest_window(LATER).end


async def test_failing_metric_does_not_stop_others() -> None:
    store = InMemoryMonitoringStore()
    store.add_events("dep", [_ok_event()])
    broken = FakeMetric("broken", applies=lambda ctx: True, raises=True)
    registry = MetricRegistry([broken, RuntimeHealthMetric()])
    worker = _worker(store, registry)

    await worker.tick(now=NOW)

    assert broken.compute_calls == 1
    assert any(r.metric == "runtime" for r in store.results)


async def test_new_registry_metric_is_computed_and_materialized() -> None:
    store = InMemoryMonitoringStore()
    store.add_events("dep", [_ok_event()])
    custom = FakeMetric(
        "custom",
        applies=lambda ctx: ctx.has_events,
        computation=MetricComputation(
            values={"score": 0.9},
            severity=Severity.WARNING,
            signals=[AlertSignal("score", 0.9, 0.5, Severity.WARNING)],
        ),
    )
    worker = _worker(store, MetricRegistry([custom]))

    await worker.tick(now=NOW)

    result = next(r for r in store.results if r.metric == "custom")
    assert result.values == {"score": 0.9}
    alerts = await store.active_alerts("dep")
    assert any(a.metric == "custom:score" and a.severity == Severity.WARNING for a in alerts)


class FailingReadStore(InMemoryMonitoringStore):
    async def read_events(self, deployment_id, window):  # noqa: ANN001, ANN201
        raise RuntimeError("greptime down")


class FailingWriteStore(InMemoryMonitoringStore):
    async def write_result(self, result) -> None:  # noqa: ANN001
        raise RuntimeError("write failed")


async def test_storage_read_failure_skips_window_without_raising() -> None:
    store = FailingReadStore()
    store.add_events("dep", [_ok_event()])
    worker = _worker(store, default_registry())

    await worker.tick(now=NOW)  # must not raise

    assert store.results == []


async def test_storage_write_failure_is_isolated() -> None:
    store = FailingWriteStore()
    store.add_events("dep", [_ok_event()])
    worker = _worker(store, default_registry())

    await worker.tick(now=NOW)  # must not raise

    assert store.results == []


async def test_window_recovers_after_transient_storage_failure() -> None:
    healthy = InMemoryMonitoringStore()
    healthy.add_events("dep", [_ok_event()])
    worker = _worker(healthy, default_registry())

    await worker.tick(now=NOW)

    assert any(r.metric == "runtime" for r in healthy.results)
