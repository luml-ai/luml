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
    ) -> None:
        self._type = type_name
        self._result = result or NodeResult(success=True)
        self.last_ctx: NodeExecutionContext | None = None

    def type_id(self) -> str:
        return self._type

    def validate_payload(self, payload: dict[str, Any]) -> None:
        pass

    async def execute(self, ctx: NodeExecutionContext) -> NodeResult:
        self.last_ctx = ctx
        return self._result

    def can_fork(self, result: NodeResult) -> bool:
        return False

    def default_next_nodes(self, result: NodeResult) -> list[NodeSpawnSpec]:
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
def engine(db: Database, pty: PtyManager, registry: NodeRegistry) -> OrchestratorEngine:
    return OrchestratorEngine(db=db, pty=pty, registry=registry)


class TestForkPayloadContainsExperimentIds:
    @pytest.mark.asyncio
    async def test_fork_payload_includes_experiment_ids(
        self, engine: OrchestratorEngine, db: Database, registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler("implement"))
        fork_handler = MockNodeHandler("fork")
        registry.register(fork_handler)
        run_handler = MockNodeHandler(
            "run",
            NodeResult(
                success=True,
                artifacts={
                    "experiment_ids": ["exp-1", "exp-2"],
                    "metrics": {"accuracy": 0.92, "loss": 0.08},
                    "metric": 0.92,
                },
            ),
        )
        registry.register(run_handler)

        config = RunConfig(run_command_template="echo test")
        run_id = await engine.create_run(
            pid, "test", "objective", config, {"prompt": "test"},
        )

        nodes = db.list_run_nodes(run_id)
        root = nodes[0]
        db.update_node_worktree(root.id, "/tmp/wt", "test-branch")

        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        nodes = db.list_run_nodes(run_id)
        fork_node = next(
            (n for n in nodes if n.node_type == NodeType.FORK), None,
        )
        assert fork_node is not None
        payload = json.loads(fork_node.payload_json)
        assert payload["experiment_ids"] == ["exp-1", "exp-2"]
        assert payload["discovered_metric_keys"] == ["accuracy", "loss"]
        assert payload["objective"] == "objective"

    @pytest.mark.asyncio
    async def test_fork_payload_empty_when_no_experiments(
        self, engine: OrchestratorEngine, db: Database, registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler("implement"))
        registry.register(MockNodeHandler("fork"))
        registry.register(MockNodeHandler(
            "run",
            NodeResult(
                success=True,
                artifacts={"metric": 0.5},
            ),
        ))

        config = RunConfig(run_command_template="echo test")
        run_id = await engine.create_run(
            pid, "test", "obj", config, {"prompt": "test"},
        )
        nodes = db.list_run_nodes(run_id)
        db.update_node_worktree(nodes[0].id, "/tmp/wt", "br")

        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        nodes = db.list_run_nodes(run_id)
        fork_node = next(
            (n for n in nodes if n.node_type == NodeType.FORK), None,
        )
        assert fork_node is not None
        payload = json.loads(fork_node.payload_json)
        assert payload["experiment_ids"] == []
        assert payload["discovered_metric_keys"] == []


class TestChildPayloadContainsParentData:
    @pytest.mark.asyncio
    async def test_fork_copies_data_to_child_payloads(
        self, engine: OrchestratorEngine, db: Database, registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler("implement"))
        registry.register(MockNodeHandler(
            "fork",
            NodeResult(
                success=True,
                artifacts={"proposals": [{"prompt": "try A"}]},
                spawn_next=[
                    NodeSpawnSpec(
                        node_type="implement",
                        payload={
                            "prompt": "try A",
                            "objective": "original obj",
                            "experiment_ids": ["exp-1"],
                            "discovered_metric_keys": ["accuracy"],
                        },
                        reason="fork",
                    ),
                ],
            ),
        ))
        registry.register(MockNodeHandler(
            "run",
            NodeResult(
                success=True,
                artifacts={
                    "experiment_ids": ["exp-1"],
                    "metrics": {"accuracy": 0.9},
                    "metric": 0.9,
                },
            ),
        ))

        config = RunConfig(run_command_template="echo test")
        run_id = await engine.create_run(
            pid, "test", "original obj", config, {"prompt": "test"},
        )
        nodes = db.list_run_nodes(run_id)
        db.update_node_worktree(nodes[0].id, "/tmp/wt", "br")

        await engine.start_run(run_id)

        for _ in range(6):
            await engine._schedule_tick()
            await asyncio.sleep(0.05)

        nodes = db.list_run_nodes(run_id)
        impl_nodes = [n for n in nodes if n.node_type == NodeType.IMPLEMENT]
        child_impls = [n for n in impl_nodes if n.parent_node_id is not None]

        if child_impls:
            child = child_impls[0]
            payload = json.loads(child.payload_json)
            assert payload["prompt"] == "try A"
            assert payload["objective"] == "original obj"
            assert payload["experiment_ids"] == ["exp-1"]
            assert payload["discovered_metric_keys"] == ["accuracy"]


