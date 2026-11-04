from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs
from uuid import UUID

import httpx
import pytest
import respx

from luml_satellite.monitoring import MonitoringQueryService, QueryDimensions
from luml_satellite.monitoring.dashboard.schemas import Compare, Granularity, SortOrder, TraceSort
from luml_satellite.monitoring.storage.greptime_query import GreptimeQueryStore
from luml_satellite.monitoring.storage.query_store import InferenceEvent, InMemoryMonitoringStore

_DEP = UUID(int=1)
_START = datetime(2026, 9, 1, tzinfo=UTC)
_END = _START + timedelta(days=30)
_URL = "http://gt:4000/v1/sql"


def _records(columns: list[str], rows: list[list[Any]]) -> dict[str, Any]:
    return {
        "code": 0,
        "output": [
            {
                "records": {
                    "schema": {"column_schemas": [{"name": c} for c in columns]},
                    "rows": rows,
                }
            }
        ],
    }


def _sql(request: httpx.Request) -> str:
    return parse_qs(request.content.decode())["sql"][0]


@pytest.mark.parametrize("sort", list(TraceSort))
@pytest.mark.parametrize("order", list(SortOrder))
@respx.mock
async def test_event_page_orders_and_bounds_sql(sort: TraceSort, order: SortOrder) -> None:
    route = respx.post(_URL).respond(200, json=_records([], []))
    store = GreptimeQueryStore(host="gt")
    try:
        assert (
            await store.fetch_events(
                _DEP, _START, _END, limit=20, offset=40, sort=sort, order=order
            )
            == []
        )
        sql = _sql(route.calls.last.request)
        assert "LIMIT 20 OFFSET 40" in sql
        assert f"ORDER BY {sort.value}" in sql
        assert order.value.upper() in sql
        assert str(_DEP) in sql
        assert f"timestamp >= {int(_START.timestamp() * 1e9)}" in sql
        assert f"timestamp < {int(_END.timestamp() * 1e9)}" in sql
    finally:
        await store.aclose()


@respx.mock
async def test_default_event_read_is_bounded() -> None:
    route = respx.post(_URL).respond(200, json=_records([], []))
    store = GreptimeQueryStore(host="gt")
    try:
        await store.fetch_events(_DEP, _START, _END)
        assert "LIMIT 50 OFFSET 0" in _sql(route.calls.last.request)
    finally:
        await store.aclose()


@pytest.mark.parametrize("limit,offset", [(0, 0), (201, 0), (1, -1)])
async def test_invalid_page_is_rejected(limit: int, offset: int) -> None:
    store = GreptimeQueryStore(host="gt")
    with pytest.raises(ValueError):
        await store.fetch_events(_DEP, _START, _END, limit=limit, offset=offset)


@respx.mock
async def test_trace_lookup_filters_event_id_and_keeps_payload() -> None:
    attrs = {"inference.event_id": "ev'1", "inference.inputs": '{"x":1}'}
    route = respx.post(_URL).respond(
        200,
        json=_records(["timestamp", "span_attributes"], [[int(_START.timestamp() * 1e9), attrs]]),
    )
    store = GreptimeQueryStore(host="gt")
    try:
        event = await store.fetch_event(_DEP, _START, _END, "ev'1")
        assert event is not None and event.inputs == '{"x":1}'
        sql = _sql(route.calls.last.request)
        assert '["inference.event_id"]' in sql
        assert "= 'ev''1'" in sql
        assert "LIMIT 1" in sql
        assert str(_DEP) in sql
        assert "timestamp >=" in sql and "timestamp <" in sql
    finally:
        await store.aclose()


@respx.mock
async def test_count_query_returns_full_total_without_payloads() -> None:
    route = respx.post(_URL).respond(200, json=_records(["total"], [[123456]]))
    store = GreptimeQueryStore(host="gt")
    try:
        assert await store.count_events(_DEP, _START, _END) == 123456
        sql = _sql(route.calls.last.request)
        assert "COUNT(*)" in sql
        assert "SELECT timestamp, span_attributes" not in sql
        assert "LIMIT" not in sql
    finally:
        await store.aclose()


