import asyncio
import json
from typing import Any

import pytest

from luml_agent.database import Database
from luml_agent.services.orchestrator.engine import OrchestratorEngine
from luml_agent.services.orchestrator.models import (
    NodeStatus,
    NodeType,
    RunConfig,
    RunStatus,
)
from luml_agent.services.orchestrator.nodes.base import (
    NodeExecutionContext,
    NodeResult,
    NodeSpawnSpec,
)
from luml_agent.services.orchestrator.registry import NodeRegistry
from luml_agent.services.pty_manager import PtyManager


class MockNodeHandler:
    def __init__(
        self,
        type_name: str = "implement",
        result: NodeResult | None = None,
        delay: float = 0,
    ) -> None:
        self._type = type_name
        self._result = result or NodeResult(success=True)
        self._delay = delay
        self.execute_count = 0

    def type_id(self) -> str:
        return self._type

    def validate_payload(
        self,
        payload: dict[str, Any],  # noqa: ANN401
    ) -> None:
        pass

    async def execute(
        self, ctx: NodeExecutionContext,
    ) -> NodeResult:
        self.execute_count += 1
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        return self._result

    def can_fork(self, result: NodeResult) -> bool:
        return False

    def default_next_nodes(
        self, result: NodeResult,
    ) -> list[NodeSpawnSpec]:
        return []


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
def registry() -> NodeRegistry:
    return NodeRegistry()


@pytest.fixture
def engine(
    db: Database,
    pty: PtyManager,
    registry: NodeRegistry,
) -> OrchestratorEngine:
    return OrchestratorEngine(
        db=db, pty=pty, registry=registry,
    )


class TestCreateRun:
    @pytest.mark.asyncio
    async def test_create_run(
        self,
        engine: OrchestratorEngine,
        db: Database,
    ) -> None:
        pid = db.list_repositories()[0].id
        config = RunConfig(agent_id="claude")
        run_id = await engine.create_run(
            repository_id=pid,
            name="test-run",
            objective="do stuff",
            config=config,
            root_payload={"prompt": "hello"},
        )
        assert run_id is not None

        run = db.get_run(run_id)
        assert run is not None
        assert run.name == "test-run"
        assert run.status == RunStatus.PENDING

        nodes = db.list_run_nodes(run_id)
        assert len(nodes) == 1
        assert nodes[0].node_type == NodeType.IMPLEMENT
        assert nodes[0].status == NodeStatus.QUEUED

    @pytest.mark.asyncio
    async def test_create_run_emits_events(
        self,
        engine: OrchestratorEngine,
        db: Database,
    ) -> None:
        pid = db.list_repositories()[0].id
        config = RunConfig()
        run_id = await engine.create_run(
            repository_id=pid,
            name="r",
            objective="",
            config=config,
            root_payload={"prompt": "test"},
        )
        events = db.list_run_events(run_id)
        event_types = [e.event_type for e in events]
        assert "run_created" in event_types
        assert "node_created" in event_types


