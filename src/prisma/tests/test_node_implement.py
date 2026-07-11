import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from luml_prisma.config import AppConfig
from luml_prisma.database import Database
from luml_prisma.services.orchestrator.engine import OrchestratorEngine
from luml_prisma.services.orchestrator.nodes.base import (
    NodeExecutionContext,
    NodeServices,
)
from luml_prisma.services.orchestrator.nodes.implement import (
    ImplementNodeHandler,
)
from luml_prisma.services.orchestrator.registry import NodeRegistry
from luml_prisma.services.pty_manager import PtyManager

_PATCH_CMD = "luml_prisma.services.orchestrator.nodes.implement.build_agent_command"


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


class TestImplementNodeHandler:
    def test_type_id(self) -> None:
        handler = ImplementNodeHandler()
        assert handler.type_id() == "implement"

    def test_validate_payload_requires_prompt(self) -> None:
        handler = ImplementNodeHandler()
        with pytest.raises(ValueError, match="prompt"):
            handler.validate_payload({})
        handler.validate_payload({"prompt": "hello"})

    @pytest.mark.asyncio
    async def test_execute_success(
        self,
        db: Database,
        pty: PtyManager,
        engine: OrchestratorEngine,
        config: AppConfig,
        tmp_path: Path,
    ) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        git_env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "t@t",
        }
        subprocess.run(
            ["git", "init", "-b", "main", str(repo)],
            check=True, env=git_env,
        )
        (repo / "f.txt").write_text("hello")
        subprocess.run(
            ["git", "-C", str(repo), "add", "."],
            check=True, env=git_env,
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", "init"],
            check=True, env=git_env,
        )

        repo_obj = db.add_repository("test", str(repo))
        run = db.add_run(repo_obj.id, "r", "")
        node = db.add_run_node(
            run.id, None, "implement", 0,
            '{"prompt": "test"}',
        )

        handler = ImplementNodeHandler()
        services = NodeServices(
            db=db, pty=pty, engine=engine, config=config,
        )

        ctx = NodeExecutionContext(
            node_id=node.id,
            run_id=run.id,
            repository_path=str(repo),
            base_branch="main",
            node_type="implement",
            depth=0,
            payload={"prompt": "echo done"},
            parent_result=None,
            parent_worktree_path=None,
            parent_branch=None,
            run_config={"agent_id": "claude"},
            services=services,
        )

        async def run_with_monitor() -> object:
            task = asyncio.create_task(handler.execute(ctx))
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

        assert result.artifacts.get("worktree_path")
        assert result.artifacts.get("branch")

    @pytest.mark.asyncio
    async def test_nested_implement_branches_from_parent(
        self,
        db: Database,
        pty: PtyManager,
        engine: OrchestratorEngine,
        config: AppConfig,
        tmp_path: Path,
    ) -> None:
        wt_dir = tmp_path / "wt"
        wt_dir.mkdir()

        handler = ImplementNodeHandler()
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "r", "")
        node = db.add_run_node(
            run.id, None, "implement", 1,
        )

        ctx = NodeExecutionContext(
            node_id=node.id,
            run_id=run.id,
            repository_path=str(tmp_path),
            base_branch="main",
            node_type="implement",
            depth=1,
            payload={"prompt": "test"},
            parent_result=None,
            parent_worktree_path=str(tmp_path),
            parent_branch="agent/parent-abc",
            run_config={"agent_id": "mock"},
            services=NodeServices(
                db=db, pty=pty,
                engine=engine, config=config,
            ),
        )

        captured_branch: list[str] = []
        original_create = AsyncMock(
            return_value=(str(wt_dir), "agent/child-def"),
        )

        async def capture_create(
            *args: Any, **kwargs: Any,  # noqa: ANN401
        ) -> tuple[str, str]:
            captured_branch.append(args[2])
            return await original_create(*args, **kwargs)

        mock_create = AsyncMock(side_effect=capture_create)
        with (
            patch(
                "luml_prisma.services.orchestrator.nodes"
                ".implement.create_worktree",
                mock_create,
            ),
            patch(
                "luml_prisma.services.orchestrator.nodes"
                ".implement.get_agent",
                return_value=None,
            ),
        ):
            result = await handler.execute(ctx)

        assert captured_branch[0] == "agent/parent-abc"
        assert result.success is False
        assert "Unknown agent" in result.error_message

    @pytest.mark.asyncio
    async def test_root_implement_branches_from_base(
        self,
        db: Database,
        pty: PtyManager,
        engine: OrchestratorEngine,
        config: AppConfig,
        tmp_path: Path,
    ) -> None:
        wt_dir = tmp_path / "wt"
        wt_dir.mkdir()

        handler = ImplementNodeHandler()
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "r", "")
        node = db.add_run_node(
            run.id, None, "implement", 0,
        )

        ctx = NodeExecutionContext(
            node_id=node.id,
            run_id=run.id,
            repository_path=str(tmp_path),
            base_branch="main",
            node_type="implement",
            depth=0,
            payload={"prompt": "test"},
            parent_result=None,
            parent_worktree_path=None,
            parent_branch=None,
            run_config={"agent_id": "mock"},
            services=NodeServices(
                db=db, pty=pty,
                engine=engine, config=config,
            ),
        )

        captured_branch: list[str] = []
        original_create = AsyncMock(
            return_value=(str(wt_dir), "agent/root-abc"),
        )

        async def capture_create(
            *args: Any, **kwargs: Any,  # noqa: ANN401
        ) -> tuple[str, str]:
            captured_branch.append(args[2])
            return await original_create(*args, **kwargs)

        mock_create = AsyncMock(side_effect=capture_create)
        with (
            patch(
                "luml_prisma.services.orchestrator.nodes"
                ".implement.create_worktree",
                mock_create,
            ),
            patch(
                "luml_prisma.services.orchestrator.nodes"
                ".implement.get_agent",
                return_value=None,
            ),
        ):
            result = await handler.execute(ctx)

        assert captured_branch[0] == "main"
        assert result.success is False

    def test_can_fork(self) -> None:
        handler = ImplementNodeHandler()
        from luml_prisma.services.orchestrator.nodes.base import (
            NodeResult,
        )

        assert handler.can_fork(
            NodeResult(success=True),
        ) is True
        assert handler.can_fork(
            NodeResult(success=False),
        ) is False
