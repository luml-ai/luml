from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import Response

from luml_prisma.schemas import NodeActionIn, NodeInputIn
from luml_prisma.services.orchestrator.engine import OrchestratorEngine

router = APIRouter(prefix="/api/nodes", tags=["nodes"])


@router.post("/{node_id}/input")
def node_input(
    request: Request,
    node_id: str,
    body: NodeInputIn,
) -> dict[str, str]:
    handler = request.app.state.node_handler
    handler.send_input(node_id, body.text)
    return {"status": "sent"}


@router.get("/{node_id}/sessions/{session_id}/scrollback")
def get_session_scrollback(
    request: Request,
    node_id: str,
    session_id: str,
) -> Response:
    pty = request.app.state.pty
    if pty.is_alive(session_id):
        data = pty.get_scrollback(session_id)
    else:
        data = OrchestratorEngine.load_scrollback(session_id)
    return Response(content=data, media_type="application/octet-stream")


@router.post("/{node_id}/action")
async def node_action(
    request: Request,
    node_id: str,
    body: NodeActionIn,
) -> dict[str, Any]:
    handler = request.app.state.node_handler
    return await handler.execute_action(
        node_id, body.action, body.payload,
    )
