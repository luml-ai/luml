"""Acknowledging an alert: the third state of the lifecycle the spec asks for."""

import uuid
from datetime import UTC, datetime

import httpx
import respx
from tests.support import FIXED_NOW, ago

from agent.monitoring import MonitoringQueryService, QueryDimensions
from agent.monitoring.greptime_query import GreptimeQueryStore
from agent.monitoring.models import Alert, AlertState, MonitoredDeployment, TimeWindow
from agent.monitoring.query_store import InMemoryMonitoringStore, StoredAlert
from agent.monitoring.registry import default_registry
from agent.monitoring.store import InMemoryMonitoringStore as WorkerStore
from agent.monitoring.worker import MonitoringWorker
from agent.schemas.monitoring_query import SectionState, Severity, Window

_URL = "http://gt:4000/v1/sql"
_DEP = uuid.UUID("019f46e3-3aa1-7672-96a9-8c6d98ab25cd")


def _stored(metric: str = "feature_drift:income", state: str = "open") -> StoredAlert:
    return StoredAlert(
        deployment_id=_DEP,
        group=metric.split(":")[0],
        metric=metric,
        feature="income",
        severity=Severity.CRITICAL,
        current_value=0.42,
        threshold=0.25,
        state=state,
        first_seen=ago(3600),
        last_seen=ago(60),
    )


def _service(store: InMemoryMonitoringStore) -> MonitoringQueryService:
    return MonitoringQueryService(store, clock=lambda: FIXED_NOW)


async def test_acknowledging_returns_the_list_as_it_now_stands() -> None:
    store = InMemoryMonitoringStore()
    store.add_alert(_stored())

    result = await _service(store).acknowledge_alert(
        _DEP, "feature_drift:income", QueryDimensions(window=Window.H24)
    )

    assert result.state is SectionState.OK
    alert = result.groups[0].alerts[0]
    assert alert.state == "acknowledged"
    # the numbers are untouched: acknowledging says "seen", not "fixed"
    assert alert.current_value == 0.42
    assert alert.severity is Severity.CRITICAL


async def test_acknowledging_an_unknown_alert_is_harmless() -> None:
    store = InMemoryMonitoringStore()
    store.add_alert(_stored())

    result = await _service(store).acknowledge_alert(
        _DEP, "runtime:error_rate", QueryDimensions(window=Window.H24)
    )

    assert [a.state for g in result.groups for a in g.alerts] == ["open"]


async def test_an_acknowledged_alert_stays_acknowledged_while_it_keeps_firing() -> None:
    """The worker must not undo a human's acknowledgement on the next window."""
    store = WorkerStore()
    alert = Alert(
        deployment_id="dep",
        metric="runtime:error_rate",
        current_value=0.2,
        threshold=0.05,
        severity=Severity.CRITICAL,
        state=AlertState.ACKNOWLEDGED,
        first_seen=datetime(2026, 1, 1, 11, 55, tzinfo=UTC),
        last_seen=datetime(2026, 1, 1, 11, 55, tzinfo=UTC),
    )
    store.alerts[("dep", "runtime:error_rate")] = alert
    window = TimeWindow(
        start=datetime(2026, 1, 1, 11, 55, tzinfo=UTC),
        end=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )

    worker = MonitoringWorker(
        store=store,
        registry=default_registry(),
        provider=lambda: [MonitoredDeployment("dep", profile={})],
        window_seconds=300.0,
        interval_seconds=60.0,
    )
    await worker._reconcile_alerts(
        "dep",
        "runtime",
        [alert_signal()],
        window,
        {"runtime:error_rate": alert},
    )

    assert store.alerts[("dep", "runtime:error_rate")].state == AlertState.ACKNOWLEDGED


def alert_signal():  # noqa: ANN201
    from agent.monitoring.models import AlertSignal

    return AlertSignal("error_rate", 0.3, 0.05, Severity.CRITICAL)


@respx.mock
async def test_acknowledging_rewrites_the_alert_row_in_place() -> None:
    """Same key and same last_seen: the row is replaced, the alert's timeline is intact."""
    columns = [
        "deployment_id",
        "metric",
        "current_value",
        "threshold",
        "severity",
        "state",
        "first_seen",
        "last_seen",
    ]
    row = [
        str(_DEP),
        "feature_drift:income",
        0.42,
        0.25,
        "critical",
        "open",
        1_767_225_600_000,
        1_767_225_900_000,
    ]
    statements: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        from urllib.parse import parse_qs

        sql = parse_qs(request.content.decode())["sql"][0]
        statements.append(sql)
        if sql.startswith("SELECT"):
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "output": [
                        {
                            "records": {
                                "schema": {"column_schemas": [{"name": c} for c in columns]},
                                "rows": [row],
                            }
                        }
                    ],
                },
            )
        return httpx.Response(200, json={"code": 0, "output": [{"affectedrows": 1}]})

    respx.post(_URL).mock(side_effect=handler)
    store = GreptimeQueryStore(host="gt", port=4000)

    assert await store.acknowledge_alert(_DEP, "feature_drift:income") is True

    insert = next(s for s in statements if s.startswith("INSERT"))
    assert "'acknowledged'" in insert
    assert "'feature_drift:income'" in insert
    # the worker's vocabulary, not the API's: it reads this table too
    assert "'critical'" in insert
    await store.aclose()


@respx.mock
async def test_nothing_to_acknowledge_is_not_an_error() -> None:
    respx.post(_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "output": [
                    {"records": {"schema": {"column_schemas": []}, "rows": []}}
                ],
            },
        )
    )
    store = GreptimeQueryStore(host="gt", port=4000)

    assert await store.acknowledge_alert(_DEP, "runtime:error_rate") is False
    await store.aclose()
