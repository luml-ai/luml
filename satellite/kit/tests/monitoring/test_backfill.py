"""Catching up: windows missed while the worker was down are still worth computing."""

from datetime import UTC, datetime, timedelta

import pytest

from luml_satellite.monitoring.compute.metric import Metric, MetricInput
from luml_satellite.monitoring.compute.models import (
    DeploymentContext,
    InferenceEvent,
    MetricComputation,
    MonitoredDeployment,
    Severity,
    TimeWindow,
)
from luml_satellite.monitoring.compute.registry import MetricRegistry, default_registry
from luml_satellite.monitoring.compute.worker import MonitoringWorker
from luml_satellite.monitoring.storage.store import InMemoryMonitoringStore

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


class TestBackfill:
    @pytest.mark.parametrize("has_old_event", [False, True])
    async def test_idle_windows_advance_progress_without_repeated_reads(
        self, has_old_event: bool
    ) -> None:
        class _CountingStore(InMemoryMonitoringStore):
            reads = 0

            async def read_events(
                self, deployment_id: str, window: TimeWindow
            ) -> list[InferenceEvent]:
                self.reads += 1
                return await super().read_events(deployment_id, window)

        store = _CountingStore()
        if has_old_event:
            store.add_events(
                "dep",
                [
                    InferenceEvent(
                        event_id="old",
                        deployment_id="dep",
                        status="success",
                        timestamp=NOW - timedelta(minutes=4),
                    )
                ],
            )
        worker = MonitoringWorker(
            store=store,
            registry=default_registry(),
            provider=lambda: [MonitoredDeployment("dep", profile={})],
            window_seconds=WINDOW_SECONDS,
            interval_seconds=60.0,
            max_backfill_windows=12,
        )

        await worker.tick(now=NOW)
        assert await store.last_materialized_window("dep") == datetime(
            2026, 1, 1, 12, 0, tzinfo=UTC
        )

        after_gap = NOW + timedelta(hours=3)
        await worker.tick(now=after_gap)

        assert store.reads == 13
        assert worker.health.for_deployment("dep").windows_processed == 13
        assert await store.last_materialized_window("dep") == datetime(
            2026, 1, 1, 15, 0, tzinfo=UTC
        )

        await worker.tick(now=after_gap + timedelta(seconds=60))
        await worker.tick(now=after_gap + timedelta(seconds=120))
        assert store.reads == 13
        assert worker.health.for_deployment("dep").windows_processed == 13

        await worker.tick(now=after_gap + timedelta(minutes=5))
        assert store.reads == 14
        assert worker.health.for_deployment("dep").windows_processed == 14
        assert await store.last_materialized_window("dep") == datetime(
            2026, 1, 1, 15, 5, tzinfo=UTC
        )

    async def test_a_fresh_deployment_starts_from_the_present(self) -> None:
        """Nothing materialized yet must not mean replaying whatever history the database has."""
        metric = _CountingMetric()

        await _worker(_store_with_events(), metric).tick(now=NOW)

        assert metric.windows == [datetime(2026, 1, 1, 12, 0, tzinfo=UTC)]

    async def test_the_next_tick_has_nothing_to_do(self) -> None:
        store = _store_with_events()
        metric = _CountingMetric()
        worker = _worker(store, metric)

        await worker.tick(now=NOW)
        await worker.tick(now=NOW + timedelta(seconds=60))  # same window, already materialized

        assert metric.windows == [datetime(2026, 1, 1, 12, 0, tzinfo=UTC)]

    async def test_a_gap_is_filled_oldest_first(self) -> None:
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

    async def test_catching_up_is_bounded(self) -> None:
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

    async def test_a_store_that_cannot_answer_still_gets_the_latest_window(self) -> None:
        class _Unreadable(InMemoryMonitoringStore):
            async def last_materialized_window(self, deployment_id: str) -> datetime | None:
                raise RuntimeError("greptime is down")

        store = _Unreadable()
        metric = _CountingMetric()

        await _worker(store, metric).tick(now=NOW)

        assert metric.windows == [datetime(2026, 1, 1, 12, 0, tzinfo=UTC)]
