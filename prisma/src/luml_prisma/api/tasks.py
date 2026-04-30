from typing import Any

from fastapi import APIRouter, Request

from luml_prisma.schemas import (
    ReorderIn,
    TaskCreateIn,
    TaskOut,
    TaskStatusUpdateIn,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _task_out(
    request: Request, task: Any,  # noqa: ANN401
) -> dict[str, Any]:
    pty = request.app.state.pty
    session_id = pty.get_active_session_id(task.id)
    has_waiting = (
        session_id is not None
        and pty.is_session_waiting_notified(session_id)
    )
    return TaskOut(
        id=task.id,
        repository_id=task.repository_id,
        name=task.name,
        branch=task.branch,
        worktree_path=task.worktree_path,
        agent_id=task.agent_id,
        status=task.status,
        prompt=task.prompt,
        base_branch=task.base_branch,
        position=task.position,
        created_at=task.created_at,
        updated_at=task.updated_at,
        is_alive=pty.is_task_alive(task.id),
        session_id=session_id,
        has_waiting_input=has_waiting,
    ).model_dump()


@router.get("")
def list_tasks(
    request: Request,
    repository_id: str | None = None,
) -> list[dict[str, Any]]:
    handler = request.app.state.task_handler
    return [
        _task_out(request, t)
        for t in handler.list_all(repository_id)
    ]


@router.post("", status_code=201)
async def create_task(
    request: Request, body: TaskCreateIn,
) -> dict[str, Any]:
    handler = request.app.state.task_handler
    task = await handler.create(
        body.repository_id,
        body.name,
        body.agent_id,
        body.prompt,
        body.base_branch,
    )
    return _task_out(request, task)


@router.get("/{task_id}")
def get_task(
    request: Request, task_id: str,
) -> dict[str, Any]:
    handler = request.app.state.task_handler
    task = handler.get(task_id)
    return _task_out(request, task)


@router.delete("/{task_id}")
async def delete_task(
    request: Request, task_id: str,
) -> dict[str, str]:
    handler = request.app.state.task_handler
    await handler.delete(task_id)
    return {"status": "deleted"}


@router.patch("/{task_id}/status")
def update_task_status(
    request: Request,
    task_id: str,
    body: TaskStatusUpdateIn,
) -> dict[str, Any]:
    handler = request.app.state.task_handler
    task = handler.update_status(task_id, body.status)
    return _task_out(request, task)


@router.post("/{task_id}/terminal")
async def open_terminal(
    request: Request,
    task_id: str,
    mode: str = "agent",
) -> dict[str, Any]:
    handler = request.app.state.task_handler
    task = handler.open_terminal(task_id, mode)
    return _task_out(request, task)


@router.patch("/reorder")
def reorder_tasks(
    request: Request, body: ReorderIn,
) -> dict[str, str]:
    db = request.app.state.db
    db.tasks.update_positions(
        [(item.id, item.position) for item in body.items],
    )
    return {"status": "ok"}


@router.post("/{task_id}/merge/preview")
async def merge_preview(
    request: Request, task_id: str,
) -> dict[str, Any]:
    handler = request.app.state.task_handler
    return await handler.merge_preview(task_id)


@router.post("/{task_id}/merge")
async def merge(
    request: Request, task_id: str,
) -> dict[str, str]:
    handler = request.app.state.task_handler
    result = await handler.merge(task_id)
    return {"status": "merged", "message": result}
