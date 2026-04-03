import logging
from typing import Any

from luml_agent.infra.exceptions import (
    InvalidOperationError,
    RepositoryNotFoundError,
    RunNotFoundError,
)
from luml_agent.models import RunOrm
from luml_agent.repositories.node import RunNodeRepository
from luml_agent.repositories.repository import RepositoryRepository
from luml_agent.repositories.run import RunRepository
from luml_agent.schemas import RunCreateIn
from luml_agent.services.merge import get_merge_preview, merge_branch
from luml_agent.services.orchestrator.engine import OrchestratorEngine
from luml_agent.services.orchestrator.models import (
    RunConfig,
    RunStatus,
)
from luml_agent.services.upload_queue import UploadQueue
from luml_agent.services.worktree import remove_worktree

logger = logging.getLogger(__name__)


class RunHandler:
    def __init__(
        self,
        run_repo: RunRepository,
        node_repo: RunNodeRepository,
        repository_repo: RepositoryRepository,
        engine: OrchestratorEngine,
        upload_queue: UploadQueue | None = None,
    ) -> None:
        self._runs = run_repo
        self._nodes = node_repo
        self._repositories = repository_repo
        self._engine = engine
        self._upload_queue = upload_queue

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
            max_log_tail=body.max_log_tail,
            primary_metric=body.primary_metric,
            luml_collection_id=body.luml_collection_id,
            luml_organization_id=body.luml_organization_id,
            luml_orbit_id=body.luml_orbit_id,
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
        run = self._runs.get(run_id)
        if self._upload_queue:
            self._upload_queue.cancel_pending(run_id)
        await self._cleanup_run_worktrees(run_id, force=True)
        return run  # type: ignore[return-value]

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

    async def delete(self, run_id: str) -> None:
        run = self._runs.get(run_id)
        if not run:
            raise RunNotFoundError
        if run.status == RunStatus.RUNNING:
            raise InvalidOperationError(
                "Cannot delete a running run"
            )
        if self._upload_queue:
            self._upload_queue.cancel_pending(run_id)
        await self._cleanup_run_worktrees(run_id, force=True)
        self._runs.remove(run_id)

    def _get_best_node(self, run_id: str) -> tuple[Any, Any]:
        run = self._runs.get(run_id)
        if not run:
            raise RunNotFoundError
        if not run.best_node_id:
            raise InvalidOperationError("Run has no best node")
        node = self._nodes.get_node(run.best_node_id)
        if not node:
            raise InvalidOperationError("Best node not found")
        return run, node

    async def merge_preview(
        self, run_id: str,
    ) -> dict[str, Any]:
        run, node = self._get_best_node(run_id)
        repo = self._repositories.get(run.repository_id)
        if not repo:
            raise RepositoryNotFoundError

        preview = await get_merge_preview(
            repo.path, node.branch, run.base_branch,
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

    async def merge(self, run_id: str) -> str:
        run, node = self._get_best_node(run_id)
        repo = self._repositories.get(run.repository_id)
        if not repo:
            raise RepositoryNotFoundError

        result = await merge_branch(
            repo.path, node.branch, run.base_branch,
        )
        self._runs.update_status(run_id, RunStatus.MERGED)
        await self._cleanup_run_worktrees(run_id)
        return result

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

    async def _cleanup_run_worktrees(
        self, run_id: str, *, force: bool = False,
    ) -> None:
        run = self._runs.get(run_id)
        if not run:
            return
        repo = self._repositories.get(run.repository_id)
        if not repo:
            return
        nodes = self._nodes.list_nodes(run_id)

        deferred_node_ids: set[str] = set()
        if not force and self._upload_queue:
            all_node_ids = [n.id for n in nodes]
            active_uploads = self._upload_queue.get_active_for_nodes(all_node_ids)
            deferred_node_ids = {u.node_id for u in active_uploads}

        if deferred_node_ids:
            self._engine._emit_event(run_id, None, "worktrees_pending_upload", {
                "deferred_node_ids": sorted(deferred_node_ids),
            })

        seen_paths: set[str] = set()
        for node in nodes:
            wt = node.worktree_path
            branch = node.branch
            if not wt or not branch or wt in seen_paths:
                continue
            seen_paths.add(wt)
            if node.id in deferred_node_ids:
                continue
            try:
                await remove_worktree(repo.path, wt, branch)
            except Exception:
                logger.warning(
                    "Failed to clean up worktree %s for run %s",
                    wt, run_id, exc_info=True,
                )

    async def try_deferred_worktree_cleanup(self, run_id: str) -> None:
        if not self._upload_queue:
            return
        nodes = self._nodes.list_nodes(run_id)
        all_node_ids = [n.id for n in nodes]
        active = self._upload_queue.get_active_for_nodes(all_node_ids)
        if not active:
            await self._cleanup_run_worktrees(run_id, force=True)
