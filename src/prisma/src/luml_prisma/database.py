from pathlib import Path

from luml_prisma.infra.db import (
    create_db_engine,
    create_session_factory,
)
from luml_prisma.migrate import run_migrations
from luml_prisma.models import (
    Base,
    NodeSessionOrm,
    RepositoryOrm,
    RunEdgeOrm,
    RunEventOrm,
    RunNodeOrm,
    RunOrm,
    TaskOrm,
)
from luml_prisma.schemas.task import TaskStatus


class Database:
    def __init__(
        self, db_path: Path | str | None = None,
    ) -> None:
        if db_path is None:
            db_url = "sqlite://"
        else:
            path = Path(db_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite:///{path}"

        self._engine = create_db_engine(db_url)
        self._session_factory = create_session_factory(self._engine)
        if db_path is None:
            Base.metadata.create_all(self._engine)
        else:
            run_migrations(self._engine)

        from luml_prisma.repositories.node import (
            RunNodeRepository,
        )
        from luml_prisma.repositories.repository import (
            RepositoryRepository,
        )
        from luml_prisma.repositories.run import RunRepository
        from luml_prisma.repositories.task import TaskRepository

        self.repositories = RepositoryRepository(self._session_factory)
        self.tasks = TaskRepository(self._session_factory)
        self.runs = RunRepository(self._session_factory)
        self.nodes = RunNodeRepository(self._session_factory)

    def close(self) -> None:
        self._engine.dispose()

    # -- Repository facade --

    def add_repository(
        self,
        name: str,
        path: str,
    ) -> RepositoryOrm:
        return self.repositories.add(name, path)

    def get_repository(
        self, repository_id: str,
    ) -> RepositoryOrm | None:
        return self.repositories.get(repository_id)

    def list_repositories(self) -> list[RepositoryOrm]:
        return self.repositories.list_all()

    def remove_repository(self, repository_id: str) -> None:
        self.repositories.remove(repository_id)

    # -- Task facade --

    def add_task(
        self,
        repository_id: str,
        name: str,
        branch: str,
        worktree_path: str,
        agent_id: str,
        prompt: str = "",
        tmux_session: str = "",
        status: str = TaskStatus.RUNNING,
        base_branch: str = "main",
    ) -> TaskOrm:
        return self.tasks.add(
            repository_id, name, branch, worktree_path,
            agent_id, prompt, tmux_session, status,
            base_branch,
        )

    def get_task(self, task_id: str) -> TaskOrm | None:
        return self.tasks.get(task_id)

    def list_tasks(
        self, repository_id: str | None = None,
    ) -> list[TaskOrm]:
        return self.tasks.list_all(repository_id)

    def update_task_status(
        self, task_id: str, status: str,
    ) -> None:
        self.tasks.update_status(task_id, status)

    def update_task_tmux_session(
        self, task_id: str, tmux_session: str,
    ) -> None:
        self.tasks.update_tmux_session(task_id, tmux_session)

    def remove_task(self, task_id: str) -> None:
        self.tasks.remove(task_id)

    # -- Run facade --

    def add_run(
        self,
        repository_id: str,
        name: str,
        objective: str,
        config_json: str = "{}",
        status: str = "pending",
        base_branch: str = "main",
    ) -> RunOrm:
        return self.runs.add(
            repository_id, name, objective,
            config_json, status, base_branch,
        )

    def get_run(self, run_id: str) -> RunOrm | None:
        return self.runs.get(run_id)

    def list_runs(
        self, repository_id: str | None = None,
    ) -> list[RunOrm]:
        return self.runs.list_all(repository_id)

    def update_run_status(
        self, run_id: str, status: str,
    ) -> None:
        self.runs.update_status(run_id, status)

    def update_run_best_node(
        self, run_id: str, node_id: str | None,
    ) -> None:
        self.runs.update_best_node(run_id, node_id)

    def update_run_discovered_metric_keys(
        self, run_id: str, keys_json: str,
    ) -> None:
        self.runs.update_discovered_metric_keys(run_id, keys_json)

    def remove_run(self, run_id: str) -> None:
        self.runs.remove(run_id)

    def reset_run_data(self, run_id: str) -> None:
        self.runs.reset_data(run_id)

    # -- RunNode facade --

    def add_run_node(
        self,
        run_id: str,
        parent_node_id: str | None,
        node_type: str,
        depth: int,
        payload_json: str = "{}",
        worktree_path: str = "",
        branch: str = "",
    ) -> RunNodeOrm:
        return self.nodes.add_node(
            run_id, parent_node_id, node_type,
            depth, payload_json, worktree_path, branch,
        )

    def get_run_node(self, node_id: str) -> RunNodeOrm | None:
        return self.nodes.get_node(node_id)

    def list_run_nodes(self, run_id: str) -> list[RunNodeOrm]:
        return self.nodes.list_nodes(run_id)

    def update_node_status(
        self, node_id: str, status: str,
    ) -> None:
        self.nodes.update_node_status(node_id, status)

    def update_node_result(
        self, node_id: str, result_json: str,
    ) -> None:
        self.nodes.update_node_result(node_id, result_json)

    def update_node_worktree(
        self,
        node_id: str,
        worktree_path: str,
        branch: str,
    ) -> None:
        self.nodes.update_node_worktree(
            node_id, worktree_path, branch,
        )

    def increment_node_debug_retries(
        self, node_id: str,
    ) -> int:
        return self.nodes.increment_debug_retries(node_id)

    # -- Edge facade --

    def add_run_edge(
        self,
        run_id: str,
        from_node_id: str,
        to_node_id: str,
        reason: str = "auto",
    ) -> RunEdgeOrm:
        return self.nodes.add_edge(
            run_id, from_node_id, to_node_id, reason,
        )

    def list_run_edges(self, run_id: str) -> list[RunEdgeOrm]:
        return self.nodes.list_edges(run_id)

    # -- Event facade --

    def get_next_event_seq(self, run_id: str) -> int:
        return self.nodes.get_next_event_seq(run_id)

    def add_run_event(
        self,
        run_id: str,
        node_id: str | None,
        event_type: str,
        data_json: str = "{}",
    ) -> RunEventOrm:
        return self.nodes.add_event(
            run_id, node_id, event_type, data_json,
        )

    def list_run_events(
        self, run_id: str, after_seq: int = 0,
    ) -> list[RunEventOrm]:
        return self.nodes.list_events(run_id, after_seq)

    # -- Session facade --

    def add_node_session(
        self, node_id: str, session_id: str,
    ) -> NodeSessionOrm:
        return self.nodes.add_session(node_id, session_id)

    def get_node_sessions(
        self, node_id: str,
    ) -> list[NodeSessionOrm]:
        return self.nodes.get_sessions(node_id)

    def get_node_by_session(
        self, session_id: str,
    ) -> RunNodeOrm | None:
        return self.nodes.get_node_by_session(session_id)
