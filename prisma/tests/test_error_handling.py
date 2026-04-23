import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from luml_prisma.config import AppConfig
from luml_prisma.database import Database
from luml_prisma.services.orchestrator.engine import OrchestratorEngine
from luml_prisma.services.orchestrator.models import RunConfig
from luml_prisma.services.orchestrator.nodes.base import (
    NodeExecutionContext,
    NodeResult,
    NodeServices,
)
from luml_prisma.services.orchestrator.nodes.debug import DebugNodeHandler
from luml_prisma.services.orchestrator.nodes.fork import ForkNodeHandler
from luml_prisma.services.orchestrator.nodes.implement import ImplementNodeHandler
from luml_prisma.services.orchestrator.nodes.run_node import RunNodeHandler
from luml_prisma.services.orchestrator.registry import NodeRegistry
from luml_prisma.services.pty_manager import PtyManager


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
def engine(db: Database, pty: PtyManager) -> OrchestratorEngine:
    return OrchestratorEngine(db=db, pty=pty, registry=NodeRegistry())


@pytest.fixture
def config(tmp_path: Path) -> AppConfig:
    return AppConfig(data_dir=tmp_path, db_path=tmp_path / "test.db")


def _make_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git_env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, env=git_env)
    (repo / "f.txt").write_text("hello")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, env=git_env)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "init"], check=True, env=git_env,
    )
    return repo


# --- RunConfig timeout fields ---


class TestRunConfigTimeouts:
    def test_default_timeout_values(self) -> None:
        config = RunConfig()
        assert config.implement_timeout == 1800
        assert config.run_timeout == 0
        assert config.debug_timeout == 1800
        assert config.fork_timeout == 900

    def test_custom_timeout_values(self) -> None:
        config = RunConfig(
            implement_timeout=60,
            run_timeout=120,
            debug_timeout=90,
            fork_timeout=45,
        )
        assert config.implement_timeout == 60
        assert config.run_timeout == 120
        assert config.debug_timeout == 90
        assert config.fork_timeout == 45


# --- Node handler timeout tests ---


class TestImplementNodeTimeout:
    @pytest.mark.asyncio
    async def test_timeout_fires(
        self,
        db: Database,
        pty: PtyManager,
        engine: OrchestratorEngine,
        config: AppConfig,
        tmp_path: Path,
    ) -> None:
        repo = _make_git_repo(tmp_path)
        repo_obj = db.add_repository("timeout-test", str(repo))
        run = db.add_run(repo_obj.id, "r", "")
        node = db.add_run_node(run.id, None, "implement", 0, '{"prompt": "test"}')

        handler = ImplementNodeHandler()
        services = NodeServices(db=db, pty=pty, engine=engine, config=config)

        ctx = NodeExecutionContext(
            node_id=node.id,
            run_id=run.id,
            repository_path=str(repo),
            base_branch="main",
            node_type="implement",
            depth=0,
            payload={"prompt": "test"},
            parent_result=None,
            parent_worktree_path=None,
            parent_branch=None,
            run_config={"agent_id": "claude", "implement_timeout": 1},
            services=services,
        )

        patch_cmd = (
            "luml_prisma.services.orchestrator.nodes.implement.build_agent_command"
        )
        with patch(patch_cmd, return_value="sleep 60"):
            result = await asyncio.wait_for(handler.execute(ctx), timeout=10)

        assert result.success is False
        assert "timed out" in result.error_message
        assert "1s" in result.error_message


