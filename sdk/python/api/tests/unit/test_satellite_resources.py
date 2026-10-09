from typing import Any

import httpx
import pytest
from respx import MockRouter

from luml_api._client import AsyncLumlClient, LumlClient
from luml_api._exceptions import LumlAPIError, UnprocessableEntityError
from luml_api._types import AsyncSatellite, Satellite
from tests.conftest import TEST_API_KEY

ORG = "0199c337-09f2-7af1-af5e-83fd7a5b51a0"
ORBIT = "0199c337-09f3-753e-9def-b27745e69be6"
SATELLITE_ID = "0199c9cd-3e36-72c0-b823-040eb8195067"
SATELLITE_URL = "https://sat.example"


def _satellite_record(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    record: dict[str, Any] = {
        "id": SATELLITE_ID,
        "orbit_id": ORBIT,
        "name": "gpu-satellite",
        "description": "Runs custom GPU metrics",
        "base_url": SATELLITE_URL,
        "paired": True,
        "capabilities": {
            "custom.gpu_monitoring": {
                "version": 1,
                "api_versions": [1],
                "facets": ["deployment:custom.gpu_monitoring"],
            }
        },
        "present_capabilities": ["custom.gpu_monitoring"],
        "slug": "gpu-satellite",
        "status": "active",
        "created_at": "2026-08-24T13:00:00Z",
        "updated_at": None,
        "last_seen_at": "2026-08-27T10:00:00Z",
    }
    record.update(overrides)
    return record


def _openapi_document() -> dict[str, Any]:
    deployment_parameter = {
        "name": "deployment_id",
        "in": "path",
        "required": True,
        "schema": {"type": "string"},
    }
    window_parameter = {
        "name": "window",
        "in": "query",
        "required": False,
        "schema": {"type": "string"},
    }
    return {
        "openapi": "3.1.0",
        "security": [{"HTTPBearer": []}],
        "paths": {
            "/deployments/{deployment_id}/custom/gpu/usage": {
                "parameters": [deployment_parameter],
                "get": {
                    "tags": ["deployment:custom.gpu_monitoring"],
                    "summary": "Read GPU usage",
                    "description": "Returns GPU usage for one deployment.",
                    "parameters": [window_parameter],
                },
            },
            "/health": {
                "get": {
                    "tags": ["satellite"],
                    "summary": "Satellite health",
                    "description": "Returns process health.",
                    "parameters": [],
                    "security": [],
                }
            },
        },
    }


def _satellite_path() -> str:
    return f"/v1/organizations/{ORG}/orbits/{ORBIT}/satellites/{SATELLITE_ID}"


def test_operations_lists_only_the_requested_facet(
    client_with_mocks: LumlClient,
    respx_mock: MockRouter,
) -> None:
    respx_mock.get(_satellite_path()).mock(
        return_value=httpx.Response(200, json=_satellite_record())
    )
    description_route = respx_mock.get(f"{_satellite_path()}/openapi").mock(
        return_value=httpx.Response(200, json=_openapi_document())
    )
    request_route = respx_mock.get(
        f"{SATELLITE_URL}/deployments/deployment-1/custom/gpu/usage"
    ).mock(return_value=httpx.Response(200, json={"usage": 42}))

    satellite = client_with_mocks.satellites.get(SATELLITE_ID)
    operations = satellite.operations(facet="deployment:custom.gpu_monitoring")
    result = satellite.request(
        operations[0]["method"],
        operations[0]["path"].format(deployment_id="deployment-1"),
    )

    assert isinstance(satellite, Satellite)
    assert satellite.present_capabilities == ["custom.gpu_monitoring"]
    assert operations == [
        {
            "method": "GET",
            "path": "/deployments/{deployment_id}/custom/gpu/usage",
            "summary": "Read GPU usage",
            "description": "Returns GPU usage for one deployment.",
            "parameters": [
                _openapi_document()["paths"][
                    "/deployments/{deployment_id}/custom/gpu/usage"
                ]["parameters"][0],
                _openapi_document()["paths"][
                    "/deployments/{deployment_id}/custom/gpu/usage"
                ]["get"]["parameters"][0],
            ],
            "security": [{"HTTPBearer": []}],
        }
    ]
    assert result == {"usage": 42}
    assert request_route.calls[0].request.headers["Authorization"] == (
        f"Bearer {TEST_API_KEY}"
    )
    assert description_route.called


def test_operations_rejects_a_missing_description(
    client_with_mocks: LumlClient,
    respx_mock: MockRouter,
) -> None:
    respx_mock.get(_satellite_path()).mock(
        return_value=httpx.Response(200, json=_satellite_record())
    )
    respx_mock.get(f"{_satellite_path()}/openapi").mock(
        return_value=httpx.Response(200, json=None)
    )

    satellite = client_with_mocks.satellites.get(SATELLITE_ID)

    with pytest.raises(LumlAPIError, match="no description available"):
        satellite.operations()


def test_request_resolves_safe_urls_and_forwards_the_bearer_key(
    client_with_mocks: LumlClient,
    respx_mock: MockRouter,
) -> None:
    respx_mock.get(_satellite_path()).mock(
        return_value=httpx.Response(200, json=_satellite_record())
    )
    relative_route = respx_mock.get(f"{SATELLITE_URL}/custom/gpu/usage").mock(
        return_value=httpx.Response(200, json={"usage": 42})
    )
    absolute_route = respx_mock.post(f"{SATELLITE_URL}/custom/gpu/limits").mock(
        return_value=httpx.Response(200, json={"limit": 80})
    )

    satellite = client_with_mocks.satellites.get(SATELLITE_ID)

    assert satellite.request("GET", "/custom/gpu/usage") == {"usage": 42}
    assert satellite.request(
        "POST",
        f"{SATELLITE_URL}/custom/gpu/limits",
        json={"limit": 80},
    ) == {"limit": 80}

    assert relative_route.calls[0].request.headers["Authorization"] == (
        f"Bearer {TEST_API_KEY}"
    )
    assert absolute_route.calls[0].request.headers["Authorization"] == (
        f"Bearer {TEST_API_KEY}"
    )


def test_request_refuses_a_foreign_origin_before_sending(
    client_with_mocks: LumlClient,
    respx_mock: MockRouter,
) -> None:
    respx_mock.get(_satellite_path()).mock(
        return_value=httpx.Response(200, json=_satellite_record())
    )
    satellite = client_with_mocks.satellites.get(SATELLITE_ID)

    with pytest.raises(LumlAPIError, match="same origin"):
        satellite.request("GET", "https://attacker.example/steal")

    assert all(call.request.url.host != "attacker.example" for call in respx_mock.calls)


def test_request_maps_satellite_http_errors(
    client_with_mocks: LumlClient,
    respx_mock: MockRouter,
) -> None:
    respx_mock.get(_satellite_path()).mock(
        return_value=httpx.Response(200, json=_satellite_record())
    )
    respx_mock.get(f"{SATELLITE_URL}/custom/gpu/usage").mock(
        return_value=httpx.Response(422, json={"detail": "invalid window"})
    )
    satellite = client_with_mocks.satellites.get(SATELLITE_ID)

    with pytest.raises(UnprocessableEntityError):
        satellite.request("GET", "/custom/gpu/usage", params={"window": "later"})


@pytest.mark.asyncio
async def test_async_satellite_operations_and_request_match_the_sync_api(
    async_client_with_mocks: AsyncLumlClient,
    respx_mock: MockRouter,
) -> None:
    respx_mock.get(_satellite_path()).mock(
        return_value=httpx.Response(200, json=_satellite_record())
    )
    respx_mock.get(f"{_satellite_path()}/openapi").mock(
        return_value=httpx.Response(200, json=_openapi_document())
    )
    request_route = respx_mock.get(f"{SATELLITE_URL}/custom/gpu/usage").mock(
        return_value=httpx.Response(200, json={"usage": 42})
    )

    satellite = await async_client_with_mocks.satellites.get(SATELLITE_ID)
    operations = await satellite.operations(facet="deployment:custom.gpu_monitoring")
    result = await satellite.request("GET", "/custom/gpu/usage")

    assert isinstance(satellite, AsyncSatellite)
    assert [operation["summary"] for operation in operations] == ["Read GPU usage"]
    assert result == {"usage": 42}
    assert request_route.calls[0].request.headers["Authorization"] == (
        f"Bearer {TEST_API_KEY}"
    )
