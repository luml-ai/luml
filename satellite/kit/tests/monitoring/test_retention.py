"""Retention: the monitoring tables must not grow forever."""

import logging

import httpx
import pytest
import respx

from luml_satellite.monitoring.storage.greptime import (
    ALERTS_TABLE,
    INFERENCE_EVENTS_TABLE,
    LEGACY_METRIC_TABLES,
    OTEL_TRACES_TABLE,
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


class TestRetention:
    @respx.mock
    async def test_tables_are_created_with_their_retention(self) -> None:
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
    async def test_raw_events_are_kept_shortest(self) -> None:
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
    async def test_every_collector_table_gets_its_retention(self) -> None:
        """The collector's own tables were the gap: traces and the legacy metric tables grew
        forever while the docstring claimed otherwise. Now every table is covered."""
        route = respx.post(_URL).mock(return_value=httpx.Response(200, json={"output": []}))
        store = GreptimeMonitoringStore(
            host="gt",
            port=4000,
            events_ttl="30d",
            results_ttl="30d",
            alerts_ttl="30d",
            traces_ttl="30d",
            metrics_ttl="7d",
        )

        await store._ensure_tables()

        sql = " ".join(_statements(route))
        assert f"ALTER TABLE {OTEL_TRACES_TABLE} SET 'ttl' = '30d'" in sql
        for table in LEGACY_METRIC_TABLES:
            # nothing writes these any more; a short TTL drains what a stand accumulated
            assert f"ALTER TABLE {table} SET 'ttl' = '7d'" in sql
        await store.aclose()

    @respx.mock
    async def test_a_failing_alter_does_not_stop_the_worker(self) -> None:
        """Retention is best-effort: an old GreptimeDB or a missing table must not block writes."""
        failed = {"alter": False}

        def answer(request: httpx.Request) -> httpx.Response:
            statement = request.content.decode()
            if "ALTER+TABLE" in statement and not failed["alter"]:
                failed["alter"] = True
                return httpx.Response(500, text="boom")
            return httpx.Response(200, json={"output": []})

        respx.post(_URL).mock(side_effect=answer)
        store = GreptimeMonitoringStore(
            host="gt", port=4000, results_ttl="30d", alerts_ttl="30d", traces_ttl="30d"
        )

        await store._ensure_tables()  # must not raise

        await store.aclose()

    @respx.mock
    async def test_without_a_setting_nothing_is_altered(self) -> None:
        route = respx.post(_URL).mock(return_value=httpx.Response(200, json={"output": []}))
        store = GreptimeMonitoringStore(host="gt", port=4000)

        await store._ensure_tables()

        sql = " ".join(_statements(route))
        assert "ALTER" not in sql.upper()
        await store.aclose()

    @respx.mock
    async def test_a_table_the_collector_has_not_created_gets_its_retention_once_it_appears(
        self,
    ) -> None:
        """On a fresh database no collector table exists at Agent start.

        Retention used to be applied only at start, so a fresh stand's traces kept
        growing until the Agent happened to restart. The missing table is remembered
        and the ALTER retried until GreptimeDB has it.
        """
        exists = {"events": False}

        def answer(request: httpx.Request) -> httpx.Response:
            sql = _statements_of(request)
            if f"ALTER TABLE {INFERENCE_EVENTS_TABLE}" in sql and not exists["events"]:
                return httpx.Response(
                    400,
                    json={
                        "code": 4001,
                        "error": f"Table not found: greptime.public.{INFERENCE_EVENTS_TABLE}",
                    },
                )
            return httpx.Response(200, json={"output": []})

        route = respx.post(_URL).mock(side_effect=answer)
        store = GreptimeMonitoringStore(host="gt", port=4000, events_ttl="7d", ttl_retry_seconds=0)

        await store._ensure_tables()
        assert store._pending_ttl == {INFERENCE_EVENTS_TABLE: "7d"}

        exists["events"] = True  # the first span arrived; the collector created the table
        await store._ensure_tables()

        alters = [s for s in _statements(route) if f"ALTER TABLE {INFERENCE_EVENTS_TABLE}" in s]
        assert len(alters) == 2
        assert store._pending_ttl == {}
        await store.aclose()

    @respx.mock
    async def test_a_missing_collector_table_is_not_a_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Eight lines of WARNING per start on every fresh stand hid real storage errors."""
        respx.post(_URL).mock(side_effect=_traces_table_missing)
        store = GreptimeMonitoringStore(host="gt", port=4000, traces_ttl="30d")

        with caplog.at_level(logging.DEBUG, logger="satellite"):
            await store._ensure_tables()

        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert warnings == []
        assert any("waits for the collector" in r.getMessage() for r in caplog.records)
        await store.aclose()

    @respx.mock
    async def test_retries_are_rate_limited(self) -> None:
        """A pending table is asked about once per interval, not on every store call."""
        route = respx.post(_URL).mock(side_effect=_traces_table_missing)
        store = GreptimeMonitoringStore(
            host="gt", port=4000, traces_ttl="30d", ttl_retry_seconds=3600
        )

        await store._ensure_tables()
        await store._ensure_tables()
        await store._ensure_tables()

        alters = [s for s in _statements(route) if "ALTER TABLE otel_traces" in s]
        # one at start, one retry on the first later call, then the interval holds
        assert len(alters) == 2
        await store.aclose()

    @respx.mock
    async def test_legacy_metric_tables_are_not_asked_about_again(self) -> None:
        """Nothing creates them any more; a fresh stand would retry five ALTERs forever."""

        def nothing_exists_yet(request: httpx.Request) -> httpx.Response:
            if "ALTER TABLE" in _statements_of(request):
                return httpx.Response(400, json={"code": 4001, "error": "Table not found: x"})
            return httpx.Response(200, json={"output": []})

        route = respx.post(_URL).mock(side_effect=nothing_exists_yet)
        store = GreptimeMonitoringStore(
            host="gt", port=4000, events_ttl="7d", metrics_ttl="7d", ttl_retry_seconds=0
        )

        await store._ensure_tables()
        await store._ensure_tables()  # the retry pass

        assert set(store._pending_ttl) == {INFERENCE_EVENTS_TABLE}
        legacy_alters = [
            s
            for s in _statements(route)
            if any(f"ALTER TABLE {t}" in s for t in LEGACY_METRIC_TABLES)
        ]
        assert len(legacy_alters) == len(LEGACY_METRIC_TABLES)  # once each, never again
        await store.aclose()


def _statements_of(request: httpx.Request) -> str:
    from urllib.parse import unquote_plus

    return unquote_plus(request.content.decode()) if request.content else ""


def _traces_table_missing(request: httpx.Request) -> httpx.Response:
    """The collector has not created ``otel_traces`` yet; everything else works."""
    if "ALTER TABLE otel_traces" in _statements_of(request):
        return httpx.Response(
            400, json={"code": 4001, "error": "Table not found: greptime.public.otel_traces"}
        )
    return httpx.Response(200, json={"output": []})