class TestRunNodeTimeout:
    @pytest.mark.asyncio
    async def test_timeout_fires(
        self,
        db: Database,
        pty: PtyManager,
        engine: OrchestratorEngine,
        config: AppConfig,
        tmp_path: Path,
    ) -> None:
        wt = tmp_path / "wt"
        wt.mkdir()

        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "r", "")
        node = db.add_run_node(run.id, None, "run", 0)

        handler = RunNodeHandler()
        services = NodeServices(db=db, pty=pty, engine=engine, config=config)

        ctx = NodeExecutionContext(
            node_id=node.id,
            run_id=run.id,
            repository_path=str(tmp_path),
            base_branch="main",
            node_type="run",
            depth=0,
            payload={"command": "sleep 60"},
            parent_result=None,
            parent_worktree_path=str(wt),
            parent_branch="main",
            run_config={"run_timeout": 1},
            services=services,
        )

        result = await asyncio.wait_for(handler.execute(ctx), timeout=10)
        assert result.success is False
        assert "timed out" in result.error_message

    @pytest.mark.asyncio
    async def test_no_timeout_when_zero(
        self,
        db: Database,
        pty: PtyManager,
        engine: OrchestratorEngine,
        config: AppConfig,
        tmp_path: Path,
    ) -> None:
        wt = tmp_path / "wt"
        wt.mkdir()

        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "r", "")
        node = db.add_run_node(run.id, None, "run", 0)

        handler = RunNodeHandler()
        services = NodeServices(db=db, pty=pty, engine=engine, config=config)

        ctx = NodeExecutionContext(
            node_id=node.id,
            run_id=run.id,
            repository_path=str(tmp_path),
            base_branch="main",
            node_type="run",
            depth=0,
            payload={"command": "echo done"},
            parent_result=None,
            parent_worktree_path=str(wt),
            parent_branch="main",
            run_config={"run_timeout": 0},
            services=services,
        )

        async def monitor() -> NodeResult:
            task = asyncio.create_task(handler.execute(ctx))
            while not task.done():
                await asyncio.sleep(0.2)
                scrollbacks = {
                    sid: pty.get_scrollback(sid)
                    for sid in pty.get_dead_session_ids()
                }
                dead = pty.cleanup_dead()
                for sid, _, _, ec in dead:
                    engine.notify_session_exit(sid, ec, scrollbacks.get(sid, b""))
            return await task

        result = await asyncio.wait_for(monitor(), timeout=10)
        assert result.success is True


class TestDebugNodeTimeout:
    @pytest.mark.asyncio
    async def test_timeout_fires(
        self,
        db: Database,
        pty: PtyManager,
        engine: OrchestratorEngine,
        config: AppConfig,
        tmp_path: Path,
    ) -> None:
        wt = tmp_path / "wt"
        wt.mkdir()

        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "r", "")
        node = db.add_run_node(run.id, None, "debug", 0)

        handler = DebugNodeHandler()
        services = NodeServices(db=db, pty=pty, engine=engine, config=config)

        ctx = NodeExecutionContext(
            node_id=node.id,
            run_id=run.id,
            repository_path=str(tmp_path),
            base_branch="main",
            node_type="debug",
            depth=0,
            payload={
                "objective": "fix",
                "failure_context": {"exit_code": 1, "logs": "err"},
            },
            parent_result=None,
            parent_worktree_path=str(wt),
            parent_branch="main",
            run_config={"agent_id": "claude", "debug_timeout": 1},
            services=services,
        )

        patch_cmd = (
            "luml_prisma.services.orchestrator.nodes.debug.build_agent_command"
        )
        with patch(patch_cmd, return_value="sleep 60"):
            result = await asyncio.wait_for(handler.execute(ctx), timeout=10)

        assert result.success is False
        assert "timed out" in result.error_message


class TestForkNodeTimeout:
    @pytest.mark.asyncio
    async def test_timeout_fires(
        self,
        db: Database,
        pty: PtyManager,
        engine: OrchestratorEngine,
        config: AppConfig,
        tmp_path: Path,
    ) -> None:
        wt = tmp_path / "wt"
        wt.mkdir()

        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "r", "")
        node = db.add_run_node(run.id, None, "fork", 0)

        handler = ForkNodeHandler()
        services = NodeServices(db=db, pty=pty, engine=engine, config=config)

        ctx = NodeExecutionContext(
            node_id=node.id,
            run_id=run.id,
            repository_path=str(tmp_path),
            base_branch="main",
            node_type="fork",
            depth=0,
            payload={"objective": "decompose"},
            parent_result=None,
            parent_worktree_path=str(wt),
            parent_branch="main",
            run_config={"agent_id": "claude", "fork_timeout": 1},
            services=services,
        )

        patch_cmd = (
            "luml_prisma.services.orchestrator.nodes.fork.build_agent_command"
        )
        with patch(patch_cmd, return_value="sleep 60"):
            result = await asyncio.wait_for(handler.execute(ctx), timeout=10)

        assert result.success is False
        assert "timed out" in result.error_message


# --- PTY crash recovery tests ---


