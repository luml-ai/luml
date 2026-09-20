import logging
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.routing import APIRouter
from starlette.datastructures import MutableHeaders
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from luml_satellite.monitoring.dashboard.api import build_query_router
from luml_satellite.monitoring.dashboard.query import HealthSource, MonitoringQueryService
from luml_satellite.monitoring.dashboard.session import (
    DEFAULT_SESSION_TTL_SECONDS,
    MonitoringSession,
    MonitoringSessionStore,
    require_monitoring_session,
    set_monitoring_cookie,
)
from luml_satellite.monitoring.storage.query_store import InMemoryMonitoringStore, MonitoringStore
from luml_satellite.wire import (
    MONITORING_READ_SCOPE,
    MonitoringIntrospection,
    MonitoringSessionInfo,
)

logger = logging.getLogger("satellite")

IntrospectFn = Callable[[str], Awaitable[MonitoringIntrospection]]

MONITORING_PATH_PREFIX = "/monitoring"
MONITORING_APP_PATH = "/monitoring/app/"
_DEFAULT_STATIC_DIR = Path(__file__).parent / "static"


def frame_ancestors_csp(origins: list[str]) -> str:
    sources = " ".join(origins) if origins else "'none'"
    return f"frame-ancestors {sources}"


class FrameAncestorsMiddleware:
    """Set ``Content-Security-Policy: frame-ancestors`` on monitoring responses.

    Restricts who may embed the dashboard in an iframe to the allowed Platform origin(s);
    all other framing is refused by the browser. Pure ASGI so it does not buffer the static
    bundle's responses.
    """

    def __init__(self, app: ASGIApp, csp_value: str) -> None:
        self.app = app
        self._csp_value = csp_value

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(MONITORING_PATH_PREFIX):
            await self.app(scope, receive, send)
            return

        async def send_with_csp(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Content-Security-Policy"] = self._csp_value
            await send(message)

        await self.app(scope, receive, send_with_csp)


def _denied_response() -> HTMLResponse:
    return HTMLResponse(
        "<h1>Monitoring unavailable</h1>"
        "<p>This monitoring link is invalid or has expired. "
        "Reopen monitoring from the platform.</p>",
        status_code=status.HTTP_403_FORBIDDEN,
    )


def _unavailable_response() -> HTMLResponse:
    return HTMLResponse(
        "<h1>Monitoring unavailable</h1>"
        "<p>Monitoring is temporarily unavailable. Please try again.</p>",
        status_code=status.HTTP_502_BAD_GATEWAY,
    )


def _build_router(introspect: IntrospectFn, cookie_secure: bool) -> APIRouter:
    router = APIRouter(prefix=MONITORING_PATH_PREFIX)

    @router.get(
        "/launch",
        summary="Launch the monitoring dashboard",
        description="Exchange a single-use token for a deployment-scoped dashboard session.",
    )
    async def launch(
        request: Request, token: str | None = None, theme: str | None = None
    ) -> Response:
        if not token:
            return _denied_response()
        try:
            introspection = await introspect(token)
        except Exception:
            logger.exception("Monitoring launch token introspection failed")
            return _unavailable_response()

        claims = introspection.claims
        if not introspection.active or claims is None or claims.scope != MONITORING_READ_SCOPE:
            return _denied_response()

        store: MonitoringSessionStore = request.app.state.monitoring_sessions
        session = store.create(claims.deployment_id, claims.scope)
        target = MONITORING_APP_PATH
        if theme in ("light", "dark"):
            target = f"{MONITORING_APP_PATH}?theme={theme}"
        response = RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)
        set_monitoring_cookie(
            response,
            store,
            session,
            secure=cookie_secure,
        )
        return response

    @router.get(
        "/api/session",
        response_model=MonitoringSessionInfo,
        summary="Get the dashboard session",
        description="Return the deployment and scope associated with the dashboard session.",
    )
    async def session_info(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
    ) -> MonitoringSessionInfo:
        return MonitoringSessionInfo(deployment_id=session.deployment_id, scope=session.scope)

    return router


def register_monitoring(
    app: FastAPI,
    *,
    introspect: IntrospectFn,
    frame_ancestors: list[str],
    session_ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
    static_dir: Path | None = None,
    session_store: MonitoringSessionStore | None = None,
    data_store: MonitoringStore | None = None,
    clock: Callable[[], float] = time.time,
    cookie_secure: bool = True,
    health_source: HealthSource | None = None,
) -> None:
    store = session_store or MonitoringSessionStore(ttl_seconds=session_ttl_seconds)
    app.state.monitoring_sessions = store
    app.state.monitoring_cookie_secure = cookie_secure
    app.state.monitoring_query = MonitoringQueryService(
        data_store or InMemoryMonitoringStore(), clock=clock, health_source=health_source
    )

    app.add_middleware(FrameAncestorsMiddleware, csp_value=frame_ancestors_csp(frame_ancestors))
    app.include_router(_build_router(introspect, cookie_secure=cookie_secure))
    app.include_router(build_query_router())

    static_root = static_dir or _DEFAULT_STATIC_DIR
    app.mount(
        "/monitoring/app",
        StaticFiles(directory=str(static_root), html=True, check_dir=False),
        name="monitoring-app",
    )


def install_machine_unknown_route(app: FastAPI) -> None:
    @app.api_route(
        "/deployments/{deployment_id}/monitoring/{unmatched_path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        include_in_schema=False,
    )
    async def unknown_machine_route(deployment_id: str, unmatched_path: str) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Not Found", "code": "unknown_route"},
        )
