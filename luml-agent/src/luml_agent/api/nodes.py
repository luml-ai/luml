from typing import Any

from fastapi import APIRouter, Request

from luml_agent.schemas import NodeActionIn, NodeInputIn

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
