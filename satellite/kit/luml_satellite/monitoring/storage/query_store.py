"""Read boundary for the Monitoring Query API.

Hides GreptimeDB and the physical schema behind a small Protocol. Parts 1 and 2 own the
production adapter that reads ``inference_events`` / ``monitoring_results`` /
``monitoring_alerts``; this slice depends only on the boundary and ships an in-memory
implementation used by the Query API tests and as the default until the adapter is wired.
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from luml_satellite.monitoring.compute.heartbeat import WorkerHeartbeat
from luml_satellite.monitoring.compute.models import InferenceEvent as WorkerInferenceEvent
from luml_satellite.monitoring.dashboard.schemas import (
    ProfileStatus,
    SortOrder,
    StatusBreakdownRow,
    TraceSort,
)


class EventStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    FAILED_INFERENCE = "failed_inference"


class MonitoringStoreUnavailable(Exception):
    """Raised when the underlying store (GreptimeDB) cannot be reached.

    The Query API turns this into a section-level ``unavailable`` state; inference is
    unaffected — monitoring availability never outranks inference availability.
    """


@dataclass(frozen=True)
class DeploymentDescriptor:
    deployment_id: UUID
    name: str | None = None
    status: str | None = None
    task_type: str | None = None
    model_kind: str = "unknown"
    model_name: str | None = None
    environment: str | None = None
    satellite: str | None = None
    inference_url: str | None = None
    last_prediction_at: datetime | None = None
    last_monitored_at: datetime | None = None


@dataclass(frozen=True)
class InferenceEvent:
    event_id: str
    deployment_id: UUID
    ts: datetime
    status: str
    status_code: int
    latency_ms: float
    trace_id: str | None = None
    span_id: str | None = None
    inputs: str | None = None
    output: str | None = None


@dataclass(frozen=True)
class RuntimeSummary:
    request_count: int
    success_count: int
    error_count: int
    timeout_count: int
    failed_inference_count: int
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    latency_max_ms: float | None
    status_breakdown: tuple[StatusBreakdownRow, ...] = ()
    first_ts: datetime | None = None
    last_ts: datetime | None = None

    @property
    def error_rate(self) -> float:
        return (
            (self.request_count - self.success_count) / self.request_count
            if self.request_count
            else 0.0
        )

    @property
    def success_rate(self) -> float:
        """Kept beside ``error_rate`` rather than derived in the UI, which does no math.

        An empty window is 0%, not 100%: nothing succeeded, and reading it as a perfect
        window would be the wrong headline for a deployment nobody called.
        """
        return self.success_count / self.request_count if self.request_count else 0.0


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def _outcome(event: InferenceEvent) -> WorkerInferenceEvent:
    return WorkerInferenceEvent(
        event_id=event.event_id,
        deployment_id=str(event.deployment_id),
        status=event.status,
        status_code=event.status_code,
    )


def _rollup(events: list[InferenceEvent]) -> RuntimeSummary:
    total = len(events)
    outcomes = [_outcome(e) for e in events]
    success = sum(1 for o in outcomes if o.is_success)
    latencies = [e.latency_ms for e in events]
    return RuntimeSummary(
        request_count=total,
        success_count=success,
        error_count=total - success,
        timeout_count=sum(1 for o in outcomes if o.is_timeout),
        failed_inference_count=sum(1 for o in outcomes if o.is_failed_inference),
        latency_p50_ms=_percentile(latencies, 50),
        latency_p95_ms=_percentile(latencies, 95),
        latency_max_ms=max(latencies) if latencies else None,
        status_breakdown=_status_breakdown(events),
        first_ts=min((e.ts for e in events), default=None),
        last_ts=max((e.ts for e in events), default=None),
    )


def _status_breakdown(events: list[InferenceEvent]) -> tuple[StatusBreakdownRow, ...]:
    """Group the window's calls by outcome and HTTP code, busiest row first.

    Outcome and code are kept as separate columns rather than one label: the same code
    carries different meaning per outcome (a 504 is a timeout, a 500 a failed inference),
    and a reader scanning for what broke wants both.
    """
    counts: dict[tuple[str, int | None], int] = defaultdict(int)
    for event in events:
        counts[(str(event.status), event.status_code)] += 1
    total = len(events)
    rows = [
        StatusBreakdownRow(
            status=status,
            status_code=code,
            count=count,
            share=count / total if total else 0.0,
        )
        for (status, code), count in counts.items()
    ]
    rows.sort(key=lambda row: (-row.count, row.status, row.status_code or 0))
    return tuple(rows)


@dataclass(frozen=True)
class RuntimeBucket:
    request_count: int
    success_count: int
    latency_p95_ms: float | None

    @property
    def error_rate(self) -> float | None:
        return (
            (self.request_count - self.success_count) / self.request_count
            if self.request_count
            else None
        )


@dataclass(frozen=True)
class SpanRecord:
    """One OpenTelemetry span of an inference trace, as stored by the collector.

    Mirrors the span shape the Platform's experiment-snapshot viewer renders, so the
    Satellite dashboard can show the same tree: `parent_span_id` links the tree,
    the nanosecond timestamps drive the waterfall bars.
    """

    span_id: str
    trace_id: str
    name: str
    kind: int
    start_time_unix_nano: int
    end_time_unix_nano: int
    parent_span_id: str | None = None
    status_code: int | None = None
    status_message: str | None = None
    dfs_span_type: int | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[Any] = field(default_factory=list)
    links: list[Any] = field(default_factory=list)


@dataclass(frozen=True)
class StoredMetricResult:
    deployment_id: UUID
    group: str
    window: str
    values: dict[str, Any]
    severity: str
    computed_at: datetime | None = None


@dataclass(frozen=True)
class StoredAlert:
    deployment_id: UUID
    group: str
    metric: str
    severity: str
    feature: str | None = None
    current_value: float | None = None
    threshold: float | None = None
    state: str = "open"
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    message: str | None = None


@dataclass(frozen=True)
class ReferenceFeatureProfile:
    """A single feature's training-time baseline: summary stats plus its reference shape."""

    feature: str
    kind: str  # "numeric" | "categorical"
    summary: dict[str, float] = field(default_factory=dict)
    bin_edges: list[float] | None = None  # numeric histogram edges
    histogram: list[float] | None = None  # numeric reference density per bin
    categories: list[str] | None = None  # categorical labels
    category_probabilities: list[float] | None = None  # categorical reference probabilities


