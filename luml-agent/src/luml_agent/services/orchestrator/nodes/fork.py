import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from luml_agent.services.agents import build_agent_command, get_agent
from luml_agent.services.orchestrator.nodes.base import (
    NodeExecutionContext,
    NodeResult,
    NodeSpawnSpec,
)
from luml_agent.services.orchestrator.nodes.result_file import read_result_file
from luml_agent.services.orchestrator.utils import ensure_luml_agent_dir

logger = logging.getLogger(__name__)


class ForkNodeHandler:
    def type_id(self) -> str:
        return "fork"

    def validate_payload(self, payload: dict[str, Any]) -> None:
        pass

    async def execute(self, ctx: NodeExecutionContext) -> NodeResult:
        worktree_path = ctx.parent_worktree_path
        if not worktree_path:
            return NodeResult(success=False, error_message="No worktree path for fork")

        objective = ctx.payload.get("objective", "")
        context_info = ctx.payload.get("context", "")
        max_children = ctx.run_config.get("max_children_per_fork", 3)

        ensure_luml_agent_dir(worktree_path)

        proposals_dir = Path(worktree_path) / ".proposals"
        proposals_dir.mkdir(exist_ok=True)

        gitignore_path = Path(worktree_path) / ".gitignore"
        _ensure_gitignore_entry(gitignore_path, ".proposals/")
        _ensure_gitignore_entry(gitignore_path, ".luml-fork.json")

        fork_prompt = (
            f"Decompose the following objective into at most {max_children} "
            f"atomic, independently implementable changes.\n\n"
            f"Objective: {objective}\n\n"
            f"Context: {context_info}\n\n"
            f"Write a file called .luml-fork.json in the repo root.\n"
            f"It must be a JSON array of strings, where each string is a "
            f"self-contained prompt describing one change to implement."
        )

        agent_id = ctx.run_config.get("agent_id", "claude")
        agent = get_agent(agent_id)
        if agent is None:
            return NodeResult(success=False, error_message=f"Unknown agent: {agent_id}")

        cmd_str = build_agent_command(agent, fork_prompt)
        command = ["bash", "-c", cmd_str]

        session = ctx.services.pty.spawn(
            task_id=ctx.node_id,
            command=command,
            cwd=worktree_path,
        )

        ctx.services.db.add_node_session(ctx.node_id, session.session_id)
        ctx.services.db.update_node_worktree(
            ctx.node_id, worktree_path, ctx.parent_branch or "",
        )

        exit_event = asyncio.Event()
        ctx.services.engine.register_session_completion(session.session_id, exit_event)

        timeout = ctx.run_config.get("fork_timeout", 900)
        try:
            await asyncio.wait_for(
                exit_event.wait(),
                timeout=timeout if timeout > 0 else None,
            )
        except TimeoutError:
            logger.warning(
                "Fork node %s timed out after %ds", ctx.node_id, timeout,
            )
            ctx.services.pty.terminate(session.session_id)
            return NodeResult(
                success=False,
                artifacts={"session_id": session.session_id},
                error_message=f"Node execution timed out after {timeout}s",
            )

        exit_code = ctx.services.engine.get_session_exit_code(session.session_id)

        result_data = read_result_file(worktree_path)
        if result_data is not None and not result_data["success"]:
            return NodeResult(
                success=False,
                error_message=result_data.get("error_message", "Fork agent failed"),
            )

        fork_strings = _read_fork_file(worktree_path, max_children)
        if fork_strings is not None:
            logger.info(
                "Fork node %d: read %d proposals from .luml-fork.json",
                ctx.node_id, len(fork_strings),
            )
            proposals = [{"prompt": s} for s in fork_strings]
        elif result_data is not None:
            proposals = result_data.get("proposals", [])[:max_children]
            logger.info(
                "Fork node %d: read %d proposals from result file",
                ctx.node_id, len(proposals),
            )
        else:
            proposals = _read_proposals(proposals_dir, max_children)
            logger.info(
                "Fork node %d: read %d proposals from .proposals/",
                ctx.node_id, len(proposals),
            )

        if exit_code != 0 and not proposals:
            return NodeResult(success=False, error_message="Fork agent failed")

        fork_auto_approve = ctx.run_config.get("fork_auto_approve", True)
        spawn_next: list[NodeSpawnSpec] = []
        if fork_auto_approve:
            for proposal in proposals:
                spawn_next.append(NodeSpawnSpec(
                    node_type="implement",
                    payload={"prompt": proposal.get("prompt", "")},
                    reason="fork",
                ))

        return NodeResult(
            success=True,
            artifacts={
                "proposals": proposals,
                "session_id": session.session_id,
                "auto_approved": fork_auto_approve,
            },
            spawn_next=spawn_next,
        )

    def can_fork(self, result: NodeResult) -> bool:
        return False

    def default_next_nodes(self, result: NodeResult) -> list[NodeSpawnSpec]:
        return []


def _read_fork_file(worktree_path: str, max_count: int) -> list[str] | None:
    path = Path(worktree_path) / ".luml-fork.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, list) or not all(isinstance(s, str) for s in data):
        return None
    return data[:max_count]


def _read_proposals(proposals_dir: Path, max_count: int) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    for i in range(1, max_count + 1):
        path = proposals_dir / f"proposal_{i}.json"
        if not path.exists():
            continue
        try:
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, dict):
                proposals.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return proposals


def _ensure_gitignore_entry(gitignore_path: Path, entry: str) -> None:
    if gitignore_path.exists():
        content = gitignore_path.read_text()
        if entry in content:
            return
        with open(gitignore_path, "a") as f:
            f.write(f"\n{entry}\n")
    else:
        gitignore_path.write_text(f"{entry}\n")
