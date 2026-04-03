import asyncio
import json
import os
import subprocess
from pathlib import Path

import pytest

from luml_agent.database import Database
from luml_agent.services.orchestrator.engine import OrchestratorEngine
from luml_agent.services.orchestrator.models import (
    NodeStatus,
    NodeType,
    RunConfig,
    RunStatus,
)
from luml_agent.services.orchestrator.registry import NodeRegistry
from luml_agent.services.pty_manager import PtyManager

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "t@t",
}


def _init_repo(path: Path) -> None:
    subprocess.run(
        ["git", "init", "-b", "main", str(path)],
        check=True, env=GIT_ENV,
    )
    (path / ".gitignore").write_text(
        ".luml-agent/mock-state.json\n"
        ".luml-agent/result.json\n"
    )
    (path / "README.md").write_text("test repo")
    subprocess.run(
        ["git", "-C", str(path), "add", "."],
        check=True, env=GIT_ENV,
    )
    subprocess.run(
        ["git", "-C", str(path), "commit", "-m", "init"],
        check=True, env=GIT_ENV,
    )


async def _drive_engine(
    engine: OrchestratorEngine,
    pty: PtyManager,
    timeout: float = 30,
) -> None:
    exit_sent_at: dict[str, float] = {}
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        now = asyncio.get_event_loop().time()
        scrollbacks = {
            sid: pty.get_scrollback(sid)
            for sid in pty.get_dead_session_ids()
        }
        dead = pty.cleanup_dead()
        for sid, _, _, ec in dead:
            engine.notify_session_exit(
                sid, ec, scrollbacks.get(sid, b""),
            )

        for sid in list(pty._sessions):
            if (
                pty.is_alive(sid)
                and now - exit_sent_at.get(sid, 0) > 2
            ):
                try:
                    pty.write(sid, b"/exit\n")
                    exit_sent_at[sid] = now
                except (KeyError, OSError):
                    pass

        await engine._schedule_tick()
        await asyncio.sleep(0.1)

        runs = engine._db.list_runs()
        if runs and runs[0].status in (
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
            RunStatus.CANCELED,
        ):
            return

    raise TimeoutError("Engine did not complete within timeout")


@pytest.fixture
def db() -> Database:
    return Database()


@pytest.fixture
def pty() -> PtyManager:
    mgr = PtyManager()
    yield mgr
    mgr.shutdown()


@pytest.fixture
def registry() -> NodeRegistry:
    from luml_agent.services.orchestrator.nodes.debug import DebugNodeHandler
    from luml_agent.services.orchestrator.nodes.fork import ForkNodeHandler
    from luml_agent.services.orchestrator.nodes.implement import (
        ImplementNodeHandler,
    )
    from luml_agent.services.orchestrator.nodes.run_node import (
        RunNodeHandler,
    )

    reg = NodeRegistry()
    reg.register(ImplementNodeHandler())
    reg.register(RunNodeHandler())
    reg.register(DebugNodeHandler())
    reg.register(ForkNodeHandler())
    return reg


@pytest.fixture
def engine(
    db: Database, pty: PtyManager, registry: NodeRegistry,
) -> OrchestratorEngine:
    return OrchestratorEngine(
        db=db, pty=pty, registry=registry,
    )


class TestImplementOnly:
    @pytest.mark.asyncio
    async def test_succeed_and_writes_step_py(
        self,
        db: Database,
        pty: PtyManager,
        engine: OrchestratorEngine,
        tmp_path: Path,
    ) -> None:
        repo = tmp_path / "repo"
        _init_repo(repo)

        repository = db.add_repository("test", str(repo))
        run_config = RunConfig(
            agent_id="mock", run_command_template="",
        )
        run_id = await engine.create_run(
            repository_id=repository.id,
            name="test-run",
            objective="test",
            config=run_config,
            root_payload={"prompt": "do something"},
        )
        await engine.start_run(run_id)
        await _drive_engine(engine, pty)

        run = db.get_run(run_id)
        assert run is not None
        assert run.status == RunStatus.FAILED

        nodes = db.list_run_nodes(run_id)
        assert len(nodes) == 1
        assert nodes[0].status == NodeStatus.SUCCEEDED

        wt = nodes[0].worktree_path
        assert (
            (Path(wt) / "step.py").read_text()
            == "# implement step 1\n"
        )


class TestImplementPlusRun:
    @pytest.mark.asyncio
    async def test_both_succeed(
        self,
        db: Database,
        pty: PtyManager,
        engine: OrchestratorEngine,
        tmp_path: Path,
    ) -> None:
        repo = tmp_path / "repo"
        _init_repo(repo)

        repository = db.add_repository("test", str(repo))
        run_config = RunConfig(
            agent_id="mock",
            run_command_template="mock-agent run",
            max_depth=2,
        )
        run_id = await engine.create_run(
            repository_id=repository.id,
            name="test-run",
            objective="test",
            config=run_config,
            root_payload={"prompt": "implement"},
        )
        await engine.start_run(run_id)
        await _drive_engine(engine, pty, timeout=60)

        run = db.get_run(run_id)
        assert run is not None
        assert run.status == RunStatus.FAILED

        nodes = db.list_run_nodes(run_id)
        assert len(nodes) >= 2

        implement_node = next(
            n for n in nodes
            if n.node_type == NodeType.IMPLEMENT
        )
        run_node = next(
            n for n in nodes if n.node_type == NodeType.RUN
        )

        assert implement_node.status == NodeStatus.SUCCEEDED
        assert run_node.status == NodeStatus.SUCCEEDED

        run_result = json.loads(run_node.result_json)
        assert run_result["artifacts"]["metrics"]["passed"] == 1

        wt = implement_node.worktree_path
        content = (Path(wt) / "step.py").read_text()
        assert content.startswith("# implement step ")