@dataclass(frozen=True)
class StoredMetricTransition:
    """One entry of the worker's own failure history."""

    metric: str
    kind: str  # failed | recovered
    error: str
    at: datetime


@dataclass(frozen=True)
class ReferenceProfile:
    """The per-deployment reference profile part 2 loads on the deploy path."""

    deployment_id: UUID
    status: ProfileStatus = ProfileStatus.READY
    baseline_label: str | None = None
    computed_at: datetime | None = None
    features: dict[str, ReferenceFeatureProfile] = field(default_factory=dict)
    # The artifact's ``reference_profile.json`` as it is, for the tab that shows the file.
    document: dict[str, Any] | None = None


class MonitoringStore(Protocol):
    """Deployment-scoped read access to the monitoring datasets.

    Async because the production adapter reads GreptimeDB over the network; callers derive
    ``deployment_id`` from the dashboard session, never from client input. Every method may
    raise :class:`MonitoringStoreUnavailable`.
    """

    async def describe_deployment(self, deployment_id: UUID) -> DeploymentDescriptor | None: ...

    async def fetch_events(
        self,
        deployment_id: UUID,
        start: datetime,
        end: datetime,
        *,
        limit: int = 50,
        offset: int = 0,
        sort: TraceSort = TraceSort.TS,
        order: SortOrder = SortOrder.DESC,
    ) -> list[InferenceEvent]: ...

    async def count_events(self, deployment_id: UUID, start: datetime, end: datetime) -> int: ...

    async def fetch_event(
        self, deployment_id: UUID, start: datetime, end: datetime, event_id: str
    ) -> InferenceEvent | None: ...

    async def fetch_runtime_summary(
        self, deployment_id: UUID, start: datetime, end: datetime
    ) -> RuntimeSummary: ...

    async def fetch_runtime_buckets(
        self,
        deployment_id: UUID,
        start: datetime,
        end: datetime,
        series_start: datetime,
        bucket_seconds: int,
        n_buckets: int,
    ) -> dict[int, RuntimeBucket]: ...

    async def fetch_spans(self, trace_id: str) -> list[SpanRecord]:
        """Every span of one trace. Callers must resolve ``trace_id`` from a
        deployment-scoped event first, so this never widens the deployment scope."""
        ...

    async def fetch_result(
        self, deployment_id: UUID, group: str, window: str
    ) -> StoredMetricResult | None: ...

    async def fetch_result_history(
        self,
        deployment_id: UUID,
        group: str,
        window: str,
        *,
        since: datetime,
        until: datetime | None = None,
    ) -> list[StoredMetricResult]:
        """Every materialized window of a metric group since ``since``, oldest first.

        The worker writes one row per window, so a trend line over a metric — PSI of a
        feature, say — is assembled from these rows rather than stored as a series.
        ``until`` bounds the read from above; compare mode uses it to aggregate a past
        period without dragging the present in.
        """
        ...

    async def fetch_alerts(self, deployment_id: UUID) -> list[StoredAlert]: ...

    async def fetch_metric_transitions(
        self, deployment_id: UUID, since: datetime
    ) -> list[StoredMetricTransition]:
        """The worker's failure history for this deployment, oldest first."""
        ...

    async def acknowledge_alert(self, deployment_id: UUID, metric: str) -> bool:
        """Mark one open alert as acknowledged; ``False`` when there is nothing to mark.

        The alert keeps firing and keeps its numbers — acknowledging only says a human has
        seen it, so the worker leaves the state alone until the condition clears.
        """
        ...

    async def fetch_profile(self, deployment_id: UUID) -> ReferenceProfile | None: ...

    async def profile_status(self, deployment_id: UUID) -> ProfileStatus: ...

    async def read_worker_heartbeats(self) -> list[WorkerHeartbeat]: ...