class TestComputeBestNodeWithMetricDirection:
    def _make_run_node(
        self, db: Database, run_id: str, parent_id: str,
        metrics: dict[str, float] | None = None,
        metric: float | None = None,
    ) -> str:
        node = db.add_run_node(
            run_id, parent_id, NodeType.RUN, depth=0,
        )
        db.update_node_status(node.id, NodeStatus.SUCCEEDED)
        artifacts: dict[str, Any] = {}
        if metrics is not None:
            artifacts["metrics"] = metrics
        if metric is not None:
            artifacts["metric"] = metric
        db.update_node_result(
            node.id,
            json.dumps({"success": True, "artifacts": artifacts}),
        )
        return node.id

    def test_max_direction_selects_highest(
        self, db: Database, engine: OrchestratorEngine,
    ) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "test", "obj")
        root = db.add_run_node(run.id, None, NodeType.IMPLEMENT, 0)

        self._make_run_node(
            db, run.id, root.id, metrics={"f1_score": 0.85},
        )
        expected = self._make_run_node(
            db, run.id, root.id, metrics={"f1_score": 0.88},
        )

        config = RunConfig(primary_metric="f1_score", metric_direction="max")
        nodes = db.list_run_nodes(run.id)
        best = engine._compute_best_node(nodes, config)
        assert best == expected

    def test_min_direction_selects_lowest(
        self, db: Database, engine: OrchestratorEngine,
    ) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "test", "obj")
        root = db.add_run_node(run.id, None, NodeType.IMPLEMENT, 0)

        self._make_run_node(
            db, run.id, root.id, metrics={"loss": 0.3},
        )
        expected = self._make_run_node(
            db, run.id, root.id, metrics={"loss": 0.1},
        )

        config = RunConfig(primary_metric="loss", metric_direction="min")
        nodes = db.list_run_nodes(run.id)
        best = engine._compute_best_node(nodes, config)
        assert best == expected

    def test_fallback_to_metric_field(
        self, db: Database, engine: OrchestratorEngine,
    ) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "test", "obj")
        root = db.add_run_node(run.id, None, NodeType.IMPLEMENT, 0)

        self._make_run_node(
            db, run.id, root.id, metric=0.7,
        )
        expected = self._make_run_node(
            db, run.id, root.id, metric=0.9,
        )

        config = RunConfig(primary_metric="f1_score", metric_direction="max")
        nodes = db.list_run_nodes(run.id)
        best = engine._compute_best_node(nodes, config)
        assert best == expected

    def test_metrics_dict_takes_priority_over_metric_field(
        self, db: Database, engine: OrchestratorEngine,
    ) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "test", "obj")
        root = db.add_run_node(run.id, None, NodeType.IMPLEMENT, 0)

        expected = self._make_run_node(
            db, run.id, root.id,
            metrics={"accuracy": 0.95}, metric=0.5,
        )
        self._make_run_node(
            db, run.id, root.id,
            metrics={"accuracy": 0.80}, metric=0.9,
        )

        config = RunConfig(primary_metric="accuracy", metric_direction="max")
        nodes = db.list_run_nodes(run.id)
        best = engine._compute_best_node(nodes, config)
        assert best == expected

    def test_default_config_uses_metric_key_max(
        self, db: Database, engine: OrchestratorEngine,
    ) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "test", "obj")
        root = db.add_run_node(run.id, None, NodeType.IMPLEMENT, 0)

        self._make_run_node(
            db, run.id, root.id, metric=0.6,
        )
        expected = self._make_run_node(
            db, run.id, root.id, metric=0.8,
        )

        config = RunConfig()
        nodes = db.list_run_nodes(run.id)
        best = engine._compute_best_node(nodes, config)
        assert best == expected

    def test_no_run_nodes_returns_none(
        self, db: Database, engine: OrchestratorEngine,
    ) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "test", "obj")
        db.add_run_node(run.id, None, NodeType.IMPLEMENT, 0)

        config = RunConfig()
        nodes = db.list_run_nodes(run.id)
        assert engine._compute_best_node(nodes, config) is None

    def test_no_metrics_returns_none(
        self, db: Database, engine: OrchestratorEngine,
    ) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "test", "obj")
        root = db.add_run_node(run.id, None, NodeType.IMPLEMENT, 0)
        node = db.add_run_node(run.id, root.id, NodeType.RUN, 0)
        db.update_node_status(node.id, NodeStatus.SUCCEEDED)
        db.update_node_result(
            node.id,
            json.dumps({"success": True, "artifacts": {}}),
        )

        config = RunConfig()
        nodes = db.list_run_nodes(run.id)
        assert engine._compute_best_node(nodes, config) is None

    def test_skips_failed_nodes(
        self, db: Database, engine: OrchestratorEngine,
    ) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "test", "obj")
        root = db.add_run_node(run.id, None, NodeType.IMPLEMENT, 0)

        good_id = self._make_run_node(
            db, run.id, root.id, metric=0.5,
        )
        bad_node = db.add_run_node(run.id, root.id, NodeType.RUN, 0)
        db.update_node_status(bad_node.id, NodeStatus.FAILED)
        db.update_node_result(
            bad_node.id,
            json.dumps({"success": False, "artifacts": {"metric": 0.99}}),
        )

        config = RunConfig()
        nodes = db.list_run_nodes(run.id)
        best = engine._compute_best_node(nodes, config)
        assert best == good_id