class TestScheduling:
    @pytest.mark.asyncio
    async def test_scheduler_picks_queued_node(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        handler = MockNodeHandler("implement")
        registry.register(handler)

        config = RunConfig()
        run_id = await engine.create_run(
            pid, "r", "", config, {"prompt": "test"},
        )
        await engine.start_run(run_id)

        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        assert handler.execute_count == 1
        nodes = db.list_run_nodes(run_id)
        assert nodes[0].status == NodeStatus.SUCCEEDED

    @pytest.mark.asyncio
    async def test_bfs_ordering(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        handler = MockNodeHandler("implement")
        registry.register(handler)
        registry.register(MockNodeHandler("run"))

        config = RunConfig(max_concurrency=1)
        run_id = await engine.create_run(
            pid, "r", "", config, {"prompt": "test"},
        )

        nodes = db.list_run_nodes(run_id)
        root = nodes[0]
        db.add_run_node(
            run_id, root.id, NodeType.RUN, depth=1,
        )
        db.add_run_node(
            run_id, root.id, NodeType.IMPLEMENT, depth=2,
        )

        await engine.start_run(run_id)

        candidates = engine._get_next_candidates(
            run_id, 3,
        )
        assert candidates[0].depth == 0
        assert candidates[1].depth == 1
        assert candidates[2].depth == 2

    @pytest.mark.asyncio
    async def test_concurrency_limit(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        handler = MockNodeHandler(
            "implement", delay=0.5,
        )
        registry.register(handler)

        config = RunConfig(max_concurrency=1)
        run_id = await engine.create_run(
            pid, "r", "", config, {"prompt": "test"},
        )

        nodes = db.list_run_nodes(run_id)
        root = nodes[0]
        db.add_run_node(
            run_id, root.id, NodeType.IMPLEMENT,
            depth=1, payload_json='{"prompt": "b"}',
        )

        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        active = engine._count_active_nodes(run_id)
        assert active <= 1


class TestAutoSpawn:
    @pytest.mark.asyncio
    async def test_auto_spawn_run_after_implement(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler(
            "implement",
            NodeResult(
                success=True,
                artifacts={
                    "worktree_path": "/tmp/wt",
                    "branch": "test",
                },
            ),
        ))
        registry.register(MockNodeHandler("run"))

        config = RunConfig(
            run_command_template="echo test",
        )
        run_id = await engine.create_run(
            pid, "r", "", config, {"prompt": "test"},
        )

        nodes = db.list_run_nodes(run_id)
        root = nodes[0]
        db.update_node_worktree(
            root.id, "/tmp/wt", "test",
        )

        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        nodes = db.list_run_nodes(run_id)
        assert len(nodes) == 2
        assert nodes[1].node_type == NodeType.RUN
        assert nodes[1].status == NodeStatus.QUEUED

    @pytest.mark.asyncio
    async def test_default_config_spawns_run_node(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler(
            "implement",
            NodeResult(
                success=True,
                artifacts={
                    "worktree_path": "/tmp/wt",
                    "branch": "test",
                },
            ),
        ))
        registry.register(MockNodeHandler("run"))

        config = RunConfig()
        run_id = await engine.create_run(
            pid, "r", "", config, {"prompt": "test"},
        )

        nodes = db.list_run_nodes(run_id)
        root = nodes[0]
        db.update_node_worktree(
            root.id, "/tmp/wt", "test",
        )

        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        nodes = db.list_run_nodes(run_id)
        assert len(nodes) == 2
        assert nodes[1].node_type == NodeType.RUN
        payload = json.loads(nodes[1].payload_json)
        assert payload["command"] == "uv run main.py"

    @pytest.mark.asyncio
    async def test_no_auto_spawn_without_run_command(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler(
            "implement", NodeResult(success=True),
        ))

        config = RunConfig(run_command_template="")
        run_id = await engine.create_run(
            pid, "r", "", config, {"prompt": "test"},
        )
        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        nodes = db.list_run_nodes(run_id)
        assert len(nodes) == 1

    @pytest.mark.asyncio
    async def test_auto_spawn_debug_on_run_failure(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler(
            "implement", NodeResult(success=True),
        ))
        registry.register(MockNodeHandler(
            "run",
            NodeResult(
                success=False,
                artifacts={
                    "exit_code": 1, "logs": "error",
                },
            ),
        ))
        registry.register(MockNodeHandler("debug"))

        config = RunConfig(
            run_command_template="fail",
            max_debug_retries=2,
        )
        run_id = await engine.create_run(
            pid, "r", "objective", config,
            {"prompt": "test"},
        )

        nodes = db.list_run_nodes(run_id)
        root = nodes[0]
        db.update_node_worktree(
            root.id, "/tmp/wt", "test",
        )

        await engine.start_run(run_id)

        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        nodes = db.list_run_nodes(run_id)
        node_types = [n.node_type for n in nodes]
        assert NodeType.DEBUG in node_types

    @pytest.mark.asyncio
    async def test_no_debug_when_budget_exhausted(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler(
            "implement", NodeResult(success=True),
        ))
        registry.register(MockNodeHandler(
            "run",
            NodeResult(
                success=False,
                artifacts={
                    "exit_code": 1, "logs": "error",
                },
            ),
        ))

        config = RunConfig(
            run_command_template="fail",
            max_debug_retries=0,
        )
        run_id = await engine.create_run(
            pid, "r", "", config, {"prompt": "test"},
        )

        nodes = db.list_run_nodes(run_id)
        root = nodes[0]
        db.update_node_worktree(
            root.id, "/tmp/wt", "test",
        )

        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        nodes = db.list_run_nodes(run_id)
        node_types = [n.node_type for n in nodes]
        assert NodeType.DEBUG not in node_types

    @pytest.mark.asyncio
    async def test_auto_spawn_fork_after_successful_run(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler(
            "implement", NodeResult(success=True),
        ))
        registry.register(MockNodeHandler(
            "run",
            NodeResult(
                success=True,
                artifacts={
                    "exit_code": 0, "logs": "ok",
                },
            ),
        ))
        registry.register(MockNodeHandler("fork"))

        config = RunConfig(
            run_command_template="echo ok",
            max_depth=5,
        )
        run_id = await engine.create_run(
            pid, "r", "build feature", config,
            {"prompt": "test"},
        )

        nodes = db.list_run_nodes(run_id)
        root = nodes[0]
        db.update_node_worktree(
            root.id, "/tmp/wt", "test",
        )

        await engine.start_run(run_id)

        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        nodes = db.list_run_nodes(run_id)
        node_types = [n.node_type for n in nodes]
        assert NodeType.FORK in node_types

        fork_node = next(
            n for n in nodes
            if n.node_type == NodeType.FORK
        )
        payload = json.loads(fork_node.payload_json)
        assert payload["objective"] == "build feature"

    @pytest.mark.asyncio
    async def test_fork_spawn_next_creates_implement_children(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler(
            "implement", NodeResult(success=True),
        ))
        registry.register(MockNodeHandler(
            "run",
            NodeResult(
                success=True,
                artifacts={
                    "exit_code": 0, "logs": "ok",
                },
            ),
        ))
        fork_result = NodeResult(
            success=True,
            artifacts={
                "proposals": [
                    {"prompt": "do A"},
                    {"prompt": "do B"},
                ],
            },
            spawn_next=[
                NodeSpawnSpec(
                    node_type="implement",
                    payload={"prompt": "do A"},
                    reason="fork",
                ),
                NodeSpawnSpec(
                    node_type="implement",
                    payload={"prompt": "do B"},
                    reason="fork",
                ),
            ],
        )
        registry.register(
            MockNodeHandler("fork", fork_result),
        )

        config = RunConfig(
            run_command_template="echo ok",
            max_depth=5,
        )
        run_id = await engine.create_run(
            pid, "r", "build feature", config,
            {"prompt": "test"},
        )

        nodes = db.list_run_nodes(run_id)
        root = nodes[0]
        db.update_node_worktree(
            root.id, "/tmp/wt", "test",
        )

        await engine.start_run(run_id)

        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        nodes = db.list_run_nodes(run_id)
        fork_children = [
            n for n in nodes
            if (
                n.node_type == NodeType.IMPLEMENT
                and n.parent_node_id is not None
                and any(
                    p.node_type == NodeType.FORK
                    for p in nodes
                    if p.id == n.parent_node_id
                )
            )
        ]
        assert len(fork_children) == 2
        payloads = [
            json.loads(n.payload_json)
            for n in fork_children
        ]
        prompts = sorted(p["prompt"] for p in payloads)
        assert prompts == ["do A", "do B"]

    @pytest.mark.asyncio
    async def test_no_fork_when_at_max_depth(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler(
            "implement", NodeResult(success=True),
        ))
        registry.register(MockNodeHandler(
            "run",
            NodeResult(
                success=True,
                artifacts={
                    "exit_code": 0, "logs": "ok",
                },
            ),
        ))

        config = RunConfig(
            run_command_template="echo ok",
            max_depth=1,
        )
        run_id = await engine.create_run(
            pid, "r", "obj", config, {"prompt": "test"},
        )

        nodes = db.list_run_nodes(run_id)
        root = nodes[0]
        db.update_node_worktree(
            root.id, "/tmp/wt", "test",
        )

        await engine.start_run(run_id)

        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        nodes = db.list_run_nodes(run_id)
        node_types = [n.node_type for n in nodes]
        assert NodeType.FORK not in node_types


class TestRunCompletion:
    @pytest.mark.asyncio
    async def test_run_completes_on_success(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler(
            "implement", NodeResult(success=True),
        ))

        config = RunConfig(run_command_template="")
        run_id = await engine.create_run(
            pid, "r", "", config, {"prompt": "test"},
        )
        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        run = db.get_run(run_id)
        assert run is not None
        assert run.status == RunStatus.SUCCEEDED

    @pytest.mark.asyncio
    async def test_run_fails_when_all_failed(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler(
            "implement",
            NodeResult(
                success=False, error_message="oops",
            ),
        ))

        config = RunConfig(run_command_template="")
        run_id = await engine.create_run(
            pid, "r", "", config, {"prompt": "test"},
        )
        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        run = db.get_run(run_id)
        assert run is not None
        assert run.status == RunStatus.FAILED


class TestBestNodeSelection:
    @pytest.mark.asyncio
    async def test_best_node_set_to_highest_metric(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler(
            "implement", NodeResult(success=True),
        ))

        config = RunConfig(run_command_template="")
        run_id = await engine.create_run(
            pid, "r", "", config, {"prompt": "test"},
        )
        await engine.start_run(run_id)

        nodes = db.list_run_nodes(run_id)
        root = nodes[0]
        db.update_node_status(root.id, NodeStatus.SUCCEEDED)
        db.update_node_result(root.id, json.dumps({"success": True}))

        impl_a = db.add_run_node(
            run_id, root.id, NodeType.IMPLEMENT, depth=2,
        )
        db.update_node_status(impl_a.id, NodeStatus.SUCCEEDED)
        db.update_node_result(impl_a.id, json.dumps({"success": True}))

        run_a = db.add_run_node(
            run_id, impl_a.id, NodeType.RUN, depth=3,
        )
        db.update_node_status(run_a.id, NodeStatus.SUCCEEDED)
        db.update_node_result(run_a.id, json.dumps({
            "success": True,
            "artifacts": {"metric": 0.75},
        }))

        impl_b = db.add_run_node(
            run_id, root.id, NodeType.IMPLEMENT, depth=2,
        )
        db.update_node_status(impl_b.id, NodeStatus.SUCCEEDED)
        db.update_node_result(impl_b.id, json.dumps({"success": True}))

        run_b = db.add_run_node(
            run_id, impl_b.id, NodeType.RUN, depth=3,
        )
        db.update_node_status(run_b.id, NodeStatus.SUCCEEDED)
        db.update_node_result(run_b.id, json.dumps({
            "success": True,
            "artifacts": {"metric": 0.95},
        }))

        await engine._check_run_completion(run_id)

        run = db.get_run(run_id)
        assert run is not None
        assert run.best_node_id == run_b.id
        assert run.status == RunStatus.SUCCEEDED

    @pytest.mark.asyncio
    async def test_best_node_none_when_no_metrics(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler(
            "implement", NodeResult(success=True),
        ))

        config = RunConfig(run_command_template="")
        run_id = await engine.create_run(
            pid, "r", "", config, {"prompt": "test"},
        )
        await engine.start_run(run_id)

        nodes = db.list_run_nodes(run_id)
        root = nodes[0]
        db.update_node_status(root.id, NodeStatus.SUCCEEDED)
        db.update_node_result(root.id, json.dumps({"success": True}))

        run_node = db.add_run_node(
            run_id, root.id, NodeType.RUN, depth=1,
        )
        db.update_node_status(run_node.id, NodeStatus.SUCCEEDED)
        db.update_node_result(run_node.id, json.dumps({
            "success": True,
            "artifacts": {},
        }))

        await engine._check_run_completion(run_id)

        run = db.get_run(run_id)
        assert run is not None
        assert run.best_node_id is None
        assert run.status == RunStatus.SUCCEEDED

    @pytest.mark.asyncio
    async def test_best_node_in_completion_event(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler(
            "implement", NodeResult(success=True),
        ))

        config = RunConfig(run_command_template="")
        run_id = await engine.create_run(
            pid, "r", "", config, {"prompt": "test"},
        )
        await engine.start_run(run_id)

        queue = engine.subscribe(run_id)

        nodes = db.list_run_nodes(run_id)
        root = nodes[0]
        db.update_node_status(root.id, NodeStatus.SUCCEEDED)
        db.update_node_result(root.id, json.dumps({"success": True}))

        impl = db.add_run_node(
            run_id, root.id, NodeType.IMPLEMENT, depth=2,
        )
        db.update_node_status(impl.id, NodeStatus.SUCCEEDED)
        db.update_node_result(impl.id, json.dumps({"success": True}))

        run_node = db.add_run_node(
            run_id, impl.id, NodeType.RUN, depth=3,
        )
        db.update_node_status(run_node.id, NodeStatus.SUCCEEDED)
        db.update_node_result(run_node.id, json.dumps({
            "success": True,
            "artifacts": {"metric": 0.88},
        }))

        await engine._check_run_completion(run_id)

        events: list[dict[str, object]] = []
        while not queue.empty():
            events.append(queue.get_nowait())

        status_events = [
            e for e in events if e["type"] == "run_status_changed"
        ]
        assert len(status_events) == 1
        assert status_events[0]["data"]["best_node_id"] == run_node.id


class TestEventSubscription:
    @pytest.mark.asyncio
    async def test_subscribe_receives_events(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler(
            "implement", NodeResult(success=True),
        ))

        config = RunConfig()
        run_id = await engine.create_run(
            pid, "r", "", config, {"prompt": "test"},
        )

        queue = engine.subscribe(run_id)

        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        events: list[dict[str, object]] = []
        while not queue.empty():
            events.append(queue.get_nowait())

        event_types = [e["type"] for e in events]
        assert "run_status_changed" in event_types
        assert "node_status_changed" in event_types
        assert "node_completed" in event_types

    @pytest.mark.asyncio
    async def test_unsubscribe(
        self, engine: OrchestratorEngine,
    ) -> None:
        queue = engine.subscribe("dummy-run-id")
        engine.unsubscribe("dummy-run-id", queue)
        engine.unsubscribe("dummy-run-id", queue)


class TestSessionCompletion:
    @pytest.mark.asyncio
    async def test_notify_session_exit(
        self, engine: OrchestratorEngine,
    ) -> None:
        event = asyncio.Event()
        engine.register_session_completion(
            "test-session", event,
        )
        assert not event.is_set()

        engine.notify_session_exit("test-session")
        assert event.is_set()

    @pytest.mark.asyncio
    async def test_notify_session_started_emits_event(
        self,
        engine: OrchestratorEngine,
        db: Database,
    ) -> None:
        pid = db.list_repositories()[0].id
        config = RunConfig()
        run_id = await engine.create_run(
            pid, "r", "", config, {"prompt": "test"},
        )
        nodes = db.list_run_nodes(run_id)
        node = nodes[0]

        engine.notify_session_started(
            node.id, "sess-abc",
        )

        events = db.list_run_events(run_id)
        session_events = [
            e for e in events
            if e.event_type == "node_session_started"
        ]
        assert len(session_events) == 1
        data = json.loads(session_events[0].data_json)
        assert data["session_id"] == "sess-abc"
        assert session_events[0].node_id == node.id

    @pytest.mark.asyncio
    async def test_notify_session_started_ignores_unknown_node(
        self,
        engine: OrchestratorEngine,
        db: Database,
    ) -> None:
        engine.notify_session_started("nonexistent", "sess-xyz")

    @pytest.mark.asyncio
    async def test_notify_unknown_session(
        self, engine: OrchestratorEngine,
    ) -> None:
        engine.notify_session_exit("nonexistent")


class TestWaitingInputStatus:
    @pytest.mark.asyncio
    async def test_idle_sets_waiting_input(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        handler = MockNodeHandler(
            "implement", delay=10,
        )
        registry.register(handler)

        config = RunConfig()
        run_id = await engine.create_run(
            pid, "r", "", config, {"prompt": "test"},
        )
        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        nodes = db.list_run_nodes(run_id)
        node = nodes[0]
        assert node.status == NodeStatus.RUNNING

        session_id = "fake-session-idle"
        db.add_node_session(node.id, session_id)

        engine.notify_session_idle(session_id)

        updated = db.get_run_node(node.id)
        assert updated is not None
        assert (
            updated.status == NodeStatus.WAITING_INPUT
        )
        assert node.id in engine._waiting_input_nodes

        await engine.cancel_run(run_id)

    @pytest.mark.asyncio
    async def test_active_resets_to_running(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        handler = MockNodeHandler(
            "implement", delay=10,
        )
        registry.register(handler)

        config = RunConfig()
        run_id = await engine.create_run(
            pid, "r", "", config, {"prompt": "test"},
        )
        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        nodes = db.list_run_nodes(run_id)
        node = nodes[0]
        session_id = "fake-session-active"
        db.add_node_session(node.id, session_id)

        engine.notify_session_idle(session_id)
        assert (
            db.get_run_node(node.id).status
            == NodeStatus.WAITING_INPUT
        )

        engine.notify_session_active(session_id)
        assert (
            db.get_run_node(node.id).status
            == NodeStatus.RUNNING
        )
        assert node.id not in engine._waiting_input_nodes

        await engine.cancel_run(run_id)

    @pytest.mark.asyncio
    async def test_ignores_non_running_nodes(
        self,
        engine: OrchestratorEngine,
        db: Database,
    ) -> None:
        pid = db.list_repositories()[0].id
        config = RunConfig()
        run_id = await engine.create_run(
            pid, "r", "", config, {"prompt": "test"},
        )

        nodes = db.list_run_nodes(run_id)
        node = nodes[0]
        assert node.status == NodeStatus.QUEUED

        session_id = "fake-session-queued"
        db.add_node_session(node.id, session_id)

        engine.notify_session_idle(session_id)
        assert (
            db.get_run_node(node.id).status
            == NodeStatus.QUEUED
        )

    @pytest.mark.asyncio
    async def test_count_active_includes_waiting_input(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        handler = MockNodeHandler(
            "implement", delay=10,
        )
        registry.register(handler)

        config = RunConfig()
        run_id = await engine.create_run(
            pid, "r", "", config, {"prompt": "test"},
        )
        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        assert engine._count_active_nodes(run_id) == 1

        nodes = db.list_run_nodes(run_id)
        session_id = "fake-session-count"
        db.add_node_session(nodes[0].id, session_id)
        engine.notify_session_idle(session_id)

        assert engine._count_active_nodes(run_id) == 1

        await engine.cancel_run(run_id)

    @pytest.mark.asyncio
    async def test_cancel_clears_waiting_input(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        handler = MockNodeHandler(
            "implement", delay=10,
        )
        registry.register(handler)

        config = RunConfig()
        run_id = await engine.create_run(
            pid, "r", "", config, {"prompt": "test"},
        )
        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        nodes = db.list_run_nodes(run_id)
        session_id = "fake-session-cancel"
        db.add_node_session(nodes[0].id, session_id)
        engine.notify_session_idle(session_id)
        assert (
            nodes[0].id in engine._waiting_input_nodes
        )

        await engine.cancel_run(run_id)
        assert (
            nodes[0].id
            not in engine._waiting_input_nodes
        )


class MockPtyManager:
    def __init__(
        self, idle_duration: float | None = None,
    ) -> None:
        self._idle_duration = idle_duration
        self.terminated: list[str] = []
        self._scrollback: dict[str, bytes] = {}

    def get_idle_duration(
        self, session_id: str,
    ) -> float | None:
        return self._idle_duration

    def get_scrollback(
        self, session_id: str,
    ) -> bytes:
        return self._scrollback.get(session_id, b"")

    def terminate(self, session_id: str) -> None:
        self.terminated.append(session_id)

    def set_scrollback(
        self, session_id: str, data: bytes,
    ) -> None:
        self._scrollback[session_id] = data


class TestAutoTerminate:
    def test_config_defaults(self) -> None:
        config = RunConfig()
        assert config.auto_mode is False
        assert config.auto_terminate_timeout == 30

    def test_config_custom_values(self) -> None:
        config = RunConfig(
            auto_mode=True, auto_terminate_timeout=60,
        )
        assert config.auto_mode is True
        assert config.auto_terminate_timeout == 60

    @pytest.mark.asyncio
    async def test_auto_terminate_calls_notify_session_exit(
        self,
        engine: OrchestratorEngine,
        db: Database,
    ) -> None:
        pid = db.list_repositories()[0].id
        config = RunConfig(
            auto_mode=True, auto_terminate_timeout=10,
        )
        run_id = await engine.create_run(
            pid, "r", "obj", config, {"prompt": "test"},
        )
        await engine.start_run(run_id)

        nodes = db.list_run_nodes(run_id)
        node = nodes[0]
        db.update_node_status(
            node.id, NodeStatus.RUNNING,
        )

        session_id = "auto-term-session"
        db.add_node_session(node.id, session_id)

        exit_event = asyncio.Event()
        engine.register_session_completion(
            session_id, exit_event,
        )

        mock_pty = MockPtyManager(idle_duration=15.0)
        mock_pty.set_scrollback(
            session_id, b"some output",
        )

        engine.maybe_auto_terminate(
            session_id,
            mock_pty,  # type: ignore[arg-type]
        )

        assert session_id in mock_pty.terminated
        assert exit_event.is_set()
        assert (
            engine.get_session_exit_code(session_id) == 0
        )
        assert (
            engine.get_session_scrollback(session_id)
            == b"some output"
        )

    @pytest.mark.asyncio
    async def test_auto_terminate_skips_non_auto_mode(
        self,
        engine: OrchestratorEngine,
        db: Database,
    ) -> None:
        pid = db.list_repositories()[0].id
        config = RunConfig(auto_mode=False)
        run_id = await engine.create_run(
            pid, "r", "obj", config, {"prompt": "test"},
        )
        await engine.start_run(run_id)

        nodes = db.list_run_nodes(run_id)
        node = nodes[0]
        db.update_node_status(
            node.id, NodeStatus.RUNNING,
        )

        session_id = "no-auto-session"
        db.add_node_session(node.id, session_id)

        exit_event = asyncio.Event()
        engine.register_session_completion(
            session_id, exit_event,
        )

        mock_pty = MockPtyManager(idle_duration=999.0)
        engine.maybe_auto_terminate(
            session_id,
            mock_pty,  # type: ignore[arg-type]
        )

        assert not mock_pty.terminated
        assert not exit_event.is_set()


class TestCancelRun:
    @pytest.mark.asyncio
    async def test_cancel_run(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(
            MockNodeHandler("implement", delay=10),
        )

        config = RunConfig()
        run_id = await engine.create_run(
            pid, "r", "", config, {"prompt": "test"},
        )
        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        await engine.cancel_run(run_id)

        run = db.get_run(run_id)
        assert run is not None
        assert run.status == RunStatus.CANCELED

        nodes = db.list_run_nodes(run_id)
        for node in nodes:
            assert node.status == NodeStatus.CANCELED