class TestPtyCrashRecovery:
    @pytest.mark.asyncio
    async def test_reader_thread_sends_none_on_process_crash(
        self, pty: PtyManager,
    ) -> None:
        session = pty.spawn("t1", ["bash", "-c", "exit 1"], cwd="/tmp")
        queue = pty.subscribe(session.session_id)

        got_none = False
        try:
            while True:
                data = await asyncio.wait_for(queue.get(), timeout=5)
                if data is None:
                    got_none = True
                    break
        except TimeoutError:
            pass

        assert got_none

    @pytest.mark.asyncio
    async def test_cleanup_dead_returns_exit_code(self, pty: PtyManager) -> None:
        session = pty.spawn("t1", ["bash", "-c", "exit 42"], cwd="/tmp")
        await asyncio.sleep(0.5)
        dead = pty.cleanup_dead()
        found = [
            (sid, ec) for sid, _, _, ec in dead if sid == session.session_id
        ]
        assert len(found) == 1
        assert found[0][1] == 42

    def test_terminate_handles_already_dead_process(self, pty: PtyManager) -> None:
        session = pty.spawn("t1", ["true"], cwd="/tmp")
        session.process.wait()
        pty.terminate(session.session_id)
        assert not pty.has_session(session.session_id)

    def test_terminate_handles_timeout_after_sigkill(self, pty: PtyManager) -> None:
        session = pty.spawn("t1", ["sleep", "60"], cwd="/tmp")
        pty.terminate(session.session_id)
        assert not pty.has_session(session.session_id)


# --- PTY spawn error handling tests ---


class TestPtySpawnErrors:
    def test_spawn_with_invalid_cwd(self, pty: PtyManager) -> None:
        with pytest.raises(OSError, match="No such file"):
            pty.spawn("t1", ["echo", "hi"], cwd="/nonexistent/path/xyz")

    def test_spawn_cleans_up_fds_on_popen_failure(self) -> None:
        mgr = PtyManager()
        try:
            open_fds_before = _count_open_fds()
            with pytest.raises(OSError, match="No such file"):
                mgr.spawn(
                    "t1", ["echo", "hi"],
                    cwd="/nonexistent/path/xyz",
                )
            open_fds_after = _count_open_fds()
            assert open_fds_after <= open_fds_before + 1
        finally:
            mgr.shutdown()

    def test_spawn_openpty_failure(self) -> None:
        mgr = PtyManager()
        try:
            openpty_path = (
                "luml_prisma.services.pty_manager.pty.openpty"
            )
            with (
                patch(openpty_path, side_effect=OSError("mock")),
                pytest.raises(OSError, match="Failed to open PTY"),
            ):
                mgr.spawn("t1", ["echo", "hi"], cwd="/tmp")
        finally:
            mgr.shutdown()


# --- Engine exception logging test ---


class TestEngineExceptionLogging:
    @pytest.mark.asyncio
    async def test_run_node_logs_exception(
        self,
        db: Database,
        pty: PtyManager,
    ) -> None:
        registry = NodeRegistry()

        class FailingHandler:
            def type_id(self) -> str:
                return "implement"

            def validate_payload(self, payload: dict[str, Any]) -> None:
                pass

            async def execute(self, ctx: NodeExecutionContext) -> NodeResult:
                raise RuntimeError("boom")

            def can_fork(self, result: NodeResult) -> bool:
                return False

            def default_next_nodes(self, result: NodeResult) -> list:
                return []

        registry.register(FailingHandler())

        engine = OrchestratorEngine(db=db, pty=pty, registry=registry)
        pid = db.list_repositories()[0].id
        config = RunConfig()
        run_id = await engine.create_run(pid, "r", "", config, {"prompt": "test"})
        await engine.start_run(run_id)

        with patch("luml_prisma.services.orchestrator.engine.logger") as mock_logger:
            await engine._schedule_tick()
            await asyncio.sleep(0.1)

        mock_logger.exception.assert_called()
        call_args = mock_logger.exception.call_args
        assert "failed" in call_args[0][0].lower()


# --- RunCreateIn schema tests ---


class TestRunCreateInTimeouts:
    def test_schema_includes_timeout_fields(self) -> None:
        from luml_prisma.schemas.run import RunCreateIn

        data = RunCreateIn(
            repository_id="r1",
            name="test",
            objective="obj",
            implement_timeout=60,
            run_timeout=120,
            debug_timeout=90,
            fork_timeout=45,
        )
        assert data.implement_timeout == 60
        assert data.run_timeout == 120
        assert data.debug_timeout == 90
        assert data.fork_timeout == 45

    def test_schema_default_timeout_values(self) -> None:
        from luml_prisma.schemas.run import RunCreateIn

        data = RunCreateIn(
            repository_id="r1",
            name="test",
            objective="obj",
        )
        assert data.implement_timeout == 1800
        assert data.run_timeout == 0
        assert data.debug_timeout == 1800
        assert data.fork_timeout == 900


def _count_open_fds() -> int:
    return len(os.listdir(f"/proc/{os.getpid()}/fd"))
