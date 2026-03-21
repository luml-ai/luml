import asyncio
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

        await exit_event.wait()

        exit_code = ctx.services.engine.get_session_exit_code(session.session_id)
        scrollback = ctx.services.engine.get_session_scrollback(session.session_id)
        logs = scrollback.decode("utf-8", errors="replace")

        stdout_metric = parse_stdout_metric(logs)

        result_data = read_result_file(worktree_path)
        if result_data is not None:
            success = result_data["success"]
            metrics = result_data.get("metrics", {})
            error_message = result_data.get("error_message", "")
        else:
            success = exit_code == 0
            metrics = self._parse_metrics(logs, ctx.payload.get("metrics_pattern"))
            error_message = ""

        artifacts: dict[str, Any] = {
            "exit_code": exit_code or 0,
            "logs": logs[-10000:] if len(logs) > 10000 else logs,
            "metrics": metrics,
            "session_id": session.session_id,
        }
        if stdout_metric is not None:
            artifacts["metric"] = stdout_metric
        if result_data and "artifacts" in result_data:
            artifacts.update(result_data["artifacts"])

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
