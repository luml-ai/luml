import json
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
from luml_agent.services.orchestrator.registry import register_all_handlers
from luml_agent.services.pty_manager import PtyManager


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


def make_config() -> RunConfig:
    return RunConfig(
        max_depth=3,
        max_children_per_fork=3,
        max_debug_retries=2,
        max_concurrency=2,
        run_command_template="",
        agent_id="echo",
        fork_auto_approve=True,
    )


def _add_run(
    db: Database, repository_id: str, config: RunConfig, status: str,
) -> object:
    config_json = json.dumps(config.__dict__)
    return db.add_run(
        repository_id, "test", "obj", config_json, status,
    )


def _add_node(
    db: Database,
    run_id: str,
    parent_id: str | None,
    node_type: str,
    depth: int,
    payload: dict[str, str],
) -> object:
    return db.add_run_node(
        run_id, parent_id, node_type, depth,
        json.dumps(payload),
    )


class TestRecovery:
    @pytest.mark.asyncio
    async def test_recover_orphaned_running_node(
        self, db: Database, pty: PtyManager,
    ) -> None:
        config = make_config()
        pid = db.list_repositories()[0].id
        run = _add_run(db, pid, config, RunStatus.RUNNING)
        node = _add_node(
            db, run.id, None,
            NodeType.IMPLEMENT, 0, {"prompt": "x"},
        )
        db.update_node_status(node.id, NodeStatus.RUNNING)

        registry = register_all_handlers()
        engine = OrchestratorEngine(
            db=db, pty=pty, registry=registry,
        )
        await engine.start()

        recovered_node = db.get_run_node(node.id)
        assert recovered_node is not None
        assert recovered_node.status == NodeStatus.FAILED

        recovered_run = db.get_run(run.id)
        assert recovered_run is not None
        assert recovered_run.status == RunStatus.FAILED

        await engine.stop()

    @pytest.mark.asyncio
    async def test_recover_orphaned_waiting_node(
        self, db: Database, pty: PtyManager,
    ) -> None:
        config = make_config()
        pid = db.list_repositories()[0].id
        run = _add_run(db, pid, config, RunStatus.RUNNING)
        node = _add_node(
            db, run.id, None,
            NodeType.IMPLEMENT, 0, {"prompt": "x"},
        )
        db.update_node_status(
            node.id, NodeStatus.WAITING_INPUT,
        )

        registry = register_all_handlers()
        engine = OrchestratorEngine(
            db=db, pty=pty, registry=registry,
        )
        await engine.start()

        recovered_node = db.get_run_node(node.id)
        assert recovered_node is not None
        assert recovered_node.status == NodeStatus.FAILED

        await engine.stop()

    @pytest.mark.asyncio
    async def test_recover_mixed_nodes(
        self, db: Database, pty: PtyManager,
    ) -> None:
        config = make_config()
        pid = db.list_repositories()[0].id
        run = _add_run(db, pid, config, RunStatus.RUNNING)

        node1 = _add_node(
            db, run.id, None,
            NodeType.IMPLEMENT, 0, {"prompt": "x"},
        )
        db.update_node_status(
            node1.id, NodeStatus.SUCCEEDED,
        )

        node2 = _add_node(
            db, run.id, node1.id,
            NodeType.RUN, 1, {"command": "test"},
        )
        db.update_node_status(node2.id, NodeStatus.RUNNING)

        registry = register_all_handlers()
        engine = OrchestratorEngine(
            db=db, pty=pty, registry=registry,
        )
        await engine.start()

        n1 = db.get_run_node(node1.id)
        assert n1 is not None
        assert n1.status == NodeStatus.SUCCEEDED

        n2 = db.get_run_node(node2.id)
        assert n2 is not None
        assert n2.status == NodeStatus.FAILED

        recovered_run = db.get_run(run.id)
        assert recovered_run is not None
        assert recovered_run.status == RunStatus.SUCCEEDED

        await engine.stop()

    @pytest.mark.asyncio
    async def test_no_recovery_for_pending_run(
        self, db: Database, pty: PtyManager,
    ) -> None:
        config = make_config()
        pid = db.list_repositories()[0].id
        run = _add_run(db, pid, config, RunStatus.PENDING)
        node = _add_node(
            db, run.id, None,
            NodeType.IMPLEMENT, 0, {"prompt": "x"},
        )

        registry = register_all_handlers()
        engine = OrchestratorEngine(
            db=db, pty=pty, registry=registry,
        )
        await engine.start()

        n = db.get_run_node(node.id)
        assert n is not None
        assert n.status == NodeStatus.QUEUED

        r = db.get_run(run.id)
        assert r is not None
        assert r.status == RunStatus.PENDING

        await engine.stop()

    @pytest.mark.asyncio
    async def test_recovery_emits_events(
        self, db: Database, pty: PtyManager,
    ) -> None:
        config = make_config()
        pid = db.list_repositories()[0].id
        run = _add_run(db, pid, config, RunStatus.RUNNING)
        node = _add_node(
            db, run.id, None,
            NodeType.IMPLEMENT, 0, {"prompt": "x"},
        )
        db.update_node_status(node.id, NodeStatus.RUNNING)

        registry = register_all_handlers()
        engine = OrchestratorEngine(
            db=db, pty=pty, registry=registry,
        )
        await engine.start()

        events = db.list_run_events(run.id)
        event_types = [e.event_type for e in events]
        assert "node_status_changed" in event_types
        assert "run_status_changed" in event_types

        await engine.stop()
