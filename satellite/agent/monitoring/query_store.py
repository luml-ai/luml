"""Read boundary for the Monitoring Query API.

Hides GreptimeDB and the physical schema behind a small Protocol. Parts 1 and 2 own the
production adapter that reads ``inference_events`` / ``monitoring_results`` /
``monitoring_alerts``; this slice depends only on the boundary and ships an in-memory
implementation used by the Query API tests and as the default until the adapter is wired.
"""

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID


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
class ReferenceProfile:
    """The per-deployment reference profile part 2 loads on the deploy path."""

    deployment_id: UUID
    status: str = "ready"  # ready | placeholder
    baseline_label: str | None = None
    computed_at: datetime | None = None
    features: dict[str, ReferenceFeatureProfile] = field(default_factory=dict)


class MonitoringStore(Protocol):
    """Deployment-scoped read access to the monitoring datasets.

    Async because the production adapter reads GreptimeDB over the network; callers derive
    ``deployment_id`` from the dashboard session, never from client input. Every method may
    raise :class:`MonitoringStoreUnavailable`.
    """

    async def describe_deployment(self, deployment_id: UUID) -> DeploymentDescriptor | None: ...

    async def fetch_events(
        self, deployment_id: UUID, start: datetime, end: datetime
    ) -> list[InferenceEvent]: ...

    async def fetch_spans(self, trace_id: str) -> list[SpanRecord]:
        """Every span of one trace. Callers must resolve ``trace_id`` from a
        deployment-scoped event first, so this never widens the deployment scope."""
        ...

    async def fetch_result(
        self, deployment_id: UUID, group: str, window: str
    ) -> StoredMetricResult | None: ...

    async def fetch_alerts(self, deployment_id: UUID) -> list[StoredAlert]: ...

    async def fetch_profile(self, deployment_id: UUID) -> ReferenceProfile | None: ...

    async def profile_status(self, deployment_id: UUID) -> str: ...


@dataclass
class InMemoryMonitoringStore:
    """In-memory :class:`MonitoringStore` for tests and the default (no-data) wiring."""

    unavailable: bool = False
    _meta: dict[UUID, DeploymentDescriptor] = field(default_factory=dict)
    _events: list[InferenceEvent] = field(default_factory=list)
    _spans: list[SpanRecord] = field(default_factory=list)
    _results: dict[tuple[UUID, str, str], StoredMetricResult] = field(default_factory=dict)
    _alerts: list[StoredAlert] = field(default_factory=list)
    _profiles: dict[UUID, str] = field(default_factory=dict)
    _profile_data: dict[UUID, ReferenceProfile] = field(default_factory=dict)

    def add_deployment(self, descriptor: DeploymentDescriptor) -> None:
        self._meta[descriptor.deployment_id] = descriptor

    def add_event(self, event: InferenceEvent) -> None:
        self._events.append(event)

    def add_span(self, span: SpanRecord) -> None:
        self._spans.append(span)

    def add_result(self, result: StoredMetricResult) -> None:
        self._results[(result.deployment_id, result.group, result.window)] = result

    def add_alert(self, alert: StoredAlert) -> None:
        self._alerts.append(alert)

    def set_profile_status(self, deployment_id: UUID, status: str) -> None:
        self._profiles[deployment_id] = status

    def add_profile(self, profile: ReferenceProfile) -> None:
        self._profile_data[profile.deployment_id] = profile
        self._profiles[profile.deployment_id] = profile.status

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

    async def fetch_events(
        self, deployment_id: UUID, start: datetime, end: datetime
    ) -> list[InferenceEvent]:
        self._guard()
        return [
            e for e in self._events if e.deployment_id == deployment_id and start <= e.ts <= end
        ]

    async def fetch_spans(self, trace_id: str) -> list[SpanRecord]:
        self._guard()
        return [s for s in self._spans if s.trace_id == trace_id]

    async def fetch_result(
        self, deployment_id: UUID, group: str, window: str
    ) -> StoredMetricResult | None:
        self._guard()
        return self._results.get((deployment_id, group, window))

    async def fetch_alerts(self, deployment_id: UUID) -> list[StoredAlert]:
        self._guard()
        return [a for a in self._alerts if a.deployment_id == deployment_id and a.state == "open"]

    async def fetch_profile(self, deployment_id: UUID) -> ReferenceProfile | None:
        self._guard()
        return self._profile_data.get(deployment_id)

    async def profile_status(self, deployment_id: UUID) -> str:
        self._guard()
        return self._profiles.get(deployment_id, "ready")
