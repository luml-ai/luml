from typing import Any

from fastapi import APIRouter, Request

from luml_agent.schemas import (
    ReorderIn,
    RunCreateIn,
    RunEdgeOut,
    RunEventOut,
    RunNodeOut,
    RunOut,
)

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _node_out(
    request: Request,
    node: Any,  # noqa: ANN401
) -> dict[str, Any]:
    pty = request.app.state.pty
    node_repo = request.app.state.db.nodes
    sessions = node_repo.get_sessions(node.id)
    active_sid = None
    for s in sessions:
        if pty.is_alive(s.session_id):
            active_sid = s.session_id
            break
    return RunNodeOut.from_db(
        node, active_sid,
    ).model_dump()


@router.post("", status_code=201)
async def create_run(
    request: Request, body: RunCreateIn,
) -> dict[str, Any]:
    handler = request.app.state.run_handler
    run = await handler.create(body)
    return RunOut.from_db(run).model_dump()


@router.get("")
def list_runs(
    request: Request,
    repository_id: str | None = None,
) -> list[dict[str, Any]]:
    handler = request.app.state.run_handler
    node_repo = request.app.state.db.nodes
    return [
        RunOut.from_db(
            r,
            has_waiting_input=node_repo.has_waiting_input_nodes(r.id),
        ).model_dump()
        for r in handler.list_all(repository_id)
    ]


@router.patch("/reorder")
def reorder_runs(
    request: Request, body: ReorderIn,
) -> dict[str, str]:
    db = request.app.state.db
    db.runs.update_positions(
        [(item.id, item.position) for item in body.items],
    )
    return {"status": "ok"}


@router.get("/{run_id}")
def get_run(
    request: Request, run_id: str,
) -> dict[str, Any]:
    handler = request.app.state.run_handler
    node_repo = request.app.state.db.nodes
    run = handler.get(run_id)
    return RunOut.from_db(
        run,
        has_waiting_input=node_repo.has_waiting_input_nodes(run_id),
    ).model_dump()


@router.post("/{run_id}/start")
async def start_run(
    request: Request, run_id: str,
) -> dict[str, Any]:
    handler = request.app.state.run_handler
    run = await handler.start(run_id)
    return RunOut.from_db(run).model_dump()


@router.post("/{run_id}/cancel")
async def cancel_run(
    request: Request, run_id: str,
) -> dict[str, Any]:
    handler = request.app.state.run_handler
    run = await handler.cancel(run_id)
    return RunOut.from_db(run).model_dump()


@router.post("/{run_id}/restart")
async def restart_run(
    request: Request, run_id: str,
) -> dict[str, Any]:
    handler = request.app.state.run_handler
    run = await handler.restart(run_id)
    return RunOut.from_db(run).model_dump()


@router.post("/{run_id}/merge/preview")
async def merge_preview(
    request: Request, run_id: str,
) -> dict[str, Any]:
    handler = request.app.state.run_handler
    return await handler.merge_preview(run_id)


@router.post("/{run_id}/merge")
async def merge_run(
    request: Request, run_id: str,
) -> dict[str, str]:
    handler = request.app.state.run_handler
    message = await handler.merge(run_id)
    return {"status": "merged", "message": message}


@router.delete("/{run_id}")
def delete_run(
    request: Request, run_id: str,
) -> dict[str, str]:
    handler = request.app.state.run_handler
    handler.delete(run_id)
    return {"status": "deleted"}


@router.get("/{run_id}/graph")
def get_run_graph(
    request: Request, run_id: str,
) -> dict[str, Any]:
    handler = request.app.state.run_handler
    graph = handler.get_graph(run_id)
    return {
        "nodes": [
            _node_out(request, n)
            for n in graph["nodes"]
        ],
        "edges": [
            RunEdgeOut.model_validate(
                e, from_attributes=True,
            ).model_dump()
            for e in graph["edges"]
        ],
    }


@router.get("/{run_id}/events")
def get_run_events(
    request: Request,
    run_id: str,
    after_seq: int = 0,
) -> list[dict[str, Any]]:
    handler = request.app.state.run_handler
    events = handler.get_events(run_id, after_seq)
    return [
        RunEventOut.from_db(e).model_dump()
        for e in events
    ]
