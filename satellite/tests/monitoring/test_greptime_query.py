from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import pytest
import respx

from agent.monitoring.greptime_query import GreptimeQueryStore
from agent.monitoring.query_store import MonitoringStoreUnavailable

_URL = "http://gt:4000/v1/sql"
_DEP = UUID("019f46e3-3aa1-7672-96a9-8c6d98ab25cd")


def _store() -> GreptimeQueryStore:
    return GreptimeQueryStore(host="gt", port=4000)


def _records(columns: list[str], rows: list[list]) -> dict:
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


@respx.mock
async def test_fetch_events_parses_span_attributes() -> None:
    ns = int(datetime(2026, 7, 9, 20, 30, tzinfo=UTC).timestamp() * 1_000_000_000)
    attrs = {
        "inference.deployment_id": str(_DEP),
        "inference.event_id": "ev-1",
        "inference.status": "success",
        "inference.latency_ms": 12.5,
        "inference.trace_id": "t1",
        "inference.inputs": '{"x": 1}',
        "inference.output": '{"y": 2}',
    }
    body = _records(["timestamp", "span_attributes"], [[ns, attrs]])
    respx.post(_URL).mock(return_value=httpx.Response(200, json=body))

    store = _store()
    end = datetime.now(UTC)
    events = await store.fetch_events(_DEP, end - timedelta(days=5), end)

    assert len(events) == 1
    e = events[0]
    assert e.deployment_id == _DEP
    assert e.event_id == "ev-1"
    assert e.status == "success"
    assert e.status_code == 200
    assert e.latency_ms == 12.5
    assert e.trace_id == "t1"
    assert e.inputs == '{"x": 1}'
    await store.aclose()


@respx.mock
async def test_describe_deployment_uses_max_timestamp() -> None:
    ns = int(datetime(2026, 7, 9, 20, 30, tzinfo=UTC).timestamp() * 1_000_000_000)
    body = _records(["max(timestamp)"], [[ns]])
    respx.post(_URL).mock(return_value=httpx.Response(200, json=body))

    store = _store()
    desc = await store.describe_deployment(_DEP)

    assert desc is not None
    assert desc.deployment_id == _DEP
    assert desc.last_prediction_at == datetime(2026, 7, 9, 20, 30, tzinfo=UTC)
    await store.aclose()


@respx.mock
async def test_describe_deployment_none_when_no_events() -> None:
    body = _records(["max(timestamp)"], [[None]])
    respx.post(_URL).mock(return_value=httpx.Response(200, json=body))
    store = _store()
    assert await store.describe_deployment(_DEP) is None
    await store.aclose()


@respx.mock
async def test_missing_table_degrades_gracefully() -> None:
    # GreptimeDB returns HTTP 400 + non-zero code when a materialized table is absent.
    respx.post(_URL).mock(
        return_value=httpx.Response(
            400, json={"code": 4001, "error": "Table not found: public.monitoring_results"}
        )
    )
    store = _store()
    assert await store.fetch_result(_DEP, "feature_drift", "24h") is None
    assert await store.fetch_alerts(_DEP) == []
    await store.aclose()


@respx.mock
async def test_connection_error_is_store_unavailable() -> None:
    respx.post(_URL).mock(side_effect=httpx.ConnectError("refused"))
    store = _store()
    with pytest.raises(MonitoringStoreUnavailable):
        await store.fetch_events(_DEP, datetime.now(UTC) - timedelta(days=1), datetime.now(UTC))
    await store.aclose()
