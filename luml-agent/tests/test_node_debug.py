import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from luml_agent.config import AppConfig
from luml_agent.models import Database
from luml_agent.orchestrator.engine import OrchestratorEngine
from luml_agent.orchestrator.nodes.base import (
    NodeExecutionContext,
    NodeResult,
    NodeServices,
)
from luml_agent.orchestrator.nodes.debug import DebugNodeHandler
from luml_agent.orchestrator.registry import NodeRegistry
from luml_agent.pty_manager import PtyManager

_PATCH_CMD = "luml_agent.orchestrator.nodes.debug.build_agent_command"


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


class TestDebugNodeHandler:
    def test_type_id(self) -> None:
        assert DebugNodeHandler().type_id() == "debug"

    @pytest.mark.asyncio
    async def test_execute_no_worktree(
        self,
        db: Database,
        pty: PtyManager,
        engine: OrchestratorEngine,
        config: AppConfig,
    ) -> None:
        handler = DebugNodeHandler()
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "r", "")
        node = db.add_run_node(run.id, None, "debug", 1)
        ctx = NodeExecutionContext(
            node_id=node.id,
            run_id=run.id,
            repository_path="/tmp",
            base_branch="main",
            node_type="debug",
            depth=1,
            payload={
                "failure_context": {
                    "exit_code": 1, "logs": "error",
                },
            },
            parent_result=None,
            parent_worktree_path=None,
            parent_branch=None,
            run_config={"agent_id": "claude"},
            services=NodeServices(
                db=db, pty=pty,
                engine=engine, config=config,
            ),
        )
        result = await handler.execute(ctx)
        assert result.success is False
        assert "worktree" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_execute_success(
        self,
        db: Database,
        pty: PtyManager,
        engine: OrchestratorEngine,
        config: AppConfig,
        tmp_path: Path,
    ) -> None:
        handler = DebugNodeHandler()
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "r", "fix the bug")
        parent = db.add_run_node(run.id, None, "run", 0)
        node = db.add_run_node(
            run.id, parent.id, "debug", 1,
        )

        ctx = NodeExecutionContext(
            node_id=node.id,
            run_id=run.id,
            repository_path=str(tmp_path),
            base_branch="main",
            node_type="debug",
            depth=1,
            payload={
                "failure_context": {
                    "exit_code": 1,
                    "logs": "test failed: assertion error",
                },
                "objective": "fix the bug",
            },
            parent_result=None,
            parent_worktree_path=str(tmp_path),
            parent_branch="agent/test",
            run_config={"agent_id": "claude"},
            services=NodeServices(
                db=db, pty=pty,
                engine=engine, config=config,
            ),
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

        with patch(_PATCH_CMD, return_value="true"):
            result = await asyncio.wait_for(
                run_with_monitor(), timeout=15,
            )

        assert result.artifacts.get("worktree_path") == str(
            tmp_path,
        )
        assert result.artifacts.get("session_id")

    def test_can_fork(self) -> None:
        assert DebugNodeHandler().can_fork(
            NodeResult(success=True),
        ) is False
