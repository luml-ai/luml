from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from luml.api.satellites import satellite_worker_router
from luml.infra.exceptions import ApplicationError
from luml.models import AuthSatellite
from luml.schemas.deployment import DeploymentStatus
from starlette.authentication import AuthCredentials, AuthenticationBackend
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection

OWNER_SATELLITE_ID = UUID("0199c337-09f9-706e-9b80-58939d5fba79")
OWNER_ORBIT_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")
FOREIGN_SATELLITE_ID = UUID("0199c337-0a02-7c1e-8a3b-3f0e1a6d95c4")
FOREIGN_ORBIT_ID = UUID("0199c337-0a03-7f5a-bb17-2c9d4e8a1b63")
DEPLOYMENT_ID = UUID("0199c337-09f7-751e-add2-d952f0d6cf4e")

DEPLOYMENT_PATH = f"/satellites/v1/deployments/{DEPLOYMENT_ID}"


class _SatelliteBackend(AuthenticationBackend):
    def __init__(self, satellite_id: UUID, orbit_id: UUID) -> None:
        self.satellite_id = satellite_id
        self.orbit_id = orbit_id

    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, AuthSatellite]:
        return AuthCredentials(["authenticated", "satellite"]), AuthSatellite(
            satellite_id=self.satellite_id, orbit_id=self.orbit_id
        )


def _client(satellite_id: UUID, orbit_id: UUID) -> TestClient:
    app = FastAPI()
    app.include_router(satellite_worker_router)
    app.add_middleware(
        AuthenticationMiddleware, backend=_SatelliteBackend(satellite_id, orbit_id)
    )

    @app.exception_handler(ApplicationError)
    async def _application_error_handler(
        request: Request, exc: ApplicationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content={"detail": exc.message}
        )

    return TestClient(app)


def test_get_deployment_route_is_registered_once() -> None:
    matching_routes = [
        route
        for route in satellite_worker_router.routes
        if isinstance(route, APIRoute)
        and route.path == "/satellites/v1/deployments/{deployment_id}"
        and "GET" in route.methods
    ]

    assert len(matching_routes) == 1


@patch(
    "luml.api.satellites.satellite_handler.touch_last_seen",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.deployments.DeploymentHandler.delete_worker_deployment",
    new_callable=AsyncMock,
)
def test_delete_deployment_forwards_the_authenticated_satellite(
    mock_delete_worker_deployment: AsyncMock,
    mock_touch_last_seen: AsyncMock,
) -> None:
    """The route must forward the satellite identity, not just the deployment id."""
    response = _client(OWNER_SATELLITE_ID, OWNER_ORBIT_ID).delete(DEPLOYMENT_PATH)

    assert response.status_code == 204
    mock_delete_worker_deployment.assert_awaited_once_with(
        OWNER_SATELLITE_ID, DEPLOYMENT_ID
    )


@patch(
    "luml.api.satellites.satellite_handler.touch_last_seen",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.deployments.DeploymentRepository.delete_satellite_deployment",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.deployments.DeploymentRepository.get_satellite_deployment",
    new_callable=AsyncMock,
)
def test_delete_deployment_from_another_satellite_is_rejected(
    mock_get_satellite_deployment: AsyncMock,
    mock_delete_satellite_deployment: AsyncMock,
    mock_touch_last_seen: AsyncMock,
) -> None:
    deployment = Mock(id=DEPLOYMENT_ID, status=DeploymentStatus.DELETION_PENDING)

    def owned_by_first_satellite(requested_id: UUID, satellite_id: UUID) -> Mock | None:
        if requested_id != DEPLOYMENT_ID or satellite_id != OWNER_SATELLITE_ID:
            return None
        return deployment

    mock_get_satellite_deployment.side_effect = owned_by_first_satellite

    response = _client(FOREIGN_SATELLITE_ID, FOREIGN_ORBIT_ID).delete(DEPLOYMENT_PATH)

    assert response.status_code == 404
    assert response.json() == {"detail": "Deployment not found"}
    mock_delete_satellite_deployment.assert_not_awaited()


@patch(
    "luml.handlers.deployments.DeploymentHandler.update_worker_deployment",
    new_callable=AsyncMock,
)
def test_progress_note_over_the_limit_is_rejected(
    mock_update_worker_deployment: AsyncMock,
) -> None:
    response = _client(OWNER_SATELLITE_ID, OWNER_ORBIT_ID).patch(
        DEPLOYMENT_PATH,
        json={"progress_note": "n" * 1001},
    )

    assert response.status_code == 422
    assert "progress_note" in response.text
    mock_update_worker_deployment.assert_not_awaited()
