import contextlib
from pathlib import Path

from luml_prisma.config import AppConfig
from luml_prisma.infra.exceptions import (
    InvalidOperationError,
    RepositoryNotFoundError,
    TaskNotFoundError,
)
from luml_prisma.models import TaskOrm
from luml_prisma.repositories.repository import RepositoryRepository
from luml_prisma.repositories.task import TaskRepository
from luml_prisma.schemas.task import TaskStatus
from luml_prisma.services.agents import build_agent_command, get_agent
from luml_prisma.services.merge import get_merge_preview, merge_branch
from luml_prisma.services.pty_manager import PtyManager
from luml_prisma.services.worktree import (
    create_worktree,
    remove_worktree,
)


class TaskHandler:
    def __init__(
        self,
        task_repo: TaskRepository,
        repository_repo: RepositoryRepository,
        pty: PtyManager,
        config: AppConfig,
    ) -> None:
        self._tasks = task_repo
        self._repositories = repository_repo
        self._pty = pty
        self._config = config

    async def create(
        self,
        repository_id: str,
        name: str,
        agent_id: str,
        prompt: str,
        base_branch: str = "main",
        auto_mode: bool = False,
    ) -> TaskOrm:
        repo = self._repositories.get(repository_id)
        if not repo:
            raise RepositoryNotFoundError

        agent = get_agent(agent_id)
        if not agent:
            raise InvalidOperationError(
                f"Unknown agent: {agent_id}"
            )

        worktree_path, branch = await create_worktree(
            repo.path,
            name,
            base_branch,
            self._config.branch_prefix,
            self._config.preserve_patterns,
        )

        return self._tasks.add(
            repository_id=repository_id,
            name=name,
            branch=branch,
            worktree_path=worktree_path,
            agent_id=agent_id,
            prompt=prompt,
            status=TaskStatus.PENDING,
            base_branch=base_branch,
            auto_mode=auto_mode,
        )

    async def delete(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if not task:
            raise TaskNotFoundError

        self._pty.terminate_task(task_id)

        repo = self._repositories.get(task.repository_id)
        if repo:
            with contextlib.suppress(RuntimeError):
                await remove_worktree(
                    repo.path,
                    task.worktree_path,
                    task.branch,
                )

        self._tasks.remove(task_id)

    def get(self, task_id: str) -> TaskOrm:
        task = self._tasks.get(task_id)
        if not task:
            raise TaskNotFoundError
        return task

    def list_all(
        self, repository_id: str | None = None,
    ) -> list[TaskOrm]:
        return self._tasks.list_all(repository_id)

    def update_status(
        self, task_id: str, status: str,
    ) -> TaskOrm:
        task = self._tasks.get(task_id)
        if not task:
            raise TaskNotFoundError
        try:
            TaskStatus(status)
        except ValueError as exc:
            raise InvalidOperationError(
                f"Invalid status: {status}"
            ) from exc
        self._tasks.update_status(task_id, status)
        return self._tasks.get(task_id)  # type: ignore[return-value]

    def open_terminal(
        self, task_id: str, mode: str = "agent",
    ) -> TaskOrm:
        task = self._tasks.get(task_id)
        if not task:
            raise TaskNotFoundError

        if self._pty.get_active_session_id(task_id):
            return task

        worktree = Path(task.worktree_path)
        if not worktree.is_dir():
            raise InvalidOperationError(
                f"Worktree directory missing: "
                f"{task.worktree_path}"
            )

        if mode == "shell":
            command = ["bash"]
            session_type = "shell"
        else:
            agent = get_agent(task.agent_id)
            if not agent:
                raise InvalidOperationError(
                    f"Unknown agent: {task.agent_id}"
                )
            cmd_str = build_agent_command(
                agent, task.prompt, auto_approve=task.auto_mode,
            )
            command = ["bash", "-c", cmd_str]
            session_type = "agent"
            self._tasks.update_status(
                task_id, TaskStatus.RUNNING,
            )

        self._pty.spawn(
            task_id,
            command,
            cwd=task.worktree_path,
            session_type=session_type,
        )
        return self._tasks.get(task_id)  # type: ignore[return-value]

    async def merge_preview(
        self, task_id: str,
    ) -> dict:  # type: ignore[type-arg]
        task = self._tasks.get(task_id)
        if not task:
            raise TaskNotFoundError
        repo = self._repositories.get(task.repository_id)
        if not repo:
            raise RepositoryNotFoundError

        preview = await get_merge_preview(
            repo.path,
            task.branch,
            task.base_branch,
        )
        return {
            "branch": preview.branch,
            "base_branch": preview.base_branch,
            "stats": {
                "commits_ahead": preview.stats.commits_ahead,
                "files_changed": preview.stats.files_changed,
                "insertions": preview.stats.insertions,
                "deletions": preview.stats.deletions,
            },
            "commit_messages": preview.commit_messages,
            "changed_files": preview.changed_files,
            "can_fast_forward": preview.can_fast_forward,
        }

    async def merge(self, task_id: str) -> str:
        task = self._tasks.get(task_id)
        if not task:
            raise TaskNotFoundError
        repo = self._repositories.get(task.repository_id)
        if not repo:
            raise RepositoryNotFoundError

        result = await merge_branch(
            repo.path,
            task.branch,
            task.base_branch,
        )
        self._tasks.update_status(
            task_id, TaskStatus.MERGED,
        )
        return result
