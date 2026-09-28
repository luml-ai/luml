from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from luml.api.orbits.orbit_artifacts import artifacts_router
from luml.api.orbits.orbit_collections import collections_router
from luml.infra.exceptions import ApplicationError
from luml.models import AuthUser
from starlette.authentication import AuthCredentials, AuthenticationBackend
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
ORBIT_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")


class StubAuthBackend(AuthenticationBackend):
    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, AuthUser]:
        return AuthCredentials(["authenticated", "jwt"]), AuthUser(
            user_id=USER_ID, email="test@example.com"
        )


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(artifacts_router, prefix="/v1/organizations")
    app.include_router(collections_router, prefix="/v1/organizations")
    app.add_middleware(AuthenticationMiddleware, backend=StubAuthBackend())

    @app.exception_handler(ApplicationError)
    async def application_error_handler(
        request: Request, error: ApplicationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code, content={"detail": error.message}
        )

    return TestClient(app)


@pytest.mark.parametrize("route", ["artifacts", "collections"])
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collections_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.get_orbit_collections",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
def test_list_rejects_invalid_cursor(
    mock_check_permissions: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collections: AsyncMock,
    mock_check_access: AsyncMock,
    route: str,
) -> None:
    mock_get_orbit_simple.return_value = Mock(organization_id=ORGANIZATION_ID)

    response = _client().get(
        f"/v1/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}/{route}",
        params={"cursor": "garbage"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid cursor"}
    mock_get_collections.assert_not_awaited()
