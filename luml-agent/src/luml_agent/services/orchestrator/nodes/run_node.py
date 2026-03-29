import asyncio
import logging
import re
from typing import Any

from luml_agent.services.orchestrator.nodes.base import (
    NodeExecutionContext,
    NodeResult,
    NodeSpawnSpec,
)
from luml_agent.services.orchestrator.nodes.result_file import (
    parse_stdout_metric,
    read_result_file,
)
from luml_agent.services.orchestrator.utils import ensure_luml_agent_dir

logger = logging.getLogger(__name__)


class RunNodeHandler:
    def type_id(self) -> str:
        return "run"

    def validate_payload(self, payload: dict[str, Any]) -> None:
        pass

    async def execute(self, ctx: NodeExecutionContext) -> NodeResult:
        command_str = ctx.payload.get("command", "")
        if not command_str:
            command_str = ctx.run_config.get("run_command_template", "")
        if not command_str:
            return NodeResult(
                success=False,
                error_message="No command specified for Run node",
            )

        worktree_path = ctx.parent_worktree_path or ""
        if not worktree_path:
            return NodeResult(success=False, error_message="No worktree path available")

        ensure_luml_agent_dir(worktree_path)

        command = ["bash", "-c", command_str]

        session = ctx.services.pty.spawn(
            task_id=ctx.node_id,
            command=command,
            cwd=worktree_path,
            session_type="run",
        )

        ctx.services.db.add_node_session(ctx.node_id, session.session_id)
        ctx.services.db.update_node_worktree(
            ctx.node_id, worktree_path, ctx.parent_branch or "",
        )

        exit_event = asyncio.Event()
        ctx.services.engine.register_session_completion(session.session_id, exit_event)

        timeout = ctx.run_config.get("run_timeout", 0)
        try:
            await asyncio.wait_for(
                exit_event.wait(),
                timeout=timeout if timeout > 0 else None,
            )
        except TimeoutError:
            logger.warning(
                "Run node %s timed out after %ds", ctx.node_id, timeout,
            )
            ctx.services.pty.terminate(session.session_id)
            return NodeResult(
                success=False,
                artifacts={"session_id": session.session_id},
                error_message=f"Node execution timed out after {timeout}s",
            )

        exit_code = ctx.services.engine.get_session_exit_code(session.session_id)
        scrollback = ctx.services.engine.get_session_scrollback(session.session_id)
        logs = scrollback.decode("utf-8", errors="replace")

        result_data = read_result_file(worktree_path)
        stdout_metric = parse_stdout_metric(logs)

        if result_data is not None:
            success = result_data.success
            metrics = result_data.metrics
            error_message = result_data.error_message or ""
            experiment_ids = result_data.experiment_ids
            model_path = result_data.model_path
        else:
            success = exit_code == 0
            metrics = self._parse_metrics(logs, ctx.payload.get("metrics_pattern"))
            error_message = ""
            experiment_ids = []
            model_path = None

        if not metrics and stdout_metric is not None:
            metrics = {"metric": float(stdout_metric)}

        artifacts: dict[str, Any] = {
            "exit_code": exit_code or 0,
            "logs": logs[-10000:] if len(logs) > 10000 else logs,
            "metrics": metrics,
            "experiment_ids": experiment_ids,
            "session_id": session.session_id,
        }
        if stdout_metric is not None:
            artifacts["metric"] = stdout_metric
        elif metrics:
            first_value = next(iter(metrics.values()))
            artifacts["metric"] = first_value
        if model_path is not None:
            artifacts["model_path"] = model_path

        return NodeResult(
            success=success,
            artifacts=artifacts,
            error_message=error_message,
        )

    def _parse_metrics(self, logs: str, pattern: str | None) -> dict[str, Any]:
        if not pattern:
            return {}
        try:
            matches = re.findall(pattern, logs)
            if matches:
                return {"raw_matches": matches}
        except re.error:
            pass
        return {}

    def can_fork(self, result: NodeResult) -> bool:
        return False

    def default_next_nodes(self, result: NodeResult) -> list[NodeSpawnSpec]:
        return []
