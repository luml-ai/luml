"""Catching up: windows missed while the worker was down are still worth computing."""

from datetime import UTC, datetime, timedelta

from agent.monitoring.metric import Metric, MetricInput
from agent.monitoring.models import (
    DeploymentContext,
    InferenceEvent,
    MetricComputation,
    MonitoredDeployment,
    Severity,
)
from agent.monitoring.registry import MetricRegistry
from agent.monitoring.store import InMemoryMonitoringStore
from agent.monitoring.worker import MonitoringWorker

WINDOW_SECONDS = 300.0
NOW = datetime(2026, 1, 1, 12, 2, tzinfo=UTC)  # latest complete window ends 12:00


class _CountingMetric(Metric):
    metric = "runtime"

    def __init__(self) -> None:
        self.windows: list[datetime] = []

    def applies(self, context: DeploymentContext) -> bool:
        return True

    def compute(self, data: MetricInput) -> MetricComputation:
        self.windows.append(data.window.end)
        return MetricComputation(values={"n": 1}, severity=Severity.NORMAL, signals=[])


def _worker(
    store: InMemoryMonitoringStore, metric: Metric, *, max_backfill_windows: int = 12
) -> MonitoringWorker:
    registry = MetricRegistry()
    registry.register(metric)
    return MonitoringWorker(
        store=store,
        registry=registry,
        provider=lambda: [MonitoredDeployment("dep", profile={})],
        window_seconds=WINDOW_SECONDS,
        interval_seconds=60.0,
        max_backfill_windows=max_backfill_windows,
    )


def _store_with_events() -> InMemoryMonitoringStore:
    store = InMemoryMonitoringStore()
    store.add_events(
        "dep",
        [
            InferenceEvent(
                event_id="e",
                deployment_id="dep",
                status="success",
                status_code=200,
                latency_ms=5.0,
                timestamp=NOW - timedelta(minutes=minutes),
            )
            for minutes in range(60)
        ],
    )
    return store


async def test_a_fresh_deployment_starts_from_the_present() -> None:
    """Nothing materialized yet must not mean replaying whatever history the database has."""
    metric = _CountingMetric()

    await _worker(_store_with_events(), metric).tick(now=NOW)

    assert metric.windows == [datetime(2026, 1, 1, 12, 0, tzinfo=UTC)]


async def test_the_next_tick_has_nothing_to_do() -> None:
    store = _store_with_events()
    metric = _CountingMetric()
    worker = _worker(store, metric)

    await worker.tick(now=NOW)
    await worker.tick(now=NOW + timedelta(seconds=60))  # same window, already materialized

    assert metric.windows == [datetime(2026, 1, 1, 12, 0, tzinfo=UTC)]


async def test_a_gap_is_filled_oldest_first() -> None:
    """The agent was down for half an hour; those windows still have their events."""
    store = _store_with_events()
    metric = _CountingMetric()
    worker = _worker(store, metric)

    await worker.tick(now=datetime(2026, 1, 1, 11, 32, tzinfo=UTC))  # window ending 11:30
    metric.windows.clear()

    await worker.tick(now=NOW)  # half an hour later

    assert metric.windows == [
        datetime(2026, 1, 1, 11, 35, tzinfo=UTC),
        datetime(2026, 1, 1, 11, 40, tzinfo=UTC),
        datetime(2026, 1, 1, 11, 45, tzinfo=UTC),
        datetime(2026, 1, 1, 11, 50, tzinfo=UTC),
        datetime(2026, 1, 1, 11, 55, tzinfo=UTC),
        datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    ]


async def test_catching_up_is_bounded() -> None:
    """A weekend-long outage must not replay hundreds of windows on the first tick."""
    store = _store_with_events()
    metric = _CountingMetric()
    worker = _worker(store, metric, max_backfill_windows=3)

    await worker.tick(now=datetime(2026, 1, 1, 11, 32, tzinfo=UTC))
    metric.windows.clear()

    await worker.tick(now=NOW)

    # the three most recent of the six missing windows, still oldest first
    assert metric.windows == [
        datetime(2026, 1, 1, 11, 50, tzinfo=UTC),
        datetime(2026, 1, 1, 11, 55, tzinfo=UTC),
        datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    ]


async def test_a_store_that_cannot_answer_still_gets_the_latest_window() -> None:
    class _Unreadable(InMemoryMonitoringStore):
        async def last_materialized_window(self, deployment_id: str) -> datetime | None:
            raise RuntimeError("greptime is down")

    store = _Unreadable()
    metric = _CountingMetric()

    await _worker(store, metric).tick(now=NOW)

    assert metric.windows == [datetime(2026, 1, 1, 12, 0, tzinfo=UTC)]
