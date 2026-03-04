import json
from pathlib import Path

import pytest

from luml_agent.models import Database
from luml_agent.orchestrator.engine import OrchestratorEngine
from luml_agent.orchestrator.models import (
    NodeStatus,
    NodeType,
    RunConfig,
    RunStatus,
)
from luml_agent.orchestrator.registry import register_all_handlers
from luml_agent.pty_manager import PtyManager


@pytest.fixture
def db(tmp_path: Path) -> Database:
    d = Database()
    d.add_repository("test", str(tmp_path))
    return d


@pytest.fixture
def pty() -> PtyManager:
    p = PtyManager()
    yield p
    p.shutdown()


@pytest.fixture
def engine(
    db: Database, pty: PtyManager,
) -> OrchestratorEngine:
    registry = register_all_handlers()
    return OrchestratorEngine(
        db=db, pty=pty, registry=registry,
    )


def make_config(**overrides: object) -> RunConfig:
    defaults = {
        "max_depth": 3,
        "max_children_per_fork": 3,
        "max_debug_retries": 2,
        "max_concurrency": 2,
        "run_command_template": "",
        "agent_id": "echo",
        "fork_auto_approve": True,
    }
    defaults.update(overrides)
    return RunConfig(**defaults)  # type: ignore[arg-type]


class TestCancelRun:
    @pytest.mark.asyncio
    async def test_cancel_pending_run(
        self,
        engine: OrchestratorEngine,
        db: Database,
    ) -> None:
        pid = db.list_repositories()[0].id
        config = make_config()
        run_id = await engine.create_run(
            pid, "test", "obj", config, {"prompt": "x"},
        )
        await engine.start_run(run_id)

        await engine.cancel_run(run_id)

        run = db.get_run(run_id)
        assert run is not None
        assert run.status == RunStatus.CANCELED

        nodes = db.list_run_nodes(run_id)
        for node in nodes:
            assert node.status == NodeStatus.CANCELED

    @pytest.mark.asyncio
    async def test_cancel_run_with_queued_nodes(
        self,
        engine: OrchestratorEngine,
        db: Database,
    ) -> None:
        pid = db.list_repositories()[0].id
        config = make_config()
        run_id = await engine.create_run(
            pid, "test", "obj", config, {"prompt": "x"},
        )

        root = db.list_run_nodes(run_id)[0]
        child = db.add_run_node(
            run_id, root.id, NodeType.RUN, 1,
            json.dumps({"command": "echo"}),
        )
        db.add_run_edge(
            run_id, root.id, child.id, "auto",
        )

        await engine.start_run(run_id)
        await engine.cancel_run(run_id)

        for node in db.list_run_nodes(run_id):
            assert node.status == NodeStatus.CANCELED

    @pytest.mark.asyncio
    async def test_cancel_emits_events(
        self,
        engine: OrchestratorEngine,
        db: Database,
    ) -> None:
        pid = db.list_repositories()[0].id
        config = make_config()
        run_id = await engine.create_run(
            pid, "test", "obj", config, {"prompt": "x"},
        )
        await engine.start_run(run_id)

        queue = engine.subscribe(run_id)
        await engine.cancel_run(run_id)

        events = []
        while not queue.empty():
            events.append(await queue.get())

        status_events = [
            e for e in events
            if e["type"] == "node_status_changed"
        ]
        assert len(status_events) >= 1
        assert (
            status_events[0]["data"]["status"]
            == NodeStatus.CANCELED
        )

        run_events = [
            e for e in events
            if e["type"] == "run_status_changed"
        ]
        assert len(run_events) == 1
        assert (
            run_events[0]["data"]["status"]
            == RunStatus.CANCELED
        )

        engine.unsubscribe(run_id, queue)


class TestCancelNode:
    @pytest.mark.asyncio
    async def test_cancel_single_node(
        self,
        engine: OrchestratorEngine,
        db: Database,
    ) -> None:
        pid = db.list_repositories()[0].id
        config = make_config()
        run_id = await engine.create_run(
            pid, "test", "obj", config, {"prompt": "x"},
        )
        await engine.start_run(run_id)

        root = db.list_run_nodes(run_id)[0]
        await engine.cancel_node(run_id, root.id)

        node = db.get_run_node(root.id)
        assert node is not None
        assert node.status == NodeStatus.CANCELED

    @pytest.mark.asyncio
    async def test_cancel_queued_node(
        self,
        engine: OrchestratorEngine,
        db: Database,
    ) -> None:
        pid = db.list_repositories()[0].id
        config = make_config()
        run_id = await engine.create_run(
            pid, "test", "obj", config, {"prompt": "x"},
        )

        root = db.list_run_nodes(run_id)[0]
        assert root.status == NodeStatus.QUEUED

        await engine.cancel_node(run_id, root.id)

        node = db.get_run_node(root.id)
        assert node is not None
        assert node.status == NodeStatus.CANCELED

    @pytest.mark.asyncio
    async def test_cancel_terminal_node_noop(
        self,
        engine: OrchestratorEngine,
        db: Database,
    ) -> None:
        pid = db.list_repositories()[0].id
        config = make_config()
        run_id = await engine.create_run(
            pid, "test", "obj", config, {"prompt": "x"},
        )

        root = db.list_run_nodes(run_id)[0]
        db.update_node_status(root.id, NodeStatus.SUCCEEDED)

        await engine.cancel_node(run_id, root.id)

        node = db.get_run_node(root.id)
        assert node is not None
        assert node.status == NodeStatus.SUCCEEDED
