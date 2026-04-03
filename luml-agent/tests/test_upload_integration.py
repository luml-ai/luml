import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from luml_agent.database import Database
from luml_agent.handlers.run import RunHandler
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
from luml_agent.services.orchestrator.nodes.result_file import (
    ARTIFACT_FILENAME,
    RESULT_DIR,
)
from luml_agent.services.orchestrator.registry import NodeRegistry
from luml_agent.services.pty_manager import PtyManager
from luml_agent.services.upload_queue import UploadQueue, UploadStatus


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
def upload_queue(tmp_path: Path) -> UploadQueue:
    return UploadQueue(tmp_path / "uploads.db")


@pytest.fixture
def worktree_with_artifact(tmp_path: Path) -> Path:
    wt = tmp_path / "worktree"
    agent_dir = wt / RESULT_DIR
    agent_dir.mkdir(parents=True)
    artifact = agent_dir / ARTIFACT_FILENAME
    artifact.write_bytes(b"model-data")
    return wt


@pytest.fixture
def model_file(worktree_with_artifact: Path) -> Path:
    return worktree_with_artifact / RESULT_DIR / ARTIFACT_FILENAME


@pytest.fixture
def engine(
    db: Database, pty: PtyManager, registry: NodeRegistry,
    upload_queue: UploadQueue,
) -> OrchestratorEngine:
    return OrchestratorEngine(
        db=db, pty=pty, registry=registry, upload_queue=upload_queue,
    )


@pytest.fixture
def run_handler(
    db: Database, engine: OrchestratorEngine, upload_queue: UploadQueue,
) -> RunHandler:
    return RunHandler(
        run_repo=db.runs,
        node_repo=db.nodes,
        repository_repo=db.repositories,
        engine=engine,
        upload_queue=upload_queue,
    )


class TestUploadEnqueueOnSuccessfulRun:
    @pytest.mark.asyncio
    async def test_enqueues_upload_with_collection_id(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
        upload_queue: UploadQueue,
        worktree_with_artifact: Path,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler("implement"))
        registry.register(MockNodeHandler("fork"))
        registry.register(MockNodeHandler(
            "run",
            NodeResult(
                success=True,
                artifacts={
                    "experiment_ids": ["exp-1", "exp-2"],
                    "metrics": {"accuracy": 0.92},
                    "metric": 0.92,
                },
            ),
        ))

        config = RunConfig(
            run_command_template="echo test",
            luml_collection_id="col-1",
            luml_organization_id="org-1",
            luml_orbit_id="orb-1",
        )
        run_id = await engine.create_run(
            pid, "test", "objective", config, {"prompt": "test"},
        )
        nodes = db.list_run_nodes(run_id)
        db.update_node_worktree(
            nodes[0].id, str(worktree_with_artifact), "test-branch",
        )

        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        pending = upload_queue.get_pending(run_id)
        assert len(pending) == 1
        assert pending[0].run_id == run_id
        assert pending[0].experiment_ids == ["exp-1", "exp-2"]
        expected_path = str(
            worktree_with_artifact / RESULT_DIR / ARTIFACT_FILENAME,
        )
        assert pending[0].model_path == expected_path

    @pytest.mark.asyncio
    async def test_emits_upload_ready_event(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
        worktree_with_artifact: Path,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler("implement"))
        registry.register(MockNodeHandler("fork"))
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

        config = RunConfig(
            run_command_template="echo test",
            luml_collection_id="col-1",
            luml_organization_id="org-1",
            luml_orbit_id="orb-1",
        )
        run_id = await engine.create_run(
            pid, "test", "obj", config, {"prompt": "test"},
        )
        nodes = db.list_run_nodes(run_id)
        db.update_node_worktree(
            nodes[0].id, str(worktree_with_artifact), "br",
        )

        queue = engine.subscribe(run_id)

        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        upload_events = [e for e in events if e["type"] == "upload_ready"]
        assert len(upload_events) == 1
        data = upload_events[0]["data"]
        assert data["collection_id"] == "col-1"
        assert data["organization_id"] == "org-1"
        assert data["orbit_id"] == "orb-1"
        assert data["experiment_ids"] == ["exp-1"]
        assert "upload_id" in data

        engine.unsubscribe(run_id, queue)


