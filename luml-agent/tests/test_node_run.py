import asyncio
from pathlib import Path

import pytest

from luml_agent.config import AppConfig
from luml_agent.models import Database
from luml_agent.orchestrator.engine import OrchestratorEngine
from luml_agent.orchestrator.nodes.base import (
    NodeExecutionContext,
    NodeResult,
    NodeServices,
)
from luml_agent.orchestrator.nodes.run_node import (
    RunNodeHandler,
)
from luml_agent.orchestrator.registry import NodeRegistry
from luml_agent.pty_manager import PtyManager


@pytest.fixture
def db() -> Database:
    d = Database()
    d.add_repository("test", "/tmp/test-repo")
    return d


@pytest.fixture
def pty() -> PtyManager:
    mgr = PtyManager()
    yield mgr
    mgr.shutdown()


@pytest.fixture
def engine(
    db: Database, pty: PtyManager,
) -> OrchestratorEngine:
    return OrchestratorEngine(
        db=db, pty=pty, registry=NodeRegistry(),
    )


@pytest.fixture
def config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        data_dir=tmp_path, db_path=tmp_path / "test.db",
    )


def _make_ctx(
    db: Database,
    pty: PtyManager,
    engine: OrchestratorEngine,
    config: AppConfig,
    command: str,
    worktree_path: str,
) -> NodeExecutionContext:
    pid = db.list_repositories()[0].id
    run = db.add_run(pid, "r", "")
    node = db.add_run_node(run.id, None, "run", 0)
    return NodeExecutionContext(
        node_id=node.id,
        run_id=run.id,
        repository_path="/tmp",
        base_branch="main",
        node_type="run",
        depth=0,
        payload={"command": command},
        parent_result=None,
        parent_worktree_path=worktree_path,
        parent_branch="test-branch",
        run_config={},
        services=NodeServices(
            db=db, pty=pty, engine=engine, config=config,
        ),
    )


