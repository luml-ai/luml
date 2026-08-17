"""Retention: the monitoring tables must not grow forever."""

import httpx
import respx

from agent.monitoring.greptime import (
    ALERTS_TABLE,
    INFERENCE_EVENTS_TABLE,
    RESULTS_TABLE,
    GreptimeMonitoringStore,
)

_URL = "http://gt:4000/v1/sql"


def _statements(route: respx.Route) -> list[str]:
    """The SQL each call carried, url-decoded back into something readable."""
    from urllib.parse import unquote_plus

    return [
        unquote_plus(call.request.content.decode()) if call.request.content else ""
        for call in route.calls
    ]


@respx.mock
async def test_tables_are_created_with_their_retention() -> None:
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json={"output": []}))
    store = GreptimeMonitoringStore(
        host="gt", port=4000, events_ttl="7d", results_ttl="30d", alerts_ttl="30d"
    )

    await store._ensure_tables()

    sql = " ".join(_statements(route))
    # the fresh table declares it, the one that already exists is altered into it
    assert f"CREATE TABLE IF NOT EXISTS {RESULTS_TABLE}" in sql
    assert "WITH (ttl = '30d')" in sql
    assert f"ALTER TABLE {RESULTS_TABLE} SET 'ttl' = '30d'" in sql
    await store.aclose()


@respx.mock
async def test_raw_events_are_kept_shortest() -> None:
    """The traces table holds the model's own inputs and predictions."""
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json={"output": []}))
    store = GreptimeMonitoringStore(
        host="gt", port=4000, events_ttl="7d", results_ttl="30d", alerts_ttl="30d"
    )

    await store._ensure_tables()

    sql = " ".join(_statements(route))
    assert f"ALTER TABLE {INFERENCE_EVENTS_TABLE} SET 'ttl' = '7d'" in sql
    assert f"ALTER TABLE {ALERTS_TABLE} SET 'ttl' = '30d'" in sql
    await store.aclose()


@respx.mock
async def test_a_failing_alter_does_not_stop_the_worker() -> None:
    """Retention is best-effort: an old GreptimeDB or a missing table must not block writes."""
    respx.post(_URL).mock(
        side_effect=[
            httpx.Response(200, json={"output": []}),  # create results
            httpx.Response(200, json={"output": []}),  # create alerts
            httpx.Response(200, json={"output": []}),  # create failures
            httpx.Response(500, text="boom"),  # alter results
            httpx.Response(200, json={"output": []}),
            httpx.Response(200, json={"output": []}),
        ]
    )
    store = GreptimeMonitoringStore(host="gt", port=4000, results_ttl="30d", alerts_ttl="30d")

    await store._ensure_tables()  # must not raise

    await store.aclose()


@respx.mock
async def test_without_a_setting_nothing_is_altered() -> None:
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json={"output": []}))
    store = GreptimeMonitoringStore(host="gt", port=4000)

    await store._ensure_tables()

    sql = " ".join(_statements(route))
    assert "ALTER" not in sql.upper()
    await store.aclose()