class TestNoUploadWithoutRequiredFields:
    @pytest.mark.asyncio
    async def test_no_enqueue_without_collection_id(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
        upload_queue: UploadQueue,
        worktree_with_artifact: Path,
    ) -> None:
        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler("implement"))
        registry.register(MockNodeHandler("fork"))
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
            pid, "test", "obj", config, {"prompt": "test"},
        )
        nodes = db.list_run_nodes(run_id)
        db.update_node_worktree(
            nodes[0].id, str(worktree_with_artifact), "br",
        )

        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        pending = upload_queue.get_pending(run_id)
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_no_enqueue_without_artifact_file(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
        upload_queue: UploadQueue,
        tmp_path: Path,
    ) -> None:
        wt = tmp_path / "empty-worktree"
        wt.mkdir()

        pid = db.list_repositories()[0].id
        registry.register(MockNodeHandler("implement"))
        registry.register(MockNodeHandler("fork"))
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

        config = RunConfig(
            run_command_template="echo test",
            luml_collection_id="col-1",
        )
        run_id = await engine.create_run(
            pid, "test", "obj", config, {"prompt": "test"},
        )
        nodes = db.list_run_nodes(run_id)
        db.update_node_worktree(nodes[0].id, str(wt), "br")

        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        pending = upload_queue.get_pending(run_id)
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_no_enqueue_without_experiment_ids(
        self,
        engine: OrchestratorEngine,
        db: Database,
        registry: NodeRegistry,
        upload_queue: UploadQueue,
        worktree_with_artifact: Path,
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
                    "metrics": {"accuracy": 0.9},
                    "metric": 0.9,
                },
            ),
        ))

        config = RunConfig(
            run_command_template="echo test",
            luml_collection_id="col-1",
        )
        run_id = await engine.create_run(
            pid, "test", "obj", config, {"prompt": "test"},
        )
        nodes = db.list_run_nodes(run_id)
        db.update_node_worktree(
            nodes[0].id, str(worktree_with_artifact), "br",
        )

        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        pending = upload_queue.get_pending(run_id)
        assert len(pending) == 0


class TestWorktreeDeferral:
    @pytest.mark.asyncio
    async def test_worktree_deferred_for_pending_upload(
        self,
        run_handler: RunHandler,
        db: Database,
        upload_queue: UploadQueue,
        model_file: Path,
        engine: OrchestratorEngine,
    ) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "test", "obj")
        node = db.add_run_node(
            run.id, None, NodeType.IMPLEMENT, 0,
            worktree_path="/tmp/wt-1", branch="branch-1",
        )
        db.update_node_status(node.id, NodeStatus.SUCCEEDED)

        upload_queue.enqueue(
            run.id, node.id, str(model_file), ["exp-1"],
        )

        queue = engine.subscribe(run.id)

        with patch(
            "luml_agent.handlers.run.remove_worktree",
            new_callable=AsyncMock,
        ) as mock_remove:
            await run_handler._cleanup_run_worktrees(run.id)
            mock_remove.assert_not_called()

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())
        pending_events = [e for e in events if e["type"] == "worktrees_pending_upload"]
        assert len(pending_events) == 1
        assert node.id in pending_events[0]["data"]["deferred_node_ids"]

        engine.unsubscribe(run.id, queue)

    @pytest.mark.asyncio
    async def test_worktree_cleaned_when_no_pending_uploads(
        self,
        run_handler: RunHandler,
        db: Database,
        upload_queue: UploadQueue,
    ) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "test", "obj")
        db.add_run_node(
            run.id, None, NodeType.IMPLEMENT, 0,
            worktree_path="/tmp/wt-1", branch="branch-1",
        )

        with patch(
            "luml_agent.handlers.run.remove_worktree",
            new_callable=AsyncMock,
        ) as mock_remove:
            await run_handler._cleanup_run_worktrees(run.id)
            mock_remove.assert_called_once()

    @pytest.mark.asyncio
    async def test_deferred_cleanup_triggers_after_upload_completion(
        self,
        run_handler: RunHandler,
        db: Database,
        upload_queue: UploadQueue,
        model_file: Path,
    ) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "test", "obj")
        node = db.add_run_node(
            run.id, None, NodeType.IMPLEMENT, 0,
            worktree_path="/tmp/wt-1", branch="branch-1",
        )

        upload = upload_queue.enqueue(
            run.id, node.id, str(model_file), ["exp-1"],
        )
        upload_queue.claim(upload.id)
        upload_queue.complete(upload.id)

        with patch(
            "luml_agent.handlers.run.remove_worktree",
            new_callable=AsyncMock,
        ) as mock_remove:
            await run_handler.try_deferred_worktree_cleanup(run.id)
            mock_remove.assert_called_once()

    @pytest.mark.asyncio
    async def test_deferred_cleanup_does_not_trigger_with_active_uploads(
        self,
        run_handler: RunHandler,
        db: Database,
        upload_queue: UploadQueue,
        model_file: Path,
    ) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "test", "obj")
        node = db.add_run_node(
            run.id, None, NodeType.IMPLEMENT, 0,
            worktree_path="/tmp/wt-1", branch="branch-1",
        )

        upload_queue.enqueue(
            run.id, node.id, str(model_file), ["exp-1"],
        )

        with patch(
            "luml_agent.handlers.run.remove_worktree",
            new_callable=AsyncMock,
        ) as mock_remove:
            await run_handler.try_deferred_worktree_cleanup(run.id)
            mock_remove.assert_not_called()


