from uuid import UUID

import httpx2
import pytest

from luml_satellite.monitoring.compute.models import TimeWindow
from luml_satellite.monitoring.storage.greptime import GreptimeMonitoringStore
from luml_satellite.monitoring.storage.greptime_query import GreptimeQueryStore
from tests.support import ago, now_dt


@pytest.mark.parametrize("store_type", [GreptimeMonitoringStore, GreptimeQueryStore])
def test_store_credentials_must_be_configured_together(
    store_type: type[GreptimeMonitoringStore] | type[GreptimeQueryStore],
) -> None:
    with pytest.raises(ValueError, match="username and password"):
        store_type(username="monitoring")


async def test_worker_store_sends_basic_auth_credentials() -> None:
    requests: list[httpx2.Request] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, json={"code": 0, "output": []})

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(respond))
    store = GreptimeMonitoringStore(
        client=client,
        username="monitoring",
        password="secret",
    )

    await store.read_events("deployment", TimeWindow(start=ago(300), end=now_dt()))

    assert requests[0].headers["Authorization"] == "Basic bW9uaXRvcmluZzpzZWNyZXQ="
    await client.aclose()


async def test_query_store_sends_basic_auth_credentials() -> None:
    requests: list[httpx2.Request] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, json={"code": 0, "output": []})

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(respond))
    store = GreptimeQueryStore(
        client=client,
        username="monitoring",
        password="secret",
    )

    await store.fetch_events(
        deployment_id=UUID("10000000-0000-0000-0000-000000000001"),
        start=ago(300),
        end=now_dt(),
    )

    assert requests[0].headers["Authorization"] == "Basic bW9uaXRvcmluZzpzZWNyZXQ="
    await client.aclose()
