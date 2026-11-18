from collections.abc import Iterator

import pytest
import respx
from respx import MockResponse

from luml_satellite.monitoring.ingest.testing import FakeTelemetry


@pytest.fixture()
def fake_telemetry() -> Iterator[FakeTelemetry]:
    telemetry = FakeTelemetry()
    yield telemetry
    telemetry.shutdown()


@pytest.fixture()
def mock_model_server(httpx2_mock: respx.MockRouter) -> Iterator[respx.MockRouter]:
    httpx2_mock.get(url__regex=r"http://sat-[^/]+:\d+/healthz").mock(
        return_value=MockResponse(200, json={"status": "healthy"})
    )
    httpx2_mock.get(url__regex=r"http://sat-[^/]+:\d+/manifest").mock(
        return_value=MockResponse(200, json={"name": "test-model", "version": "1.0"})
    )
    httpx2_mock.get(url__regex=r"http://sat-[^/]+:\d+/openapi\.json").mock(
        return_value=MockResponse(200, json={"openapi": "3.0.0", "paths": {}})
    )
    httpx2_mock.post(url__regex=r"http://sat-[^/]+:\d+/compute").mock(
        return_value=MockResponse(200, json={"prediction": 42})
    )
    yield httpx2_mock
