from typing import cast
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from luml.api.orbits.orbit_satellites import (
    get_satellite_openapi,
    organization_orbit_satellites_router,
)
from luml.models import AuthUser
from starlette.authentication import AuthCredentials, AuthenticationBackend
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection, Request

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
ORBIT_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")


class _SignedInBackend(AuthenticationBackend):
    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, AuthUser]:
        return AuthCredentials(["authenticated", "jwt"]), AuthUser(
            user_id=USER_ID, email="caller@example.com"
        )


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(organization_orbit_satellites_router)
    app.add_middleware(AuthenticationMiddleware, backend=_SignedInBackend())
    return TestClient(app)


@pytest.mark.parametrize("body", [{}, {"name": None}], ids=["missing", "null"])
@patch(
    "luml.handlers.satellites.SatelliteHandler.create_satellite",
    new_callable=AsyncMock,
)
def test_create_satellite_requires_name(
    mock_create_satellite: AsyncMock, body: dict[str, object]
) -> None:
    response = _client().post(
        f"/{ORGANIZATION_ID}/orbits/{ORBIT_ID}/satellites", json=body
    )

    assert response.status_code == 422
    assert ["body", "name"] in [error["loc"] for error in response.json()["detail"]]
    mock_create_satellite.assert_not_awaited()


@patch(
    "luml.api.orbits.orbit_satellites.SatelliteHandler.get_satellite_openapi",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_satellite_openapi_endpoint(
    mock_get_satellite_openapi: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")
    document = {"openapi": "3.1.0", "paths": {}}
    request = Mock(user=Mock(id=user_id))
    mock_get_satellite_openapi.return_value = document

    result = await get_satellite_openapi(
        cast(Request, request), organization_id, orbit_id, satellite_id
    )

    assert result == document
    mock_get_satellite_openapi.assert_awaited_once_with(
        user_id, organization_id, orbit_id, satellite_id
    )
