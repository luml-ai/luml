import asyncio
from typing import Any

from luml_agent.services.agents import build_agent_command, get_agent
from luml_agent.services.orchestrator.nodes.base import (
    NodeExecutionContext,
    NodeResult,
    NodeSpawnSpec,
)
from luml_agent.services.orchestrator.nodes.result_file import read_result_file
from luml_agent.services.worktree import create_worktree


class ImplementNodeHandler:
    def type_id(self) -> str:
        return "implement"

    def validate_payload(self, payload: dict[str, Any]) -> None:
        if "prompt" not in payload:
            raise ValueError("Implement node requires 'prompt' in payload")

    async def execute(self, ctx: NodeExecutionContext) -> NodeResult:
        prompt = ctx.payload.get("prompt", "")
        agent_id = ctx.run_config.get("agent_id", "claude")
        app_config = ctx.services.config

        source_branch = ctx.parent_branch or ctx.base_branch
        worktree_path, branch = await create_worktree(
            ctx.repository_path,
            f"run{ctx.run_id}-node{ctx.node_id}",
            source_branch,
            app_config.branch_prefix,
            app_config.preserve_patterns,
        )

        ctx.services.db.update_node_worktree(ctx.node_id, worktree_path, branch)

        agent = get_agent(agent_id)
        if agent is None:
            return NodeResult(success=False, error_message=f"Unknown agent: {agent_id}")

        cmd_str = build_agent_command(agent, prompt)
        command = ["bash", "-c", cmd_str]

        session = ctx.services.pty.spawn(
            task_id=ctx.node_id,
            command=command,
            cwd=worktree_path,
        )

        ctx.services.db.add_node_session(ctx.node_id, session.session_id)
        ctx.services.engine.notify_session_started(ctx.node_id, session.session_id)

        exit_event = asyncio.Event()
        ctx.services.engine.register_session_completion(session.session_id, exit_event)

        await exit_event.wait()

        exit_code = ctx.services.engine.get_session_exit_code(session.session_id)

        result_data = read_result_file(worktree_path)
        if result_data is not None:
            success = result_data["success"]
            error_message = result_data.get("error_message", "")
        else:
            success = exit_code == 0
            error_message = ""

        artifacts: dict[str, Any] = {
            "worktree_path": worktree_path,
            "branch": branch,
            "exit_code": exit_code or 0,
            "session_id": session.session_id,
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
        return result.success

    def default_next_nodes(self, result: NodeResult) -> list[NodeSpawnSpec]:
        return []