class TestDeletionCancelsUploads:
    @pytest.mark.asyncio
    async def test_delete_cancels_pending_uploads(
        self,
        run_handler: RunHandler,
        db: Database,
        upload_queue: UploadQueue,
        model_file: Path,
    ) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "test", "obj")
        db.update_run_status(run.id, RunStatus.SUCCEEDED)
        node = db.add_run_node(
            run.id, None, NodeType.IMPLEMENT, 0,
            worktree_path="/tmp/wt-1", branch="branch-1",
        )

        upload = upload_queue.enqueue(
            run.id, node.id, str(model_file), ["exp-1"],
        )

        with patch(
            "luml_agent.handlers.run.remove_worktree",
            new_callable=AsyncMock,
        ):
            await run_handler.delete(run.id)

        fetched = upload_queue.get(upload.id)
        assert fetched is not None
        assert fetched.status == UploadStatus.FAILED
        assert fetched.error == "run cancelled"

    @pytest.mark.asyncio
    async def test_cancel_cancels_pending_uploads(
        self,
        run_handler: RunHandler,
        db: Database,
        upload_queue: UploadQueue,
        model_file: Path,
        engine: OrchestratorEngine,
    ) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "test", "obj")
        db.update_run_status(run.id, RunStatus.RUNNING)
        node = db.add_run_node(
            run.id, None, NodeType.IMPLEMENT, 0,
            worktree_path="/tmp/wt-1", branch="branch-1",
        )
        db.update_node_status(node.id, NodeStatus.SUCCEEDED)

        upload = upload_queue.enqueue(
            run.id, node.id, str(model_file), ["exp-1"],
        )

        with patch(
            "luml_agent.handlers.run.remove_worktree",
            new_callable=AsyncMock,
        ):
            await run_handler.cancel(run.id)

        fetched = upload_queue.get(upload.id)
        assert fetched is not None
        assert fetched.status == UploadStatus.FAILED

    @pytest.mark.asyncio
    async def test_delete_force_cleans_worktrees(
        self,
        run_handler: RunHandler,
        db: Database,
        upload_queue: UploadQueue,
        model_file: Path,
    ) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "test", "obj")
        db.update_run_status(run.id, RunStatus.SUCCEEDED)
        node = db.add_run_node(
            run.id, None, NodeType.IMPLEMENT, 0,
            worktree_path="/tmp/wt-1", branch="branch-1",
        )

        upload_queue.enqueue(
            run.id, node.id, str(model_file), ["exp-1"],
        )

        with patch(
            "luml_agent.handlers.run.remove_worktree",
            new_callable=AsyncMock,
        ) as mock_remove:
            await run_handler.delete(run.id)
            mock_remove.assert_called_once()


