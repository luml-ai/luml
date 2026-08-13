import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
from fastapi import FastAPI

from agent.monitoring import (
    IntrospectFn,
    MonitoringSessionStore,
    register_monitoring,
)
from agent.monitoring.query_store import MonitoringStore
from agent.schemas.monitoring import (
    MONITORING_READ_SCOPE,
    MonitoringIntrospection,
    MonitoringTokenClaims,
)

DEFAULT_FRAME_ANCESTORS = ["https://app.luml.ai"]
FIXED_NOW = 1_700_000_000.0


def now_dt() -> datetime:
    return datetime.fromtimestamp(FIXED_NOW, tz=UTC)


def ago(seconds: float) -> datetime:
    return datetime.fromtimestamp(FIXED_NOW - seconds, tz=UTC)


def make_claims(
    deployment_id: uuid.UUID | None = None,
    scope: str = MONITORING_READ_SCOPE,
) -> MonitoringTokenClaims:
    return MonitoringTokenClaims(
        deployment_id=deployment_id or uuid.uuid4(),
        satellite_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        scope=scope,
        jti=uuid.uuid4(),
        exp=9999999999,
    )


def introspect_returning(*results: MonitoringIntrospection) -> IntrospectFn:
    """Fake Platform introspection yielding ``results`` in order, repeating the last.

    Modelling successive results is how single-use is exercised: the Platform reports the
    token active on the first introspection and consumed on any reuse.
    """
    calls = {"n": 0}

    async def _introspect(token: str) -> MonitoringIntrospection:
        index = min(calls["n"], len(results) - 1)
        calls["n"] += 1
        return results[index]

    return _introspect


async def introspect_raises(token: str) -> MonitoringIntrospection:
    raise RuntimeError("platform unreachable")


def build_app(
    introspect: IntrospectFn,
    *,
    frame_ancestors: list[str] | None = None,
    session_store: MonitoringSessionStore | None = None,
    data_store: MonitoringStore | None = None,
    clock: Callable[[], float] | None = None,
    cookie_secure: bool = True,
) -> FastAPI:
    app = FastAPI()
    register_monitoring(
        app,
        introspect=introspect,
        frame_ancestors=DEFAULT_FRAME_ANCESTORS if frame_ancestors is None else frame_ancestors,
        session_store=session_store,
        data_store=data_store,
        clock=(lambda: FIXED_NOW) if clock is None else clock,
        cookie_secure=cookie_secure,
    )
    return app


def client_for(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")
