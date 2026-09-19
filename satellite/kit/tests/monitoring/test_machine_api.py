"""The machine surface: monitoring as a facet of the deployment tree.

A bearer key is valid for a whole orbit and carries no deployment, so the request names
its deployment in the path — and the surface shares one credential story with inference,
while the browser world under /monitoring keeps its cookie sessions. These tests pin the
door, not the data behind it: the sections themselves are covered by the query-service
tests.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.exceptions import HTTPException as StarletteHTTPException

from luml_satellite import DeploymentMetadata
from luml_satellite.monitoring import LocalDeployment, MonitoringQueryService, register_monitoring
from luml_satellite.monitoring.compute.health import worker_health
from luml_satellite.monitoring.dashboard.api import (
    DeploymentNotHostedError,
    build_machine_router,
)
from luml_satellite.monitoring.dashboard.app import MONITORING_APP_PATH
from luml_satellite.monitoring.storage.query_store import (
    EventStatus,
    InferenceEvent,
    InMemoryMonitoringStore,
)
from luml_satellite.wire import MonitoringIntrospection
from tests.support import FIXED_NOW

DEPLOYMENT_ID = uuid.uuid4()
OTHER_DEPLOYMENT_ID = uuid.uuid4()
GOOD_KEY = "dfs_good"


async def _authorize(api_key: str) -> bool:
    if api_key == "boom":
        raise RuntimeError("platform down")
    return api_key == GOOD_KEY


async def _introspect(token: str) -> MonitoringIntrospection:
    return MonitoringIntrospection(active=False)


@pytest.fixture()
def app() -> Iterator[FastAPI]:
    application = FastAPI()
    security = HTTPBearer(auto_error=False)
    deployments: dict[str, LocalDeployment] = {}

    @application.exception_handler(DeploymentNotHostedError)
    async def deployment_not_hosted(
        request: Request, error: DeploymentNotHostedError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": error.detail, "code": error.code},
        )

    @application.exception_handler(404)
    async def unknown_route(request: Request, error: StarletteHTTPException) -> Response:
        if (
            request.url.path.startswith(MONITORING_APP_PATH)
            or request.scope.get("route") is not None
        ):
            return await http_exception_handler(request, error)
        return JSONResponse(
            status_code=404,
            content={"detail": error.detail, "code": "unknown_route"},
            headers=error.headers,
        )

    async def verify_token(
        credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
    ) -> bool:
        if credentials is None:
            raise HTTPException(status_code=403, detail="Not authenticated")
        try:
            authorized = await _authorize(credentials.credentials)
        except Exception as error:
            raise HTTPException(status_code=502, detail="Authorization failed") from error
        if not authorized:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return True

    register_monitoring(
        application,
        introspect=_introspect,
        frame_ancestors=["https://app.luml.ai"],
    )
    application.include_router(
        build_machine_router(lambda deployment_id: str(deployment_id) in deployments),
        dependencies=[Depends(verify_token)],
    )

    @application.post("/deployments/{deployment_id}/compute")
    async def compute(
        deployment_id: str,
        authorized: bool = Depends(verify_token),  # noqa: B008
    ) -> dict[str, object]:
        if deployment_id not in deployments:
            raise DeploymentNotHostedError()
        return {}

    @application.get("/deployments")
    async def listed_deployments(
        authorized: bool = Depends(verify_token),  # noqa: B008
    ) -> list[dict[str, object]]:
        return [
            {
                "deployment_id": deployment.deployment_id,
                "name": deployment.metadata.name,
                "status": deployment.metadata.status,
                "monitoring_mode": "full" if deployment.monitoring_enabled else "off",
                "last_monitored_at": worker_health.snapshot(
                    deployment.deployment_id
                ).deployment.last_window_end,
            }
            for deployment in deployments.values()
        ]

    store = InMemoryMonitoringStore()
    store.add_event(
        InferenceEvent(
            event_id="evt-1",
            deployment_id=DEPLOYMENT_ID,
            ts=datetime.fromtimestamp(FIXED_NOW - 60, tz=UTC),
            status=EventStatus.SUCCESS,
            status_code=200,
            latency_ms=12.0,
        )
    )
    application.state.monitoring_query = MonitoringQueryService(store, clock=lambda: FIXED_NOW)

    deployments[str(DEPLOYMENT_ID)] = LocalDeployment(
        deployment_id=str(DEPLOYMENT_ID),
        monitoring_enabled=True,
        metadata=DeploymentMetadata(name="insurance", status="active"),
    )
    yield application


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


def _url(section: str = "overview", deployment: uuid.UUID = DEPLOYMENT_ID) -> str:
    return f"/deployments/{deployment}/monitoring/{section}"


def _bearer(key: str = GOOD_KEY) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


class TestMachineAPI:
    async def test_a_key_reads_any_section_of_a_hosted_deployment(self, app: FastAPI) -> None:
        async with _client(app) as client:
            overview = await client.get(_url("overview"), headers=_bearer())
            runtime = await client.get(_url("runtime"), headers=_bearer())
            output_drift = await client.get(_url("output-drift"), headers=_bearer())

        assert overview.status_code == 200
        assert overview.json()["state"] == "ok"
        assert runtime.status_code == 200
        assert runtime.json()["request_count"] == 1
        # no materialized output window in the seeded store: empty, but served
        assert output_drift.status_code == 200
        assert output_drift.json()["state"] == "empty"

    async def test_without_a_credential_the_door_stays_shut(self, app: FastAPI) -> None:
        async with _client(app) as client:
            resp = await client.get(_url())

        assert resp.status_code == 403

    async def test_a_rejected_key_is_unauthenticated(self, app: FastAPI) -> None:
        async with _client(app) as client:
            resp = await client.get(_url(), headers=_bearer("dfs_wrong"))

        assert resp.status_code == 401

    async def test_an_unverifiable_key_fails_closed(self, app: FastAPI) -> None:
        """Platform unreachable and nothing cached: refuse, never trust."""
        async with _client(app) as client:
            resp = await client.get(_url(), headers=_bearer("boom"))

        assert resp.status_code == 502

    async def test_a_deployment_this_satellite_does_not_host_is_not_found(
        self, app: FastAPI
    ) -> None:
        async with _client(app) as client:
            resp = await client.get(_url(deployment=OTHER_DEPLOYMENT_ID), headers=_bearer())

        assert resp.status_code == 404
        assert resp.json() == {
            "detail": "Deployment not found on this Satellite",
            "code": "deployment_not_hosted",
        }

    async def test_compute_for_a_deployment_this_satellite_does_not_host_is_coded(
        self,
        app: FastAPI,
    ) -> None:
        async with _client(app) as client:
            resp = await client.post(
                f"/deployments/{OTHER_DEPLOYMENT_ID}/compute",
                headers=_bearer(),
                json={},
            )

        assert resp.status_code == 404
        assert resp.json() == {
            "detail": "Deployment not found on this Satellite",
            "code": "deployment_not_hosted",
        }

    async def test_an_unmatched_route_has_a_machine_readable_code(self, app: FastAPI) -> None:
        async with _client(app) as client:
            resp = await client.get("/not-a-satellite-route")

        assert resp.status_code == 404
        assert resp.json() == {"detail": "Not Found", "code": "unknown_route"}

    async def test_a_missing_dashboard_static_file_keeps_its_plain_404(self, app: FastAPI) -> None:
        async with _client(app) as client:
            resp = await client.get("/monitoring/app/missing.js")

        assert resp.status_code == 404
        assert resp.json() == {"detail": "Not Found"}

    async def test_a_missing_trace_keeps_its_plain_404(self, app: FastAPI) -> None:
        async with _client(app) as client:
            resp = await client.get(_url("traces/missing"), headers=_bearer())

        assert resp.status_code == 404
        assert resp.json() == {"detail": "trace not found in this window"}

    async def test_a_dashboard_cookie_does_not_open_the_machine_surface(self, app: FastAPI) -> None:
        """One credential per surface: sessions stay in the browser world."""
        client = _client(app)
        client.cookies.set("monitoring_session", "some-session")
        async with client:
            resp = await client.get(_url())

        assert resp.status_code == 403

    async def test_the_machine_surface_is_read_only(self, app: FastAPI) -> None:
        """Acknowledging alerts stays on the session surface: machines watch, a person decides."""
        async with _client(app) as client:
            resp = await client.post(
                _url("alerts/acknowledge"), headers=_bearer(), json={"metric": "runtime:error_rate"}
            )

        assert resp.status_code in (404, 405)

    async def test_the_listing_says_what_is_monitored_here(self, app: FastAPI) -> None:
        worker_health.window_processed(
            str(DEPLOYMENT_ID),
            datetime.fromtimestamp(FIXED_NOW - 300, tz=UTC),
            datetime.fromtimestamp(FIXED_NOW, tz=UTC),
        )
        try:
            async with _client(app) as client:
                resp = await client.get("/deployments", headers=_bearer())
        finally:
            worker_health._deployments.pop(str(DEPLOYMENT_ID), None)

        assert resp.status_code == 200
        rows = {row["deployment_id"]: row for row in resp.json()}
        row = rows[str(DEPLOYMENT_ID)]
        assert row["name"] == "insurance"
        assert row["status"] == "active"
        assert row["monitoring_mode"] == "full"
        assert row["last_monitored_at"] is not None