class TestDiscoveredMetricKeys:
    @pytest.mark.asyncio
    async def test_first_success_sets_discovered_keys(
        self, engine: OrchestratorEngine, db: Database, registry: NodeRegistry,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler("implement"))
        registry.register(MockNodeHandler("fork"))
        registry.register(MockNodeHandler(
            "run",
            NodeResult(
                success=True,
                artifacts={
                    "experiment_ids": [],
                    "metrics": {"accuracy": 0.92, "loss": 0.08},
                    "metric": 0.92,
                },
            ),
        ))

        config = RunConfig(run_command_template="echo test")
        run_id = await engine.create_run(
            pid, "test", "obj", config, {"prompt": "test"},
        )
        nodes = db.list_run_nodes(run_id)
        db.update_node_worktree(nodes[0].id, "/tmp/wt", "br")

        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        run = db.get_run(run_id)
        assert run is not None
        keys = json.loads(run.discovered_metric_keys_json)
        assert sorted(keys) == ["accuracy", "loss"]

    @pytest.mark.asyncio
    async def test_subsequent_success_does_not_overwrite(
        self, db: Database, engine: OrchestratorEngine,
    ) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "test", "obj")

        db.update_run_discovered_metric_keys(
            run.id, json.dumps(["accuracy", "loss"]),
        )

        engine._record_discovered_metric_keys(run.id, ["new_metric"])

        run = db.get_run(run.id)
        assert run is not None
        keys = json.loads(run.discovered_metric_keys_json)
        assert keys == ["accuracy", "loss"]

    def test_empty_keys_not_recorded(
        self, db: Database, engine: OrchestratorEngine,
    ) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "test", "obj")

        engine._record_discovered_metric_keys(run.id, [])

        run = db.get_run(run.id)
        assert run is not None
        keys = json.loads(run.discovered_metric_keys_json)
        assert keys == []


class TestRunConfigNewFields:
    def test_default_values(self) -> None:
        config = RunConfig()
        assert config.primary_metric == "metric"
        assert config.metric_direction == "max"

    def test_custom_values(self) -> None:
        config = RunConfig(primary_metric="f1_score", metric_direction="min")
        assert config.primary_metric == "f1_score"
        assert config.metric_direction == "min"

    def test_config_serialization_roundtrip(self) -> None:
        config = RunConfig(primary_metric="loss", metric_direction="min")
        serialized = json.dumps(config.__dict__)
        data = json.loads(serialized)
        restored = RunConfig(**{
            k: v for k, v in data.items()
            if k in RunConfig.__dataclass_fields__
        })
        assert restored.primary_metric == "loss"
        assert restored.metric_direction == "min"
