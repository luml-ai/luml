from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from luml_prisma.api.health import HealthResponse
from luml_prisma.server import app
from luml_prisma.version import __version__


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient) -> None:
    resp = await client.get("/api/health/")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health_response_body(client: AsyncClient) -> None:
    resp = await client.get("/api/health/")
    body = resp.json()
    assert body["service"] == "luml-prisma"
    assert body["version"] == __version__


@pytest.mark.asyncio
async def test_health_response_model(client: AsyncClient) -> None:
    resp = await client.get("/api/health/")
    parsed = HealthResponse.model_validate(resp.json())
    assert parsed.service == "luml-prisma"
    assert parsed.version == __version__
