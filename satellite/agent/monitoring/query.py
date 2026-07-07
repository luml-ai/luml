"""Chart-ready read logic for the Monitoring Query API.

Turns the store's rows into already-aggregated, render-ready contracts — the UI does no
metric math. ``deployment_id`` always comes from the caller (the dashboard session), never
from client input.
"""

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import time
from uuid import UUID

from agent.monitoring.query_store import (
    EventStatus,
    InferenceEvent,
    MonitoringStore,
    MonitoringStoreUnavailable,
    ReferenceFeatureProfile,
    StoredAlert,
    StoredMetricResult,
)
from agent.schemas.monitoring_query import (
    AlertBanner,
    AlertGroup,
    AlertsResponse,
    Card,
    Compare,
    DataQualityFeatureRow,
    DataQualityResponse,
    DistributionBin,
    DriftedFeature,
    FeatureDistribution,
    FeatureDriftDetail,
    FeatureDriftResponse,
    Granularity,
    HeaderResponse,
    MultivariatePanel,
    OverviewResponse,
    PcaPoint,
    ProfileStatus,
    ReferenceProfileFeature,
    ReferenceProfileResponse,
    RuntimeResponse,
    SectionState,
    Series,
    SeriesPoint,
    Severity,
    SeverityFilter,
    TraceRow,
    TracesResponse,
    Window,
)

GROUP_RUNTIME = "runtime"
GROUP_DATA_QUALITY = "data_quality"
GROUP_FEATURE_DRIFT = "feature_drift"
GROUP_MULTIVARIATE = "multivariate"

_WINDOW_SECONDS: dict[Window, int] = {
    Window.H24: 24 * 3600,
    Window.D7: 7 * 24 * 3600,
    Window.D30: 30 * 24 * 3600,
}
_AUTO_BUCKET_SECONDS: dict[Window, int] = {
    Window.H24: 3600,
    Window.D7: 6 * 3600,
    Window.D30: 24 * 3600,
}
_BANNER_LIMIT = 5
_TOP_DRIFTED_LIMIT = 5
_ALERT_GROUP_ORDER = (GROUP_RUNTIME, GROUP_DATA_QUALITY, GROUP_FEATURE_DRIFT)

TRACES_DEFAULT_LIMIT = 50
TRACES_MAX_LIMIT = 200
_TRACE_SUMMARY_MAX_LEN = 200
_TRACE_SUMMARY_MAX_KEYS = 8


@dataclass(frozen=True)
class QueryDimensions:
    window: Window = Window.H24
    compare: Compare = Compare.REFERENCE
    severity: SeverityFilter = SeverityFilter.ALL
    granularity: Granularity = Granularity.AUTO
    feature: str | None = None


@dataclass(frozen=True)
class _Rollup:
    request_count: int
    success_count: int
    error_count: int
    timeout_count: int
    failed_inference_count: int
    error_rate: float
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    latency_max_ms: float | None


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def _rollup(events: list[InferenceEvent]) -> _Rollup:
    total = len(events)
    success = sum(1 for e in events if e.status == EventStatus.SUCCESS)
    latencies = [e.latency_ms for e in events]
    return _Rollup(
        request_count=total,
        success_count=success,
        error_count=sum(1 for e in events if e.status == EventStatus.ERROR),
        timeout_count=sum(1 for e in events if e.status == EventStatus.TIMEOUT),
        failed_inference_count=sum(1 for e in events if e.status == EventStatus.FAILED_INFERENCE),
        error_rate=(total - success) / total if total else 0.0,
        latency_p50_ms=_percentile(latencies, 50),
        latency_p95_ms=_percentile(latencies, 95),
        latency_max_ms=max(latencies) if latencies else None,
    )


def _bucket_seconds(dims: QueryDimensions) -> int:
    if dims.granularity is Granularity.HOUR:
        bucket = 3600
    elif dims.granularity is Granularity.DAY:
        bucket = 24 * 3600
    else:
        bucket = _AUTO_BUCKET_SECONDS[dims.window]
    return min(bucket, _WINDOW_SECONDS[dims.window])