@respx.mock
async def test_runtime_queries_return_only_summaries_and_grouped_buckets() -> None:
    queries: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        sql = _sql(request)
        queries.append(sql)
        if "GROUP BY status" in sql:
            return httpx.Response(
                200,
                json=_records(
                    ["status", "status_code", "count"], [["success", 200, 2], ["error", 504, 1]]
                ),
            )
        if "GROUP BY bucket" in sql:
            return httpx.Response(
                200,
                json=_records(
                    ["bucket", "request_count", "success_count", "latency_p95_ms"],
                    [[0, 3, 2, 90.0]],
                ),
            )
        return httpx.Response(
            200,
            json=_records(
                [
                    "request_count",
                    "success_count",
                    "error_count",
                    "timeout_count",
                    "failed_inference_count",
                    "latency_p50_ms",
                    "latency_p95_ms",
                    "latency_max_ms",
                    "first_ts",
                    "last_ts",
                ],
                [
                    [
                        3,
                        2,
                        0,
                        1,
                        0,
                        20.0,
                        90.0,
                        90.0,
                        int(_START.timestamp() * 1e9),
                        int((_START + timedelta(seconds=10)).timestamp() * 1e9),
                    ]
                ],
            ),
        )

    respx.post(_URL).mock(side_effect=answer)
    store = GreptimeQueryStore(host="gt")
    try:
        summary = await store.fetch_runtime_summary(_DEP, _START, _END)
        assert summary.request_count == 3
        assert summary.success_rate == pytest.approx(2 / 3)
        assert summary.error_rate == pytest.approx(1 / 3)
        assert summary.latency_p50_ms == 20.0
        assert summary.timeout_count == 1
        assert summary.first_ts == _START
        assert summary.status_breakdown[0].count == 2
        assert summary.status_breakdown[1].status_code == 504
        buckets = await store.fetch_runtime_buckets(_DEP, _START, _END, _START, 60, 43200)
        assert buckets[0].request_count == 3
        assert buckets[0].latency_p95_ms == 90.0
        assert all(
            "inference.inputs" not in sql and "inference.output" not in sql for sql in queries
        )
        assert all("SELECT timestamp, span_attributes" not in sql for sql in queries)
        assert any("ROW_NUMBER() OVER" in sql for sql in queries)
        assert any("PARTITION BY bucket" in sql for sql in queries)
        assert any("WHEN bucket_index >= 43200 THEN 43199" in sql for sql in queries)
        assert any("rank = CEIL(total * 0.5)" in sql for sql in queries)
        assert any("rank = CEIL(total * 0.95)" in sql for sql in queries)
        assert all('["inference.status_code"]' in sql for sql in queries)
        assert all("status_code = 504" in sql for sql in queries if "is_timeout" in sql)
        assert any("GROUP BY status, status_code" in sql for sql in queries)
    finally:
        await store.aclose()


async def test_runtime_and_detail_never_fetch_event_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryMonitoringStore()
    store.add_event(InferenceEvent("e", _DEP, _START, "success", 200, 10.0))

    async def reject(*args: object, **kwargs: object) -> list[InferenceEvent]:
        raise AssertionError("runtime and trace detail must not fetch event pages")

    monkeypatch.setattr(store, "fetch_events", reject)
    service = MonitoringQueryService(store)
    dims = QueryDimensions(start=_START, end=_END)
    assert (await service.runtime(_DEP, dims)).request_count == 1
    assert (await service.trace_detail(_DEP, dims, "e")).trace is not None


async def test_empty_page_retains_total_and_window_is_half_open() -> None:
    store = InMemoryMonitoringStore()
    store.add_event(InferenceEvent("inside", _DEP, _START, "success", 200, 10.0))
    store.add_event(InferenceEvent("end", _DEP, _END, "success", 200, 10.0))
    store.add_event(InferenceEvent("other", UUID(int=2), _START, "success", 200, 10.0))
    service = MonitoringQueryService(store)
    dims = QueryDimensions(start=_START, end=_END)
    page = await service.traces(_DEP, dims, offset=100)
    assert page.total == 1 and page.rows == [] and page.state == "ok"
    assert (await service.trace_detail(_DEP, dims, "end")).trace is None
    assert (await service.trace_detail(_DEP, dims, "other")).trace is None


@respx.mock
async def test_missing_event_table_returns_empty_summaries_and_series() -> None:
    respx.post(_URL).respond(400, json={"code": 4001, "error": "Table not found: inference_events"})
    store = GreptimeQueryStore(host="gt")
    try:
        assert await store.count_events(_DEP, _START, _END) == 0
        assert await store.fetch_event(_DEP, _START, _END, "missing") is None
        assert await store.fetch_runtime_buckets(_DEP, _START, _END, _START, 60, 43200) == {}
        service = MonitoringQueryService(store)
        result = await service.runtime(
            _DEP, QueryDimensions(start=_START, end=_END, granularity=Granularity.DAY)
        )
        assert result.request_count == 0
        assert result.latency_p50_ms is None
        assert result.latency_p95_ms is None
        assert result.status_breakdown == []
        assert len(result.series[0].points) == 30
        assert all(point.value == 0.0 for point in result.series[0].points)
        assert all(point.value is None for series in result.series[1:] for point in series.points)
    finally:
        await store.aclose()


@respx.mock
async def test_query_outage_keeps_sections_unavailable() -> None:
    respx.post(_URL).mock(side_effect=httpx.ConnectError("refused"))
    store = GreptimeQueryStore(host="gt")
    try:
        service = MonitoringQueryService(store)
        dims = QueryDimensions(start=_START, end=_END)
        assert (await service.runtime(_DEP, dims)).state == "unavailable"
        assert (await service.overview(_DEP, dims)).state == "unavailable"
        assert (await service.traces(_DEP, dims)).state == "unavailable"
        assert (await service.trace_detail(_DEP, dims, "e")).state == "unavailable"
    finally:
        await store.aclose()


async def test_compare_series_keeps_events_beyond_current_chart_span() -> None:
    store = InMemoryMonitoringStore()
    store.add_event(
        InferenceEvent("baseline", _DEP, _START + timedelta(minutes=90), "error", 500, 25.0)
    )
    service = MonitoringQueryService(store)
    result = await service.runtime(
        _DEP,
        QueryDimensions(
            start=_END,
            end=_END + timedelta(hours=1),
            granularity=Granularity.HOUR,
            compare=Compare.CUSTOM,
            compare_start=_START,
            compare_end=_START + timedelta(hours=2),
        ),
    )
    assert result.baseline is not None and result.baseline.request_count == 1
    assert result.series[0].baseline is not None
    assert [p.value for p in result.series[0].baseline] == [1.0]
    assert result.series[2].baseline is not None
    assert [p.value for p in result.series[2].baseline] == [25.0]