class TestUploadQueueGetActiveForNodes:
    def test_returns_pending_and_in_progress(
        self, upload_queue: UploadQueue, model_file: Path,
    ) -> None:
        upload_queue.enqueue("r1", "n1", str(model_file), ["e1"])
        u2 = upload_queue.enqueue("r1", "n2", str(model_file), ["e2"])
        upload_queue.claim(u2.id)

        active = upload_queue.get_active_for_nodes(["n1", "n2", "n3"])
        assert len(active) == 2
        ids = {u.node_id for u in active}
        assert ids == {"n1", "n2"}

    def test_excludes_completed_and_failed(
        self, upload_queue: UploadQueue, model_file: Path,
    ) -> None:
        u1 = upload_queue.enqueue("r1", "n1", str(model_file), ["e1"])
        u2 = upload_queue.enqueue("r1", "n2", str(model_file), ["e2"])
        upload_queue.claim(u1.id)
        upload_queue.complete(u1.id)
        upload_queue.claim(u2.id)
        upload_queue.fail(u2.id, "error")
        upload_queue.fail(u2.id, "error")
        upload_queue.fail(u2.id, "error")

        active = upload_queue.get_active_for_nodes(["n1", "n2"])
        assert len(active) == 0

    def test_empty_node_ids_returns_empty(
        self, upload_queue: UploadQueue,
    ) -> None:
        assert upload_queue.get_active_for_nodes([]) == []


class TestRunConfigCollectionFields:
    def test_default_values_are_none(self) -> None:
        config = RunConfig()
        assert config.luml_collection_id is None
        assert config.luml_organization_id is None
        assert config.luml_orbit_id is None

    def test_custom_values(self) -> None:
        config = RunConfig(
            luml_collection_id="col-1",
            luml_organization_id="org-1",
            luml_orbit_id="orb-1",
        )
        assert config.luml_collection_id == "col-1"
        assert config.luml_organization_id == "org-1"
        assert config.luml_orbit_id == "orb-1"

    def test_serialization_roundtrip(self) -> None:
        config = RunConfig(
            luml_collection_id="col-1",
            luml_organization_id="org-1",
            luml_orbit_id="orb-1",
        )
        serialized = json.dumps(config.__dict__)
        data = json.loads(serialized)
        restored = RunConfig(**{
            k: v for k, v in data.items()
            if k in RunConfig.__dataclass_fields__
        })
        assert restored.luml_collection_id == "col-1"
        assert restored.luml_organization_id == "org-1"
        assert restored.luml_orbit_id == "orb-1"


class TestEngineWithoutUploadQueue:
    @pytest.mark.asyncio
    async def test_no_error_when_no_upload_queue(
        self,
        db: Database,
        pty: PtyManager,
        registry: NodeRegistry,
        worktree_with_artifact: Path,
    ) -> None:
        engine = OrchestratorEngine(db=db, pty=pty, registry=registry)
        registry.register(MockNodeHandler("implement"))
        registry.register(MockNodeHandler("fork"))
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

        pid = db.list_repositories()[0].id
        config = RunConfig(
            run_command_template="echo test",
            luml_collection_id="col-1",
        )
        run_id = await engine.create_run(
            pid, "test", "obj", config, {"prompt": "test"},
        )
        nodes = db.list_run_nodes(run_id)
        db.update_node_worktree(
            nodes[0].id, str(worktree_with_artifact), "br",
        )

        await engine.start_run(run_id)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)
        await engine._schedule_tick()
        await asyncio.sleep(0.05)

        nodes = db.list_run_nodes(run_id)
        fork_nodes = [n for n in nodes if n.node_type == NodeType.FORK]
        assert len(fork_nodes) == 1
