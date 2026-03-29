import asyncio
import contextlib
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from luml_agent.api import aggregate_router
from luml_agent.config import AppConfig, load_config
from luml_agent.database import Database
from luml_agent.handlers.node import NodeHandler
from luml_agent.handlers.repository import RepositoryHandler
from luml_agent.handlers.run import RunHandler
from luml_agent.handlers.task import TaskHandler
from luml_agent.infra.exceptions import ApplicationError
from luml_agent.schemas.task import TaskStatus
from luml_agent.services.orchestrator.engine import OrchestratorEngine
from luml_agent.services.orchestrator.registry import (
    register_all_handlers,
)
from luml_agent.services.pty_manager import PtyManager


async def _monitor_loop(app: FastAPI) -> None:
    db: Database = app.state.db
    pty: PtyManager = app.state.pty
    engine: OrchestratorEngine = app.state.engine
    while True:
        await asyncio.sleep(2)
        scrollbacks: dict[str, bytes] = {}
        for sid in pty.get_dead_session_ids():
            scrollbacks[sid] = pty.get_scrollback(sid)
        dead = pty.cleanup_dead()
        pty.check_idle_sessions()
        for sid in pty.get_agent_session_ids():
            if pty.is_session_waiting_notified(sid):
                engine.notify_session_idle(sid)
            else:
                engine.notify_session_active(sid)
            engine.maybe_auto_terminate(sid, pty)
        for (
            session_id,
            task_id,
            session_type,
            exit_code,
        ) in dead:
            engine.notify_session_exit(
                session_id,
                exit_code,
                scrollbacks.get(session_id, b""),
            )
            if session_type != "agent":
                continue
            task = db.get_task(task_id)
            if (
                task
                and task.status == TaskStatus.RUNNING
            ):
                db.update_task_status(
                    task_id, TaskStatus.SUCCEEDED,
                )


@asynccontextmanager
async def _lifespan(
    app: FastAPI,
) -> AsyncGenerator[None, None]:
    config: AppConfig = load_config()
    db = Database(config.db_path)
    pty = PtyManager()

    for task in db.list_tasks():
        if task.status == TaskStatus.RUNNING:
            db.update_task_status(
                task.id, TaskStatus.FAILED,
            )

    registry = register_all_handlers()
    engine = OrchestratorEngine(
        db=db, pty=pty, registry=registry,
    )
    await engine.start()

    app.state.config = config
    app.state.db = db
    app.state.pty = pty
    app.state.engine = engine

    app.state.repository_handler = RepositoryHandler(
        repository_repo=db.repositories,
        task_repo=db.tasks,
        pty=pty,
    )
    app.state.task_handler = TaskHandler(
        task_repo=db.tasks,
        repository_repo=db.repositories,
        pty=pty,
        config=config,
    )
    app.state.run_handler = RunHandler(
        run_repo=db.runs,
        node_repo=db.nodes,
        repository_repo=db.repositories,
        engine=engine,
    )
    app.state.node_handler = NodeHandler(
        node_repo=db.nodes,
        pty=pty,
        engine=engine,
    )

    monitor_task = asyncio.create_task(
        _monitor_loop(app),
    )
    app.state.monitor_task = monitor_task

    yield

    monitor_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await monitor_task
    await engine.stop()
    pty.shutdown()
    db.close()


async def _handle_app_error(
    request: Request,
    exc: ApplicationError,
) -> JSONResponse:
    from luml_agent.infra.exceptions import MergeConflictError

    content: dict[str, object] = {"detail": exc.message}
    if isinstance(exc, MergeConflictError):
        content["conflicting_files"] = exc.conflicting_files
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
    )


def _origins_to_regex(patterns: list[str]) -> str:
    parts: list[str] = []
    for p in patterns:
        if "*" not in p:
            parts.append(re.escape(p))
            continue
        scheme, _, rest = p.partition("://")
        host_pattern = rest
        if host_pattern == "*":
            escaped = ".*"
        elif host_pattern.startswith("*."):
            escaped = r".*\." + re.escape(host_pattern[2:])
        elif host_pattern.endswith(":*"):
            escaped = re.escape(host_pattern[:-2]) + r"(:\d+)?"
        else:
            escaped = re.escape(host_pattern).replace(r"\*", ".*")
        parts.append(re.escape(scheme) + "://" + escaped)
    return "^(" + "|".join(parts) + ")$"


def create_app() -> FastAPI:
    config = load_config()
    app = FastAPI(
        title="LUML Agent", lifespan=_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=_origins_to_regex(config.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(
        ApplicationError, _handle_app_error,  # type: ignore[arg-type]
    )
    app.include_router(aggregate_router())
    return app
