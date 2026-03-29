import asyncio
import logging
import subprocess
from typing import Any

from luml_agent.services.agents import build_agent_command, get_agent
from luml_agent.services.orchestrator.nodes.base import (
    NodeExecutionContext,
    NodeResult,
    NodeSpawnSpec,
)
from luml_agent.services.orchestrator.nodes.result_file import read_result_file
from luml_agent.services.orchestrator.prompts import build_debug_prompt
from luml_agent.services.orchestrator.utils import ensure_luml_agent_dir
from luml_agent.services.worktree import auto_commit_changes

logger = logging.getLogger(__name__)


class DebugNodeHandler:
    def type_id(self) -> str:
        return "debug"

    def validate_payload(self, payload: dict[str, Any]) -> None:
        pass

    @staticmethod
    def _compute_git_diff(
        worktree_path: str,
        base_branch: str,
    ) -> str:
        try:
            result = subprocess.run(
                ["git", "diff", f"{base_branch}...HEAD"],
                cwd=worktree_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.stdout
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as exc:
            logger.warning("git diff failed in %s: %s", worktree_path, exc)
            return "(git diff unavailable)"

    async def execute(self, ctx: NodeExecutionContext) -> NodeResult:
        worktree_path = ctx.parent_worktree_path
        if not worktree_path:
            return NodeResult(success=False, error_message="No worktree path for debug")

        failure_context = ctx.payload.get("failure_context", {})
        logs = failure_context.get("logs", "")

        git_diff = self._compute_git_diff(worktree_path, ctx.base_branch)
        debug_prompt = build_debug_prompt(
            ctx.payload, git_diff, logs, ctx.run_config,
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
            success = result_data.success
            error_message = result_data.error_message or ""
        else:
            success = result_exit_code == 0
            error_message = ""

        artifacts: dict[str, Any] = {
            "exit_code": result_exit_code or 0,
            "session_id": session.session_id,
            "worktree_path": worktree_path,
            "branch": ctx.parent_branch or "",
        }
        if result_data and result_data.metrics:
            artifacts["metrics"] = result_data.metrics

        return NodeResult(
            success=success,
            artifacts=artifacts,
            error_message=error_message,
        )

    def can_fork(self, result: NodeResult) -> bool:
        return False

    def default_next_nodes(self, result: NodeResult) -> list[NodeSpawnSpec]:
        return []
