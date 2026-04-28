from typing import Any

from fastapi import APIRouter, Request

from luml_prisma.api.agents import router as agents_router
from luml_prisma.api.browse import router as browse_router
from luml_prisma.api.health import router as health_router
from luml_prisma.api.nodes import router as nodes_router
from luml_prisma.api.repositories import (
    router as repositories_router,
)
from luml_prisma.api.runs import router as runs_router
from luml_prisma.api.tasks import router as tasks_router
from luml_prisma.api.uploads import router as uploads_router
from luml_prisma.api.websockets import router as ws_router

_debug_router = APIRouter(tags=["debug"])


@_debug_router.get("/api/debug/sessions")
def api_debug_sessions(
    request: Request,
) -> list[dict[str, Any]]:
    pty = request.app.state.pty
    result = []
    for sid, session in pty._sessions.items():
        alive = session.process.poll() is None
        result.append(
            {
                "session_id": sid,
                "task_id": session.task_id,
                "pid": session.pid,
                "session_type": session.session_type,
                "alive": alive,
                "exit_code": session.process.poll(),
            }
        )
    return result


def aggregate_router() -> APIRouter:
    root = APIRouter()
    root.include_router(repositories_router)
    root.include_router(tasks_router)
    root.include_router(runs_router)
    root.include_router(nodes_router)
    root.include_router(browse_router)
    root.include_router(agents_router)
    root.include_router(uploads_router)
    root.include_router(ws_router)
    root.include_router(health_router)
    root.include_router(_debug_router)
    return root
