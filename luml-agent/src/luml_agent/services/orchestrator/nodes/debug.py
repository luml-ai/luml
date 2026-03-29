import asyncio
import logging
from typing import Any

from luml_agent.services.agents import build_agent_command, get_agent
from luml_agent.services.orchestrator.nodes.base import (
    NodeExecutionContext,
    NodeResult,
    NodeSpawnSpec,
)
from luml_agent.services.orchestrator.nodes.result_file import read_result_file
from luml_agent.services.orchestrator.utils import ensure_luml_agent_dir
from luml_agent.services.worktree import auto_commit_changes

logger = logging.getLogger(__name__)

_MAX_LOG_TAIL = 3000


class DebugNodeHandler:
    def type_id(self) -> str:
        return "debug"

    def validate_payload(self, payload: dict[str, Any]) -> None:
        pass

    async def execute(self, ctx: NodeExecutionContext) -> NodeResult:
        worktree_path = ctx.parent_worktree_path
        if not worktree_path:
            return NodeResult(success=False, error_message="No worktree path for debug")

        failure_context = ctx.payload.get("failure_context", {})
        objective = ctx.payload.get("objective", "")
        exit_code = failure_context.get("exit_code", "unknown")
        logs = failure_context.get("logs", "")
        log_tail = logs[-_MAX_LOG_TAIL:] if len(logs) > _MAX_LOG_TAIL else logs

        debug_prompt = (
            f"The previous run command failed with exit code {exit_code}.\n"
            f"Original objective: {objective}\n\n"
            f"Failure logs (last {_MAX_LOG_TAIL} chars):\n{log_tail}\n\n"
            f"Please analyze the failure and fix the code in this worktree."
        )

        ensure_luml_agent_dir(worktree_path)

        agent_id = ctx.run_config.get("agent_id", "claude")
        agent = get_agent(agent_id)
        if agent is None:
            return NodeResult(success=False, error_message=f"Unknown agent: {agent_id}")

        cmd_str = build_agent_command(agent, debug_prompt)
        command = ["bash", "-c", cmd_str]

        session = ctx.services.pty.spawn(
            task_id=ctx.node_id,
            command=command,
            cwd=worktree_path,
        )

        ctx.services.db.add_node_session(ctx.node_id, session.session_id)
        ctx.services.engine.notify_session_started(ctx.node_id, session.session_id)
        ctx.services.db.update_node_worktree(
            ctx.node_id, worktree_path, ctx.parent_branch or "",
        )

        exit_event = asyncio.Event()
        ctx.services.engine.register_session_completion(session.session_id, exit_event)

        timeout = ctx.run_config.get("debug_timeout", 1800)
        try:
            await asyncio.wait_for(
                exit_event.wait(),
                timeout=timeout if timeout > 0 else None,
            )
        except TimeoutError:
            logger.warning(
                "Debug node %s timed out after %ds", ctx.node_id, timeout,
            )
            ctx.services.pty.terminate(session.session_id)
            return NodeResult(
                success=False,
                artifacts={"session_id": session.session_id},
                error_message=f"Node execution timed out after {timeout}s",
            )

        result_exit_code = ctx.services.engine.get_session_exit_code(session.session_id)

        await auto_commit_changes(worktree_path)

        result_data = read_result_file(worktree_path)
        if result_data is not None:
            success = result_data["success"]
            error_message = result_data.get("error_message", "")
        else:
            success = result_exit_code == 0
            error_message = ""

        artifacts: dict[str, Any] = {
            "exit_code": result_exit_code or 0,
            "session_id": session.session_id,
            "worktree_path": worktree_path,
            "branch": ctx.parent_branch or "",
        }
        if result_data:
            if "artifacts" in result_data:
                artifacts.update(result_data["artifacts"])
            if "metrics" in result_data:
                artifacts["metrics"] = result_data["metrics"]

        return NodeResult(
            success=success,
            artifacts=artifacts,
            error_message=error_message,
        )

    def can_fork(self, result: NodeResult) -> bool:
        return False

    def default_next_nodes(self, result: NodeResult) -> list[NodeSpawnSpec]:
        return []