class TestRunNodeHandler:
    def test_type_id(self) -> None:
        handler = RunNodeHandler()
        assert handler.type_id() == "run"

    @pytest.mark.asyncio
    async def test_execute_captures_stdout_metric(
        self,
        db: Database,
        pty: PtyManager,
        engine: OrchestratorEngine,
        config: AppConfig,
        tmp_path: Path,
    ) -> None:
        handler = RunNodeHandler()
        cmd = (
            "python3 -c \"import json;"
            " print('working...');"
            " print(json.dumps({'type':"
            " 'luml-agent-message',"
            " 'metric': 0.42}))\" "
        )
        ctx = _make_ctx(
            db, pty, engine, config, cmd, str(tmp_path),
        )

        async def run_with_monitor() -> NodeResult:
            task = asyncio.create_task(
                handler.execute(ctx),
            )
            while not task.done():
                await asyncio.sleep(0.2)
                scrollbacks = {
                    sid: pty.get_scrollback(sid)
                    for sid in pty.get_dead_session_ids()
                }
                dead = pty.cleanup_dead()
                for sid, _, _, ec in dead:
                    engine.notify_session_exit(
                        sid, ec,
                        scrollbacks.get(sid, b""),
                    )
            return await task

        result = await asyncio.wait_for(
            run_with_monitor(), timeout=10,
        )

        assert result.success is True
        assert result.artifacts["metric"] == 0.42

    @pytest.mark.asyncio
    async def test_execute_success(
        self,
        db: Database,
        pty: PtyManager,
        engine: OrchestratorEngine,
        config: AppConfig,
        tmp_path: Path,
    ) -> None:
        handler = RunNodeHandler()
        ctx = _make_ctx(
            db, pty, engine, config,
            "echo hello && sleep 0.1",
            str(tmp_path),
        )

        async def run_with_monitor() -> NodeResult:
            task = asyncio.create_task(
                handler.execute(ctx),
            )
            while not task.done():
                await asyncio.sleep(0.2)
                scrollbacks = {
                    sid: pty.get_scrollback(sid)
                    for sid in pty.get_dead_session_ids()
                }
                dead = pty.cleanup_dead()
                for sid, _, _, ec in dead:
                    engine.notify_session_exit(
                        sid, ec,
                        scrollbacks.get(sid, b""),
                    )
            return await task

        result = await asyncio.wait_for(
            run_with_monitor(), timeout=10,
        )

        assert result.success is True
        assert result.artifacts["exit_code"] == 0
        assert "hello" in result.artifacts["logs"]

    @pytest.mark.asyncio
    async def test_execute_failure(
        self,
        db: Database,
        pty: PtyManager,
        engine: OrchestratorEngine,
        config: AppConfig,
        tmp_path: Path,
    ) -> None:
        handler = RunNodeHandler()
        ctx = _make_ctx(
            db, pty, engine, config,
            "echo fail && sleep 0.1 && exit 1",
            str(tmp_path),
        )

        async def run_with_monitor() -> NodeResult:
            task = asyncio.create_task(
                handler.execute(ctx),
            )
            while not task.done():
                await asyncio.sleep(0.2)
                scrollbacks = {
                    sid: pty.get_scrollback(sid)
                    for sid in pty.get_dead_session_ids()
                }
                dead = pty.cleanup_dead()
                for sid, _, _, ec in dead:
                    engine.notify_session_exit(
                        sid, ec,
                        scrollbacks.get(sid, b""),
                    )
            return await task

        result = await asyncio.wait_for(
            run_with_monitor(), timeout=10,
        )

        assert result.success is False
        assert result.artifacts["exit_code"] == 1

    @pytest.mark.asyncio
    async def test_no_command_returns_error(
        self,
        db: Database,
        pty: PtyManager,
        engine: OrchestratorEngine,
        config: AppConfig,
    ) -> None:
        handler = RunNodeHandler()
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "r", "")
        node = db.add_run_node(run.id, None, "run", 0)
        ctx = NodeExecutionContext(
            node_id=node.id,
            run_id=run.id,
            repository_path="/tmp",
            base_branch="main",
            node_type="run",
            depth=0,
            payload={},
            parent_result=None,
            parent_worktree_path="/tmp",
            parent_branch="b",
            run_config={},
            services=NodeServices(
                db=db, pty=pty,
                engine=engine, config=config,
            ),
        )
        result = await handler.execute(ctx)
        assert result.success is False
        assert "No command" in result.error_message

    @pytest.mark.asyncio
    async def test_no_worktree_returns_error(
        self,
        db: Database,
        pty: PtyManager,
        engine: OrchestratorEngine,
        config: AppConfig,
    ) -> None:
        handler = RunNodeHandler()
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "r", "")
        node = db.add_run_node(run.id, None, "run", 0)
        ctx = NodeExecutionContext(
            node_id=node.id,
            run_id=run.id,
            repository_path="/tmp",
            base_branch="main",
            node_type="run",
            depth=0,
            payload={"command": "echo hi"},
            parent_result=None,
            parent_worktree_path=None,
            parent_branch=None,
            run_config={},
            services=NodeServices(
                db=db, pty=pty,
                engine=engine, config=config,
            ),
        )
        result = await handler.execute(ctx)
        assert result.success is False
        assert "worktree" in result.error_message.lower()

    def test_can_fork(self) -> None:
        handler = RunNodeHandler()
        assert handler.can_fork(
            NodeResult(success=True),
        ) is False

    def test_parse_metrics(self) -> None:
        handler = RunNodeHandler()
        result = handler._parse_metrics(
            "accuracy: 0.95\nloss: 0.05",
            r"accuracy: ([\d.]+)",
        )
        assert result["raw_matches"] == ["0.95"]

    def test_parse_metrics_no_pattern(self) -> None:
        handler = RunNodeHandler()
        assert handler._parse_metrics("data", None) == {}
