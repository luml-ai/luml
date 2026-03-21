from pathlib import Path

from luml_agent.infra.exceptions import RepositoryNotFoundError
from luml_agent.models import RepositoryOrm
from luml_agent.repositories.repository import RepositoryRepository
from luml_agent.repositories.task import TaskRepository
from luml_agent.services.pty_manager import PtyManager


class RepositoryHandler:
    def __init__(
        self,
        repository_repo: RepositoryRepository,
        task_repo: TaskRepository,
        pty: PtyManager,
    ) -> None:
        self._repositories = repository_repo
        self._tasks = task_repo
        self._pty = pty

    def create(
        self, name: str, path: str,
    ) -> RepositoryOrm:
        resolved = Path(path).resolve()
        if not (resolved / ".git").exists():
            from luml_agent.infra.exceptions import (
                InvalidOperationError,
            )

            raise InvalidOperationError(
                f"Not a git repository: {resolved}"
            )
        return self._repositories.add(name, str(resolved))

    def delete(self, repository_id: str) -> None:
        if not self._repositories.get(repository_id):
            raise RepositoryNotFoundError
        for task in self._tasks.list_all(repository_id):
            self._pty.terminate_task(task.id)
        self._repositories.remove(repository_id)

    def list_all(self) -> list[RepositoryOrm]:
        return self._repositories.list_all()
