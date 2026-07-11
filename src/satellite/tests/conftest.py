import os

# agent.settings.Settings requires SATELLITE_TOKEN at import time; provide a
# dummy so the agent package can be imported under test.
os.environ.setdefault("SATELLITE_TOKEN", "test-token")

import httpx
import pytest
import respx

from agent.clients.model_server_client import ModelServerClient
from agent.monitoring.testing import FakeTelemetry


@pytest.fixture()
def fake_telemetry() -> FakeTelemetry:
    ft = FakeTelemetry()
    yield ft
    ft.shutdown()


@pytest.fixture()
def mock_model_server(respx_mock: respx.MockRouter) -> respx.MockRouter:
    """Pre-configured respx mock for model-server HTTP calls.

    Stubs the healthz, manifest, openapi, and compute endpoints for any
    deployment id so tests don't need a running model-server container.
    """
    respx_mock.get(url__regex=r"http://sat-[^/]+:\d+/healthz").mock(
        return_value=httpx.Response(200, json={"status": "healthy"})
    )
    respx_mock.get(url__regex=r"http://sat-[^/]+:\d+/manifest").mock(
        return_value=httpx.Response(200, json={"name": "test-model", "version": "1.0"})
    )
    respx_mock.get(url__regex=r"http://sat-[^/]+:\d+/openapi\.json").mock(
        return_value=httpx.Response(200, json={"openapi": "3.0.0", "paths": {}})
    )
    respx_mock.post(url__regex=r"http://sat-[^/]+:\d+/compute").mock(
        return_value=httpx.Response(200, json={"prediction": 42})
    )
    return respx_mock


@pytest.fixture()
def model_server_client() -> ModelServerClient:
    return ModelServerClient()
