import asyncio
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from luml_prisma.config import AppConfig
from luml_prisma.database import Database
from luml_prisma.services.orchestrator.engine import OrchestratorEngine
from luml_prisma.services.orchestrator.nodes.base import (
    NodeExecutionContext,
    NodeResult,
    NodeServices,
)
from luml_prisma.services.orchestrator.nodes.debug import DebugNodeHandler
from luml_prisma.services.orchestrator.registry import NodeRegistry
from luml_prisma.services.pty_manager import PtyManager

_PATCH_CMD = "luml_prisma.services.orchestrator.nodes.debug.build_agent_command"


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


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True, capture_output=True,
    )


class TestComputeGitDiff:
    @pytest.fixture
    def worktree(self, tmp_path: Path) -> Path:
        repo = tmp_path / "repo"
        (repo / "data").mkdir(parents=True)
        (repo / "data" / "big.csv").write_text("x,y\n" * 20000)
        (repo / "main.py").write_text("print('v1')\n")
        _git(repo, "init", "-b", "main")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "base")
        _git(repo, "checkout", "-b", "prisma/branch")
        shutil.rmtree(repo / "data")
        (repo / "data").symlink_to(tmp_path / "shared-data")
        (repo / "main.py").write_text("print('v2')\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "agent changes")
        return repo

    def test_excludes_shared_paths(self, worktree: Path) -> None:
        diff = DebugNodeHandler._compute_git_diff(
            str(worktree), "main", exclude=["data"],
        )
        assert "v2" in diff
        assert "big.csv" not in diff

    def test_truncates_to_budget(self, worktree: Path) -> None:
        diff = DebugNodeHandler._compute_git_diff(
            str(worktree), "main", max_chars=500,
        )
        assert len(diff) < 600
        assert diff.endswith("(diff truncated to 500 chars)")


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
