import asyncio
import contextlib
import json
import logging
from typing import Any

from luml_agent.database import Database
from luml_agent.models import RunNodeOrm
from luml_agent.services.orchestrator.models import (
    NodeStatus,
    NodeType,
    RunConfig,
    RunStatus,
)
from luml_agent.services.orchestrator.nodes.base import (
    NodeExecutionContext,
    NodeResult,
    NodeServices,
)
from luml_agent.services.orchestrator.registry import NodeRegistry
from luml_agent.services.pty_manager import PtyManager

logger = logging.getLogger("luml_agent.orchestrator")

_TERMINAL_STATUSES = {NodeStatus.SUCCEEDED, NodeStatus.FAILED, NodeStatus.CANCELED}


class OrchestratorEngine:
    def __init__(
        self,
        db: Database,
        pty: PtyManager,
        registry: NodeRegistry,
    ) -> None:
        self._db = db
        self._pty = pty
        self._registry = registry
        self._running_nodes: dict[str, asyncio.Task[None]] = {}
        self._session_exit_events: dict[str, asyncio.Event] = {}
        self._session_exit_codes: dict[str, int | None] = {}
        self._session_scrollback: dict[str, bytes] = {}
        self._event_subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}
        self._scheduler_task: asyncio.Task[None] | None = None
        self._waiting_input_nodes: set[str] = set()

    async def start(self) -> None:
        self._recover_orphaned_runs()
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    def _recover_orphaned_runs(self) -> None:
        for run in self._db.list_runs():
            if run.status != RunStatus.RUNNING:
                continue
            nodes = self._db.list_run_nodes(run.id)
            recovered = False
            for node in nodes:
                if node.status in (NodeStatus.RUNNING, NodeStatus.WAITING_INPUT):
                    logger.warning(
                        "Recovery: marking orphaned node %s (run %s) as failed",
                        node.id, run.id,
                    )
                    self._db.update_node_status(node.id, NodeStatus.FAILED)
                    self._db.update_node_result(
                        node.id,
                        json.dumps({"error": "Orphaned after server restart"}),
                    )
                    self._emit_event(
                        run.id, node.id, "node_status_changed",
                        {"status": NodeStatus.FAILED},
                    )
                    recovered = True
            if recovered:
                all_terminal = all(
                    self._db.get_run_node(n.id).status in _TERMINAL_STATUSES  # type: ignore[union-attr]
                    for n in nodes
                )
                if all_terminal:
                    any_success = any(
                        self._db.get_run_node(n.id).status == NodeStatus.SUCCEEDED  # type: ignore[union-attr]
                        for n in nodes
                    )
                    new_status = (
                        RunStatus.SUCCEEDED if any_success
                        else RunStatus.FAILED
                    )
                    self._db.update_run_status(run.id, new_status)
                    self._emit_event(
                        run.id, None, "run_status_changed",
                        {"status": new_status},
                    )
                    logger.info("Recovery: run %s marked as %s", run.id, new_status)

    async def stop(self) -> None:
        if self._scheduler_task:
            self._scheduler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._scheduler_task
        for _node_id, task in list(self._running_nodes.items()):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._running_nodes.clear()

    async def create_run(
        self,
        repository_id: str,
        name: str,
        objective: str,
        config: RunConfig,
        root_payload: dict[str, Any],
        base_branch: str = "main",
    ) -> str:
        run = self._db.add_run(
            repository_id=repository_id,
            name=name,
            objective=objective,
            config_json=json.dumps(config.__dict__),
            status=RunStatus.PENDING,
            base_branch=base_branch,
        )
        root_node = self._db.add_run_node(
            run_id=run.id,
            parent_node_id=None,
            node_type=NodeType.IMPLEMENT,
            depth=0,
            payload_json=json.dumps(root_payload),
        )
        logger.info(
            "Created run %s (%s) for repo %s", run.id, name, repository_id,
        )
        self._emit_event(run.id, None, "run_created", {"run_id": run.id, "name": name})
        self._emit_event(run.id, root_node.id, "node_created", {
            "node_id": root_node.id, "node_type": NodeType.IMPLEMENT, "depth": 0,
        })
        return run.id

    async def start_run(self, run_id: str) -> None:
        logger.info("Starting run %s", run_id)
        self._db.update_run_status(run_id, RunStatus.RUNNING)
        self._emit_event(
            run_id, None, "run_status_changed",
            {"status": RunStatus.RUNNING},
        )

    async def restart_run(self, run_id: str) -> None:
        run = self._db.get_run(run_id)
        if not run:
            return
        logger.info("Restarting run %s", run_id)
        self._db.reset_run_data(run_id)
        self._db.update_run_status(run_id, RunStatus.PENDING)

        root_node = self._db.add_run_node(
            run_id=run_id,
            parent_node_id=None,
            node_type=NodeType.IMPLEMENT,
            depth=0,
            payload_json=json.dumps({"prompt": run.objective}),
        )
        self._emit_event(
            run_id, None, "run_status_changed",
            {"status": RunStatus.PENDING},
        )
        self._emit_event(run_id, root_node.id, "node_created", {
            "node_id": root_node.id, "node_type": NodeType.IMPLEMENT, "depth": 0,
        })

    async def cancel_run(self, run_id: str) -> None:
        logger.info("Canceling run %s", run_id)
        nodes = self._db.list_run_nodes(run_id)
        for node in nodes:
            if node.status in (NodeStatus.RUNNING, NodeStatus.WAITING_INPUT):
                await self._cancel_node(run_id, node)
            elif node.status == NodeStatus.QUEUED:
                self._db.update_node_status(node.id, NodeStatus.CANCELED)
                self._emit_event(
                    run_id, node.id, "node_status_changed",
                    {"status": NodeStatus.CANCELED},
                )
        self._db.update_run_status(run_id, RunStatus.CANCELED)
        self._emit_event(
            run_id, None, "run_status_changed",
            {"status": RunStatus.CANCELED},
        )

    async def cancel_node(self, run_id: str, node_id: str) -> None:
        node = self._db.get_run_node(node_id)
        if not node:
            return
        if node.status in (NodeStatus.RUNNING, NodeStatus.WAITING_INPUT):
            await self._cancel_node(run_id, node)
        elif node.status == NodeStatus.QUEUED:
            self._db.update_node_status(node.id, NodeStatus.CANCELED)
            self._emit_event(
                run_id, node.id, "node_status_changed",
                {"status": NodeStatus.CANCELED},
            )

    async def _cancel_node(self, run_id: str, node: RunNodeOrm) -> None:
        task = self._running_nodes.pop(node.id, None)
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        sessions = self._db.get_node_sessions(node.id)
        for sess in sessions:
            if self._pty.is_alive(sess.session_id):
                self._pty.terminate(sess.session_id)
        self._waiting_input_nodes.discard(node.id)
        self._db.update_node_status(node.id, NodeStatus.CANCELED)
        self._emit_event(
            run_id, node.id, "node_status_changed",
            {"status": NodeStatus.CANCELED},
        )

    def register_session_completion(
        self, session_id: str, event: asyncio.Event,
    ) -> None:
        self._session_exit_events[session_id] = event

    def notify_session_exit(
        self,
        session_id: str,
        exit_code: int | None = None,
        scrollback: bytes = b"",
    ) -> None:
        self._session_exit_codes[session_id] = exit_code
        self._session_scrollback[session_id] = scrollback
        event = self._session_exit_events.pop(session_id, None)
        if event is not None:
            event.set()

    def get_session_exit_code(self, session_id: str) -> int | None:
        return self._session_exit_codes.get(session_id)

    def get_session_scrollback(self, session_id: str) -> bytes:
        return self._session_scrollback.get(session_id, b"")

    def notify_session_started(self, node_id: str, session_id: str) -> None:
        node = self._db.get_run_node(node_id)
        if node is None:
            return
        self._emit_event(
            node.run_id, node_id, "node_session_started",
            {"session_id": session_id},
        )

    def notify_session_idle(self, session_id: str) -> None:
        node = self._db.get_node_by_session(session_id)
        if node is None or node.status != NodeStatus.RUNNING:
            return
        if node.id in self._waiting_input_nodes:
            return
        self._waiting_input_nodes.add(node.id)
        self._db.update_node_status(node.id, NodeStatus.WAITING_INPUT)
        self._emit_event(
            node.run_id, node.id, "node_status_changed",
            {"status": NodeStatus.WAITING_INPUT},
        )

    def notify_session_active(self, session_id: str) -> None:
        node = self._db.get_node_by_session(session_id)
        if node is None or node.id not in self._waiting_input_nodes:
            return
        self._waiting_input_nodes.discard(node.id)
        self._db.update_node_status(node.id, NodeStatus.RUNNING)
        self._emit_event(
            node.run_id, node.id, "node_status_changed",
            {"status": NodeStatus.RUNNING},
        )

    def maybe_auto_terminate(self, session_id: str, pty: PtyManager) -> None:
        node = self._db.get_node_by_session(session_id)
        if node is None:
            return
        run = self._db.get_run(node.run_id)
        if run is None:
            return
        config = self._load_config(run.config_json)
        if not config.auto_mode:
            return
        idle_duration = pty.get_idle_duration(session_id)
        if idle_duration is not None and idle_duration >= config.auto_terminate_timeout:
            logger.info(
                "Auto-terminating idle session %s (node %s, idle %.1fs)",
                session_id, node.id, idle_duration,
            )
            scrollback = pty.get_scrollback(session_id)
            pty.terminate(session_id)
            self.notify_session_exit(session_id, exit_code=0, scrollback=scrollback)

    def subscribe(self, run_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=512)
        self._event_subscribers.setdefault(run_id, []).append(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        subs = self._event_subscribers.get(run_id, [])
        with contextlib.suppress(ValueError):
            subs.remove(queue)

    async def _scheduler_loop(self) -> None:
        while True:
            await asyncio.sleep(0.5)
            try:
                await self._schedule_tick()
            except Exception:
                logger.exception("Scheduler tick failed")

    async def _schedule_tick(self) -> None:
        running_runs = [
            r for r in self._db.list_runs()
            if r.status == RunStatus.RUNNING
        ]
        for run in running_runs:
            config = self._load_config(run.config_json)
            active_count = self._count_active_nodes(run.id)
            if active_count >= config.max_concurrency:
                continue
            slots = config.max_concurrency - active_count
            candidates = self._get_next_candidates(run.id, slots)
            for node in candidates:
                self._execute_node(node, config, run.id)

    def _count_active_nodes(self, run_id: str) -> int:
        nodes = self._db.list_run_nodes(run_id)
        active = (NodeStatus.RUNNING, NodeStatus.WAITING_INPUT)
        return sum(1 for n in nodes if n.status in active)

    def _get_next_candidates(self, run_id: str, slots: int) -> list[RunNodeOrm]:
        nodes = self._db.list_run_nodes(run_id)
        queued = [n for n in nodes if n.status == NodeStatus.QUEUED]
        queued.sort(key=lambda n: (n.depth, n.created_at))
        return queued[:slots]

    def _execute_node(self, node: RunNodeOrm, config: RunConfig, run_id: str) -> None:
        task = asyncio.create_task(self._run_node(node, config, run_id))
        self._running_nodes[node.id] = task

    async def _run_node(self, node: RunNodeOrm, config: RunConfig, run_id: str) -> None:
        handler = self._registry.get(node.node_type)
        if handler is None:
            self._db.update_node_status(node.id, NodeStatus.FAILED)
            self._db.update_node_result(
                node.id,
                json.dumps({"error": f"Unknown node type: {node.node_type}"}),
            )
            self._emit_event(
                run_id, node.id, "node_status_changed",
                {"status": NodeStatus.FAILED},
            )
            self._running_nodes.pop(node.id, None)
            await self._check_run_completion(run_id)
            return

        logger.info(
            "Running node %s (type=%s, depth=%d) for run %s",
            node.id, node.node_type, node.depth, run_id,
        )
        self._db.update_node_status(node.id, NodeStatus.RUNNING)
        self._emit_event(
            run_id, node.id, "node_status_changed",
            {"status": NodeStatus.RUNNING},
        )

        ctx = self._build_context(node, config, run_id)
        try:
            result = await handler.execute(ctx)
        except asyncio.CancelledError:
            logger.info("Node %s canceled", node.id)
            raise
        except Exception as exc:
            logger.exception("Node %s execution failed", node.id)
            result = NodeResult(success=False, error_message=str(exc))

        if node.node_type in (NodeType.IMPLEMENT, NodeType.DEBUG):
            refreshed = self._db.get_run_node(node.id)
            if refreshed:
                node = refreshed

        self._waiting_input_nodes.discard(node.id)
        new_status = NodeStatus.SUCCEEDED if result.success else NodeStatus.FAILED
        logger.info("Node %s completed: %s", node.id, new_status)
        self._db.update_node_status(node.id, new_status)
        self._db.update_node_result(node.id, json.dumps({
            "success": result.success,
            "artifacts": result.artifacts,
            "error_message": result.error_message,
        }))
        self._emit_event(run_id, node.id, "node_completed", {
            "status": new_status,
            "success": result.success,
            "result": {
                "success": result.success,
                "artifacts": result.artifacts,
                "error_message": result.error_message,
            },
        })

        await self._process_result(node, result, config, run_id)
        self._running_nodes.pop(node.id, None)
        await self._check_run_completion(run_id)

    async def _process_result(
        self, node: RunNodeOrm, result: NodeResult, config: RunConfig, run_id: str,
    ) -> None:
        if result.success and node.node_type in (NodeType.IMPLEMENT, NodeType.DEBUG):
            if config.run_command_template:
                self._spawn_child(run_id, node, NodeType.RUN, {
                    "command": config.run_command_template,
                }, "auto")

        elif result.success and node.node_type == NodeType.RUN:
            self._spawn_child(run_id, node, NodeType.FORK, {
                "objective": self._get_run_objective(run_id),
                "context": json.dumps(result.artifacts) if result.artifacts else "",
            }, "auto", config=config)

        elif not result.success and node.node_type == NodeType.RUN:
            ancestor = self._get_implement_ancestor(node)
            if ancestor and ancestor.debug_retries < config.max_debug_retries:
                self._db.increment_node_debug_retries(ancestor.id)
                self._spawn_child(run_id, node, NodeType.DEBUG, {
                    "failure_context": result.artifacts,
                    "objective": self._get_run_objective(run_id),
                }, "debug")
            else:
                self._emit_event(run_id, node.id, "branch_failed", {
                    "reason": (
                        "debug_budget_exhausted"
                        if ancestor else "no_implement_ancestor"
                    ),
                })

        if result.spawn_next:
            logger.info(
                "Node %s returned %d spawn_next specs (depth=%d, max_depth=%d)",
                node.id, len(result.spawn_next), node.depth, config.max_depth,
            )
        for spec in result.spawn_next:
            self._spawn_child(
                run_id, node, spec.node_type,
                spec.payload, spec.reason,
                config=config,
            )

    def _spawn_child(
        self,
        run_id: str,
        parent_node: RunNodeOrm,
        child_type: str,
        payload: dict[str, Any],
        reason: str,
        config: RunConfig | None = None,
    ) -> RunNodeOrm | None:
        if child_type == NodeType.FORK:
            child_depth = parent_node.depth + 1
            if config and child_depth >= config.max_depth:
                logger.info(
                    "Skipping fork: depth %d >= max_depth %d",
                    child_depth, config.max_depth,
                )
                return None
        else:
            child_depth = parent_node.depth
        child = self._db.add_run_node(
            run_id=run_id,
            parent_node_id=parent_node.id,
            node_type=child_type,
            depth=child_depth,
            payload_json=json.dumps(payload),
            worktree_path=parent_node.worktree_path,
            branch=parent_node.branch,
        )
        self._db.add_run_edge(run_id, parent_node.id, child.id, reason)
        self._emit_event(run_id, child.id, "node_created", {
            "node_id": child.id,
            "node_type": child_type,
            "parent_node_id": parent_node.id,
            "depth": child.depth,
        })
        self._emit_event(run_id, None, "edge_created", {
            "from_node_id": parent_node.id,
            "to_node_id": child.id,
            "reason": reason,
        })
        return child

    def _build_context(
        self, node: RunNodeOrm, config: RunConfig, run_id: str,
    ) -> NodeExecutionContext:
        payload = json.loads(node.payload_json) if node.payload_json else {}
        parent_result = None
        parent_worktree_path = None
        parent_branch = None

        if node.parent_node_id is not None:
            parent = self._db.get_run_node(node.parent_node_id)
            if parent:
                parent_result = (
                    json.loads(parent.result_json)
                    if parent.result_json else None
                )
                parent_worktree_path = parent.worktree_path or None
                parent_branch = parent.branch or None

        run = self._db.get_run(run_id)
        repo = self._db.get_repository(run.repository_id) if run else None

        from luml_agent.config import load_config as load_app_config

        services = NodeServices(
            db=self._db,
            pty=self._pty,
            engine=self,
            config=load_app_config(),
        )

        return NodeExecutionContext(
            node_id=node.id,
            run_id=run_id,
            repository_path=repo.path if repo else "",
            base_branch=run.base_branch if run else "main",
            node_type=node.node_type,
            depth=node.depth,
            payload=payload,
            parent_result=parent_result,
            parent_worktree_path=parent_worktree_path or node.worktree_path or None,
            parent_branch=parent_branch or node.branch or None,
            run_config=config.__dict__,
            services=services,
        )

    def _get_implement_ancestor(self, node: RunNodeOrm) -> RunNodeOrm | None:
        current = node
        while current.parent_node_id is not None:
            parent = self._db.get_run_node(current.parent_node_id)
            if parent is None:
                return None
            if parent.node_type == NodeType.IMPLEMENT:
                return parent
            current = parent
        return None

    def _get_run_objective(self, run_id: str) -> str:
        run = self._db.get_run(run_id)
        return run.objective if run else ""

    def _load_config(self, config_json: str) -> RunConfig:
        try:
            data = json.loads(config_json)
        except (json.JSONDecodeError, TypeError):
            return RunConfig()
        fields = RunConfig.__dataclass_fields__
        return RunConfig(**{
            k: v for k, v in data.items() if k in fields
        })

    async def _check_run_completion(self, run_id: str) -> None:
        run = self._db.get_run(run_id)
        if not run or run.status != RunStatus.RUNNING:
            return
        nodes = self._db.list_run_nodes(run_id)
        if not nodes:
            return
        all_terminal = all(n.status in _TERMINAL_STATUSES for n in nodes)
        if all_terminal:
            any_success = any(n.status == NodeStatus.SUCCEEDED for n in nodes)
            new_status = RunStatus.SUCCEEDED if any_success else RunStatus.FAILED
            logger.info(
                "Run %s completed: %s (%d nodes)",
                run_id, new_status, len(nodes),
            )

            best_node_id = self._compute_best_node(nodes) if any_success else None
            if best_node_id:
                self._db.update_run_best_node(run_id, best_node_id)

            self._db.update_run_status(run_id, new_status)
            self._emit_event(
                run_id, None, "run_status_changed",
                {"status": new_status, "best_node_id": best_node_id},
            )

    def _compute_best_node(
        self, nodes: list[RunNodeOrm],
    ) -> str | None:
        best_metric: float | None = None
        best_run_id: str | None = None

        for node in nodes:
            if node.node_type != NodeType.RUN:
                continue
            if node.status != NodeStatus.SUCCEEDED:
                continue
            try:
                result = (
                    json.loads(node.result_json)
                    if node.result_json else {}
                )
            except (json.JSONDecodeError, TypeError):
                continue
            metric = result.get("artifacts", {}).get("metric")
            if not isinstance(metric, (int, float)):
                continue
            if best_metric is None or metric > best_metric:
                best_metric = metric
                best_run_id = node.id
        return best_run_id

    def _emit_event(
        self,
        run_id: str,
        node_id: str | None,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        event = self._db.add_run_event(run_id, node_id, event_type, json.dumps(data))
        msg = {"seq": event.seq, "type": event_type, "node_id": node_id, "data": data}
        for queue in self._event_subscribers.get(run_id, []):
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(msg)
