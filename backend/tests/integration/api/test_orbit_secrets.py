from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock
from uuid import uuid7

import pytest
from httpx import ASGITransport, AsyncClient
from luml.handlers.orbit_secrets import OrbitSecretHandler
from luml.handlers.permissions import PermissionsHandler
from luml.infra.security import JWTAuthenticationBackend
from luml.models import AuthUser
from luml.repositories.orbit_secrets import OrbitSecretRepository
from luml.service import AppService
from starlette.authentication import AuthCredentials

from tests.support.auth import satellite
from tests.support.seeds import OrbitFixtureData


@pytest.fixture
async def client(
    seeded_orbit: OrbitFixtureData,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient]:
    data = seeded_orbit
    monkeypatch.setattr(
        OrbitSecretHandler,
        "_OrbitSecretHandler__secret_repository",
        OrbitSecretRepository(data.engine),
    )
    monkeypatch.setattr(PermissionsHandler, "check_permissions", AsyncMock())
    monkeypatch.setattr(
        JWTAuthenticationBackend,
        "authenticate",
        AsyncMock(
            return_value=(
                AuthCredentials(["authenticated", "jwt"]),
                AuthUser(user_id=data.user.id, email=data.user.email),
            )
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=AppService()), base_url="http://test"
    ) as test_client:
        yield test_client


@pytest.mark.parametrize(
    "value", ["dummy-value", "", "x" * 8192], ids=["ordinary", "empty", "max-length"]
)
async def test_user_responses_mask_values_and_workers_can_read_them(
    client: AsyncClient,
    seeded_orbit: OrbitFixtureData,
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    orbit_id = seeded_orbit.orbit.id
    path = f"/v1/organizations/{seeded_orbit.organization.id}/orbits/{orbit_id}/secrets"
    created = await client.post(path, json={"name": "API_KEY", "value": value})

    assert created.status_code == 200
    metadata = created.json()
    assert metadata["value"] == ""
    assert metadata["name"] == "API_KEY"
    assert metadata["orbit_id"] == str(orbit_id)
    assert metadata["created_at"]
    secret_path = f"{path}/{metadata['id']}"

    fetched = await client.get(secret_path)
    assert fetched.status_code == 200
    assert fetched.json() == metadata

    updated = await client.patch(secret_path, json={"tags": ["tag"]})
    assert updated.status_code == 200
    assert updated.json()["value"] == ""
    assert updated.json()["tags"] == ["tag"]
    assert updated.json()["name"] == "API_KEY"
    assert updated.json()["created_at"] == metadata["created_at"]

    listed = await client.get(path)
    assert listed.status_code == 200
    assert listed.json() == [updated.json()]

    monkeypatch.setattr(
        JWTAuthenticationBackend,
        "authenticate",
        AsyncMock(return_value=satellite(uuid7(), orbit_id)),
    )
    worker_path = f"/satellites/v1/secrets/{metadata['id']}"
    worker_secret = await client.get(worker_path)
    assert worker_secret.status_code == 200
    assert worker_secret.json()["value"] == value

    worker_secrets = await client.get("/satellites/v1/secrets")
    assert worker_secrets.status_code == 200
    assert worker_secrets.json() == [worker_secret.json()]
