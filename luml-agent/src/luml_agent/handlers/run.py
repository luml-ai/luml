from typing import Any

from luml_agent.exceptions import (
    InvalidOperationError,
    RepositoryNotFoundError,
    RunNotFoundError,
)
from luml_agent.orchestrator.engine import OrchestratorEngine
from luml_agent.orchestrator.models import (
    RunConfig,
    RunStatus,
)
from luml_agent.orm import RunOrm
from luml_agent.repositories.node import RunNodeRepository
from luml_agent.repositories.repository import RepositoryRepository
from luml_agent.repositories.run import RunRepository
from luml_agent.schemas import RunCreateIn


class RunHandler:
    def __init__(
        self,
        run_repo: RunRepository,
        node_repo: RunNodeRepository,
        repository_repo: RepositoryRepository,
        engine: OrchestratorEngine,
    ) -> None:
        self._runs = run_repo
        self._nodes = node_repo
        self._repositories = repository_repo
        self._engine = engine

    async def create(self, body: RunCreateIn) -> RunOrm:
        if not self._repositories.get(body.repository_id):
            raise RepositoryNotFoundError

        config = RunConfig(
            max_depth=body.max_depth,
            max_children_per_fork=body.max_children_per_fork,
            max_debug_retries=body.max_debug_retries,
            max_concurrency=body.max_concurrency,
            run_command_template=body.run_command,
            agent_id=body.agent_id,
            fork_auto_approve=body.fork_auto_approve,
            auto_mode=body.auto_mode,
            auto_terminate_timeout=(
                body.auto_terminate_timeout
            ),
        )

        run_id = await self._engine.create_run(
            repository_id=body.repository_id,
            name=body.name,
            objective=body.objective,
            config=config,
            root_payload={"prompt": body.objective},
            base_branch=body.base_branch,
        )
        return self._runs.get(run_id)  # type: ignore[return-value]

    def list_all(
        self, repository_id: str | None = None,
    ) -> list[RunOrm]:
        return self._runs.list_all(repository_id)

    def get(self, run_id: str) -> RunOrm:
        run = self._runs.get(run_id)
        if not run:
            raise RunNotFoundError
        return run

    async def start(self, run_id: str) -> RunOrm:
        if not self._runs.get(run_id):
            raise RunNotFoundError
        await self._engine.start_run(run_id)
        return self._runs.get(run_id)  # type: ignore[return-value]

    async def cancel(self, run_id: str) -> RunOrm:
        if not self._runs.get(run_id):
            raise RunNotFoundError
        await self._engine.cancel_run(run_id)
        return self._runs.get(run_id)  # type: ignore[return-value]

    async def restart(self, run_id: str) -> RunOrm:
        run = self._runs.get(run_id)
        if not run:
            raise RunNotFoundError
        if run.status not in (
            RunStatus.FAILED,
            RunStatus.CANCELED,
            RunStatus.SUCCEEDED,
        ):
            raise InvalidOperationError(
                f"Cannot restart run with status: "
                f"{run.status}"
            )
        await self._engine.restart_run(run_id)
        return self._runs.get(run_id)  # type: ignore[return-value]

    def delete(self, run_id: str) -> None:
        run = self._runs.get(run_id)
        if not run:
            raise RunNotFoundError
        if run.status == RunStatus.RUNNING:
            raise InvalidOperationError(
                "Cannot delete a running run"
            )
        self._runs.remove(run_id)

    def get_graph(
        self, run_id: str,
    ) -> dict[str, Any]:
        if not self._runs.get(run_id):
            raise RunNotFoundError
        nodes = self._nodes.list_nodes(run_id)
        edges = self._nodes.list_edges(run_id)
        return {"nodes": nodes, "edges": edges}

    def get_events(
        self,
        run_id: str,
        after_seq: int = 0,
    ) -> list[Any]:  # noqa: ANN401
        if not self._runs.get(run_id):
            raise RunNotFoundError
        return self._nodes.list_events(
            run_id, after_seq,
        )