@dataclass
class InMemoryMonitoringStore:
    """In-memory :class:`MonitoringStore` for tests and the default (no-data) wiring."""

    unavailable: bool = False
    _meta: dict[UUID, DeploymentDescriptor] = field(default_factory=dict)
    _events: list[InferenceEvent] = field(default_factory=list)
    _spans: list[SpanRecord] = field(default_factory=list)
    _results: dict[tuple[UUID, str, str], StoredMetricResult] = field(default_factory=dict)
    # every window ever written, so trend lines can be assembled from past windows
    _history: list[StoredMetricResult] = field(default_factory=list)
    _alerts: list[StoredAlert] = field(default_factory=list)
    _profiles: dict[UUID, ProfileStatus] = field(default_factory=dict)
    _profile_data: dict[UUID, ReferenceProfile] = field(default_factory=dict)
    # The worker's own failure history, as the dashboard reads it back.
    transitions: list[StoredMetricTransition] = field(default_factory=list)
    _heartbeats: dict[tuple[int, int], WorkerHeartbeat] = field(default_factory=dict)

    def add_deployment(self, descriptor: DeploymentDescriptor) -> None:
        self._meta[descriptor.deployment_id] = descriptor

    def add_event(self, event: InferenceEvent) -> None:
        self._events.append(event)

    def add_span(self, span: SpanRecord) -> None:
        self._spans.append(span)

    def add_result(self, result: StoredMetricResult) -> None:
        self._results[(result.deployment_id, result.group, result.window)] = result
        self._history.append(result)

    def add_alert(self, alert: StoredAlert) -> None:
        self._alerts.append(alert)

    def set_profile_status(self, deployment_id: UUID, status: ProfileStatus | str) -> None:
        self._profiles[deployment_id] = ProfileStatus(status)

    def add_profile(self, profile: ReferenceProfile) -> None:
        self._profile_data[profile.deployment_id] = profile
        self._profiles[profile.deployment_id] = ProfileStatus(profile.status)

    async def write_worker_heartbeat(self, heartbeat: WorkerHeartbeat) -> None:
        self._heartbeats[(heartbeat.shard_count, heartbeat.shard_index)] = heartbeat

    async def read_worker_heartbeats(self) -> list[WorkerHeartbeat]:
        self._guard()
        return list(self._heartbeats.values())

    def _guard(self) -> None:
        if self.unavailable:
            raise MonitoringStoreUnavailable("monitoring store unavailable")

    async def describe_deployment(self, deployment_id: UUID) -> DeploymentDescriptor | None:
        self._guard()
        meta = self._meta.get(deployment_id)
        if meta is None:
            return None
        event_times = [e.ts for e in self._events if e.deployment_id == deployment_id]
        result_times = [
            r.computed_at
            for (dep, _group, _window), r in self._results.items()
            if dep == deployment_id and r.computed_at is not None
        ]
        return replace(
            meta,
            last_prediction_at=max(event_times, default=None),
            last_monitored_at=max(result_times, default=None),
        )

    def _matching_events(
        self, deployment_id: UUID, start: datetime, end: datetime
    ) -> list[InferenceEvent]:
        self._guard()
        return [e for e in self._events if e.deployment_id == deployment_id and start <= e.ts < end]

    async def fetch_events(
        self,
        deployment_id: UUID,
        start: datetime,
        end: datetime,
        *,
        limit: int = 50,
        offset: int = 0,
        sort: TraceSort = TraceSort.TS,
        order: SortOrder = SortOrder.DESC,
    ) -> list[InferenceEvent]:
        if not 1 <= limit <= 200 or offset < 0:
            raise ValueError("invalid event page bounds")
        sort, order = TraceSort(sort), SortOrder(order)
        keys = {
            TraceSort.TS: lambda e: (e.ts, e.event_id),
            TraceSort.LATENCY: lambda e: (e.latency_ms, e.ts, e.event_id),
            TraceSort.STATUS: lambda e: (e.status_code, e.ts, e.event_id),
        }
        events = sorted(
            self._matching_events(deployment_id, start, end),
            key=keys[sort],
            reverse=order is SortOrder.DESC,
        )
        return events[offset : offset + limit]

    async def count_events(self, deployment_id: UUID, start: datetime, end: datetime) -> int:
        return len(self._matching_events(deployment_id, start, end))

    async def fetch_event(
        self, deployment_id: UUID, start: datetime, end: datetime, event_id: str
    ) -> InferenceEvent | None:
        return next(
            (e for e in self._matching_events(deployment_id, start, end) if e.event_id == event_id),
            None,
        )

    async def fetch_runtime_summary(
        self, deployment_id: UUID, start: datetime, end: datetime
    ) -> RuntimeSummary:
        return _rollup(self._matching_events(deployment_id, start, end))

    async def fetch_runtime_buckets(
        self,
        deployment_id: UUID,
        start: datetime,
        end: datetime,
        series_start: datetime,
        bucket_seconds: int,
        n_buckets: int,
    ) -> dict[int, RuntimeBucket]:
        if bucket_seconds <= 0 or n_buckets <= 0:
            raise ValueError("bucket size and count must be positive")
        buckets: dict[int, list[InferenceEvent]] = defaultdict(list)
        for event in self._matching_events(deployment_id, start, end):
            index = math.floor((event.ts - series_start).total_seconds() / bucket_seconds)
            buckets[min(max(index, 0), n_buckets - 1)].append(event)
        return {
            index: RuntimeBucket(
                len(events),
                sum(1 for e in events if _outcome(e).is_success),
                _percentile([e.latency_ms for e in events], 95),
            )
            for index, events in buckets.items()
        }

    async def fetch_spans(self, trace_id: str) -> list[SpanRecord]:
        self._guard()
        return [s for s in self._spans if s.trace_id == trace_id]

    async def fetch_result(
        self, deployment_id: UUID, group: str, window: str
    ) -> StoredMetricResult | None:
        self._guard()
        return self._results.get((deployment_id, group, window))

    async def fetch_result_history(
        self,
        deployment_id: UUID,
        group: str,
        window: str,
        *,
        since: datetime,
        until: datetime | None = None,
    ) -> list[StoredMetricResult]:
        self._guard()
        matching = [
            result
            for result in self._history
            if result.deployment_id == deployment_id
            and result.group == group
            and result.window == window
            and result.computed_at is not None
            and result.computed_at >= since
            and (until is None or result.computed_at <= until)
        ]
        return sorted(matching, key=lambda result: result.computed_at or since)

    async def fetch_alerts(self, deployment_id: UUID) -> list[StoredAlert]:
        self._guard()

        return [
            a for a in self._alerts if a.deployment_id == deployment_id and a.state != "resolved"
        ]

    async def fetch_metric_transitions(
        self, deployment_id: UUID, since: datetime
    ) -> list[StoredMetricTransition]:
        self._guard()
        return [t for t in self.transitions if t.at >= since]

    async def acknowledge_alert(self, deployment_id: UUID, metric: str) -> bool:
        self._guard()
        for index, alert in enumerate(self._alerts):
            if alert.deployment_id == deployment_id and alert.metric == metric:
                self._alerts[index] = replace(alert, state="acknowledged")
                return True
        return False

    async def fetch_profile(self, deployment_id: UUID) -> ReferenceProfile | None:
        self._guard()
        return self._profile_data.get(deployment_id)

    async def profile_status(self, deployment_id: UUID) -> ProfileStatus:
        self._guard()
        return self._profiles.get(deployment_id, ProfileStatus.ABSENT)