def _runtime_series(
    events: list[InferenceEvent], start: datetime, bucket_seconds: int, n_buckets: int
) -> list[Series]:
    buckets: list[list[InferenceEvent]] = [[] for _ in range(n_buckets)]
    for event in events:
        index = int((event.ts - start).total_seconds() // bucket_seconds)
        buckets[min(max(index, 0), n_buckets - 1)].append(event)

    stamps = [start + timedelta(seconds=i * bucket_seconds) for i in range(n_buckets)]
    requests, error_rate, latency = [], [], []
    for stamp, bucket in zip(stamps, buckets, strict=True):
        count = len(bucket)
        successes = sum(1 for e in bucket if e.status == EventStatus.SUCCESS)
        requests.append(SeriesPoint(t=stamp, value=float(count)))
        error_rate.append(
            SeriesPoint(t=stamp, value=(count - successes) / count if count else None)
        )
        latency.append(SeriesPoint(t=stamp, value=_percentile([e.latency_ms for e in bucket], 95)))
    return [
        Series(key="requests", label="Requests", points=requests),
        Series(key="error_rate", label="Error rate", unit="ratio", points=error_rate),
        Series(key="latency_p95", label="Latency p95", unit="ms", points=latency),
    ]


def _severity_matches(severity: str, chosen: SeverityFilter) -> bool:
    if chosen is SeverityFilter.ALL:
        return True
    return severity == chosen.value


def _alert_banner(alert: StoredAlert) -> AlertBanner:
    label = alert.feature or alert.metric
    message = alert.message or (
        f"{label} {alert.severity}: {alert.current_value} vs threshold {alert.threshold}"
    )
    return AlertBanner(
        group=alert.group,
        metric=alert.metric,
        feature=alert.feature,
        severity=Severity(alert.severity),
        current_value=alert.current_value,
        threshold=alert.threshold,
        message=message,
        first_seen=alert.first_seen,
        last_seen=alert.last_seen,
    )


def _delta(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return current - previous


class MonitoringQueryService:
    """Assembles the Query API contracts from a :class:`MonitoringStore`."""

    def __init__(self, store: MonitoringStore, clock: Callable[[], float] = time) -> None:
        self._store = store
        self._clock = clock

    def _window_bounds(self, window: Window) -> tuple[datetime, datetime]:
        end = datetime.fromtimestamp(self._clock(), tz=UTC)
        return end - timedelta(seconds=_WINDOW_SECONDS[window]), end

    async def header(self, deployment_id: UUID) -> HeaderResponse:
        try:
            descriptor = await self._store.describe_deployment(deployment_id)
            profile = await self._profile_status(deployment_id)
        except MonitoringStoreUnavailable:
            return HeaderResponse(state=SectionState.UNAVAILABLE, deployment_id=deployment_id)
        if descriptor is None:
            return HeaderResponse(
                state=SectionState.EMPTY, deployment_id=deployment_id, profile_status=profile
            )
        return HeaderResponse(
            state=SectionState.OK,
            deployment_id=deployment_id,
            name=descriptor.name,
            status=descriptor.status,
            task_type=descriptor.task_type,
            model_name=descriptor.model_name,
            environment=descriptor.environment,
            satellite=descriptor.satellite,
            inference_url=descriptor.inference_url,
            last_prediction_at=descriptor.last_prediction_at,
            last_monitored_at=descriptor.last_monitored_at,
            profile_status=profile,
        )

    async def runtime(self, deployment_id: UUID, dims: QueryDimensions) -> RuntimeResponse:
        try:
            rollup, series = await self._runtime(deployment_id, dims)
            alerts = await self._banners(deployment_id, dims.severity, group=GROUP_RUNTIME)
            profile = await self._profile_status(deployment_id)
        except MonitoringStoreUnavailable:
            return RuntimeResponse(state=SectionState.UNAVAILABLE)
        return RuntimeResponse(
            state=SectionState.OK,
            profile_status=profile,
            request_count=rollup.request_count,
            success_count=rollup.success_count,
            error_count=rollup.error_count,
            error_rate=rollup.error_rate,
            latency_p50_ms=rollup.latency_p50_ms,
            latency_p95_ms=rollup.latency_p95_ms,
            latency_max_ms=rollup.latency_max_ms,
            timeout_count=rollup.timeout_count,
            failed_inference_count=rollup.failed_inference_count,
            series=series,
            alerts=alerts,
        )

    async def overview(self, deployment_id: UUID, dims: QueryDimensions) -> OverviewResponse:
        try:
            rollup, series = await self._runtime(deployment_id, dims)
            previous = await self._previous_rollup(deployment_id, dims)
            alerts = await self._store.fetch_alerts(deployment_id)
            drift = await self._store.fetch_result(
                deployment_id, GROUP_FEATURE_DRIFT, dims.window.value
            )
            profile = await self._profile_status(deployment_id)
        except MonitoringStoreUnavailable:
            return OverviewResponse(state=SectionState.UNAVAILABLE)

        matching = [a for a in alerts if _severity_matches(a.severity, dims.severity)]
        criticals = [a for a in matching if a.severity == Severity.CRITICAL]
        banners = [_alert_banner(a) for a in sorted(matching, key=_banner_order)][:_BANNER_LIMIT]

        drifted = _drifted_features(drift.values if drift else {})
        top_drifted = sorted(drifted, key=lambda d: d.psi, reverse=True)[:_TOP_DRIFTED_LIMIT]
        drifted_names = [d.feature for d in drifted if d.severity is not Severity.OK]

        return OverviewResponse(
            state=SectionState.OK,
            profile_status=profile,
            cards=_overview_cards(rollup, previous, dims, matching, criticals, drifted_names),
            alert_banners=banners,
            series=series,
            top_drifted_features=top_drifted,
        )

    async def data_quality(self, deployment_id: UUID, dims: QueryDimensions) -> DataQualityResponse:
        try:
            result = await self._store.fetch_result(
                deployment_id, GROUP_DATA_QUALITY, dims.window.value
            )
            alerts = await self._banners(deployment_id, dims.severity, group=GROUP_DATA_QUALITY)
            profile = await self._profile_status(deployment_id)
        except MonitoringStoreUnavailable:
            return DataQualityResponse(state=SectionState.UNAVAILABLE)
        if result is None:
            return DataQualityResponse(
                state=SectionState.EMPTY, profile_status=profile, alerts=alerts
            )
        rows = _data_quality_rows(result.values, dims.feature)
        return DataQualityResponse(
            state=SectionState.OK, profile_status=profile, features=rows, alerts=alerts
        )

    async def feature_drift(
        self, deployment_id: UUID, dims: QueryDimensions
    ) -> FeatureDriftResponse:
        try:
            drift = await self._store.fetch_result(
                deployment_id, GROUP_FEATURE_DRIFT, dims.window.value
            )
            multivariate = await self._store.fetch_result(
                deployment_id, GROUP_MULTIVARIATE, dims.window.value
            )
            alerts = await self._banners(deployment_id, dims.severity, group=GROUP_FEATURE_DRIFT)
            profile = await self._profile_status(deployment_id)
        except MonitoringStoreUnavailable:
            return FeatureDriftResponse(state=SectionState.UNAVAILABLE)

        panel = _multivariate_panel(multivariate)
        if drift is None:
            return FeatureDriftResponse(
                state=SectionState.EMPTY,
                profile_status=profile,
                multivariate=panel,
                alerts=alerts,
            )
        ranked = sorted(_drifted_features(drift.values), key=lambda d: d.psi, reverse=True)
        return FeatureDriftResponse(
            state=SectionState.OK,
            profile_status=profile,
            features=ranked,
            selected=_feature_detail(drift.values, dims.feature),
            multivariate=panel,
            alerts=alerts,
        )

    async def reference_profile(
        self, deployment_id: UUID, dims: QueryDimensions
    ) -> ReferenceProfileResponse:
        try:
            profile = await self._store.fetch_profile(deployment_id)
            status = await self._profile_status(deployment_id)
        except MonitoringStoreUnavailable:
            return ReferenceProfileResponse(state=SectionState.UNAVAILABLE)
        if profile is None:
            return ReferenceProfileResponse(state=SectionState.EMPTY, profile_status=status)
        selected = None
        if dims.feature is not None:
            entry = profile.features.get(dims.feature)
            if entry is not None:
                selected = _reference_feature(entry)
        return ReferenceProfileResponse(
            state=SectionState.OK,
            profile_status=status,
            baseline_label=profile.baseline_label,
            computed_at=profile.computed_at,
            features=sorted(profile.features),
            feature=selected,
        )

    async def alerts(self, deployment_id: UUID, dims: QueryDimensions) -> AlertsResponse:
        try:
            stored = await self._store.fetch_alerts(deployment_id)
            profile = await self._profile_status(deployment_id)
        except MonitoringStoreUnavailable:
            return AlertsResponse(state=SectionState.UNAVAILABLE)
        matching = [a for a in stored if _severity_matches(a.severity, dims.severity)]
        return AlertsResponse(
            state=SectionState.OK,
            profile_status=profile,
            groups=_group_alerts(matching),
        )

    async def traces(
        self,
        deployment_id: UUID,
        dims: QueryDimensions,
        *,
        limit: int = TRACES_DEFAULT_LIMIT,
        offset: int = 0,
    ) -> TracesResponse:
        try:
            start, end = self._window_bounds(dims.window)
            events = await self._store.fetch_events(deployment_id, start, end)
            profile = await self._profile_status(deployment_id)
        except MonitoringStoreUnavailable:
            return TracesResponse(state=SectionState.UNAVAILABLE, limit=limit, offset=offset)
        ordered = sorted(events, key=lambda e: e.ts, reverse=True)
        page = ordered[offset : offset + limit]
        return TracesResponse(
            state=SectionState.OK if ordered else SectionState.EMPTY,
            profile_status=profile,
            rows=[_trace_row(e) for e in page],
            total=len(ordered),
            limit=limit,
            offset=offset,
        )

    async def _runtime(
        self, deployment_id: UUID, dims: QueryDimensions
    ) -> tuple[_Rollup, list[Series]]:
        start, end = self._window_bounds(dims.window)
        events = await self._store.fetch_events(deployment_id, start, end)
        bucket = _bucket_seconds(dims)
        n_buckets = math.ceil(_WINDOW_SECONDS[dims.window] / bucket)
        return _rollup(events), _runtime_series(events, start, bucket, n_buckets)

    async def _previous_rollup(self, deployment_id: UUID, dims: QueryDimensions) -> _Rollup | None:
        if dims.compare is not Compare.PREVIOUS:
            return None
        _, current_start = self._window_bounds(dims.window)
        duration = timedelta(seconds=_WINDOW_SECONDS[dims.window])
        prev_start = current_start - 2 * duration
        prev_end = current_start - duration
        return _rollup(await self._store.fetch_events(deployment_id, prev_start, prev_end))

    async def _banners(
        self, deployment_id: UUID, severity: SeverityFilter, *, group: str
    ) -> list[AlertBanner]:
        alerts = await self._store.fetch_alerts(deployment_id)
        return [
            _alert_banner(a)
            for a in sorted(alerts, key=_banner_order)
            if a.group == group and _severity_matches(a.severity, severity)
        ]

    async def _profile_status(self, deployment_id: UUID) -> ProfileStatus:
        raw = await self._store.profile_status(deployment_id)
        return ProfileStatus.PLACEHOLDER if raw != ProfileStatus.READY else ProfileStatus.READY


def _banner_order(alert: StoredAlert) -> tuple[int, float]:
    rank = 0 if alert.severity == Severity.CRITICAL else 1
    last_seen = alert.last_seen.timestamp() if alert.last_seen else 0.0
    return rank, -last_seen


def _group_alerts(alerts: list[StoredAlert]) -> list[AlertGroup]:
    by_group: dict[str, list[AlertBanner]] = {}
    for alert in sorted(alerts, key=_banner_order):
        by_group.setdefault(alert.group, []).append(_alert_banner(alert))
    known = [
        AlertGroup(group=group, alerts=by_group.pop(group))
        for group in _ALERT_GROUP_ORDER
        if group in by_group
    ]
    extra = [AlertGroup(group=group, alerts=items) for group, items in by_group.items()]
    return known + extra


def _drifted_features(values: dict) -> list[DriftedFeature]:
    features = values.get("features", {})
    drifted: list[DriftedFeature] = []
    for name, entry in features.items():
        psi = entry.get("psi")
        if psi is None:
            continue
        drifted.append(
            DriftedFeature(
                feature=name,
                psi=float(psi),
                severity=Severity(entry.get("status", Severity.OK)),
            )
        )
    return drifted


def _maybe_float(value: float | int | str | None) -> float | None:
    return None if value is None else float(value)


def _feature_detail(values: dict, feature: str | None) -> FeatureDriftDetail | None:
    if feature is None:
        return None
    entry = values.get("features", {}).get(feature)
    if entry is None:
        return None
    return FeatureDriftDetail(
        feature=feature,
        psi=_maybe_float(entry.get("psi")),
        status=Severity(entry.get("status", Severity.OK)),
        distribution=_distribution(entry.get("distribution")),
        psi_over_time=_psi_series(feature, entry.get("psi_series")),
    )


def _distribution(raw: dict | None) -> FeatureDistribution | None:
    if not raw:
        return None
    bins = [
        DistributionBin(
            label=str(b.get("label")),
            reference=_maybe_float(b.get("reference")),
            current=_maybe_float(b.get("current")),
        )
        for b in raw.get("bins", [])
    ]
    return FeatureDistribution(kind=raw.get("kind", "numeric"), bins=bins)


def _psi_series(feature: str, raw: list | None) -> Series | None:
    if not raw:
        return None
    points = [SeriesPoint(t=p["t"], value=_maybe_float(p.get("value"))) for p in raw]
    return Series(key="psi", label=f"PSI · {feature}", points=points)


def _points(raw: list) -> list[PcaPoint]:
    return [PcaPoint(x=float(p[0]), y=float(p[1])) for p in raw]


def _multivariate_panel(result: StoredMetricResult | None) -> MultivariatePanel:
    if result is None:
        return MultivariatePanel(state=SectionState.EMPTY)
    values = result.values
    projection = values.get("projection", {})
    return MultivariatePanel(
        state=SectionState.OK,
        status=Severity(values.get("status", result.severity or Severity.OK)),
        shift_value=_maybe_float(values.get("shift_value")),
        shift_metric=values.get("shift_metric"),
        explained_variance=[float(v) for v in values.get("explained_variance", [])],
        feature_psi=sorted(_drifted_features(values), key=lambda d: d.psi, reverse=True),
        reference_projection=_points(projection.get("reference", [])),
        current_projection=_points(projection.get("current", [])),
    )


def _reference_feature(entry: ReferenceFeatureProfile) -> ReferenceProfileFeature:
    return ReferenceProfileFeature(
        feature=entry.feature,
        kind=entry.kind,
        summary=entry.summary,
        bin_edges=entry.bin_edges,
        histogram=entry.histogram,
        categories=entry.categories,
        category_probabilities=entry.category_probabilities,
    )


def _data_quality_rows(values: dict, feature: str | None) -> list[DataQualityFeatureRow]:
    features = values.get("features", {})
    rows: list[DataQualityFeatureRow] = []
    for name, entry in features.items():
        if feature is not None and name != feature:
            continue
        rows.append(
            DataQualityFeatureRow(
                feature=name,
                missing_rate=entry.get("missing_rate"),
                type_error_rate=entry.get("type_error_rate"),
                range_unseen_rate=entry.get("range_unseen_rate"),
                status=Severity(entry.get("status", Severity.OK)),
            )
        )
    return rows


def _overview_cards(
    rollup: _Rollup,
    previous: _Rollup | None,
    dims: QueryDimensions,
    alerts: list[StoredAlert],
    criticals: list[StoredAlert],
    drifted_names: list[str],
) -> list[Card]:
    kind = dims.compare if previous is not None else None
    return [
        Card(
            key="requests",
            label="Requests",
            value=rollup.request_count,
            delta=_delta(rollup.request_count, previous.request_count) if previous else None,
            delta_kind=kind,
        ),
        Card(
            key="error_rate",
            label="Error rate",
            value=rollup.error_rate,
            unit="ratio",
            delta=_delta(rollup.error_rate, previous.error_rate) if previous else None,
            delta_kind=kind,
        ),
        Card(
            key="latency_p95",
            label="Latency p95",
            value=rollup.latency_p95_ms,
            unit="ms",
            delta=_delta(rollup.latency_p95_ms, previous.latency_p95_ms) if previous else None,
            delta_kind=kind,
        ),
        Card(
            key="active_alerts",
            label="Active alerts",
            value=len(alerts),
            critical_count=len(criticals),
        ),
        Card(
            key="drifted_features",
            label="Drifted features",
            value=len(drifted_names),
            feature_names=drifted_names,
        ),
    ]


def _trace_row(event: InferenceEvent) -> TraceRow:
    return TraceRow(
        event_id=event.event_id,
        ts=event.ts,
        features_summary=_preview(event.inputs),
        prediction=_preview(event.output),
        latency_ms=event.latency_ms,
        status=event.status,
        status_code=event.status_code,
    )


def _preview(raw: str | None) -> str | None:
    """Condense a stored inputs/output JSON string into one bounded table-cell summary."""
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except ValueError:
        return _truncate(raw, _TRACE_SUMMARY_MAX_LEN)
    if isinstance(parsed, dict):
        items = list(parsed.items())[:_TRACE_SUMMARY_MAX_KEYS]
        summary = ", ".join(f"{key}={_scalar(value)}" for key, value in items)
        if len(parsed) > _TRACE_SUMMARY_MAX_KEYS:
            summary += ", …"
        return _truncate(summary, _TRACE_SUMMARY_MAX_LEN)
    return _truncate(_scalar(parsed), _TRACE_SUMMARY_MAX_LEN)


def _scalar(value: object) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, (str, int)):
        return str(value)
    return json.dumps(value, separators=(",", ":"))


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"
