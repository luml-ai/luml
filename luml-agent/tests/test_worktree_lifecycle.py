import os
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from luml_agent.config import AppConfig
from luml_agent.database import Database
from luml_agent.handlers.run import RunHandler
from luml_agent.infra.exceptions import MergeConflictError
from luml_agent.services.merge import merge_branch
from luml_agent.services.orchestrator.engine import (
    OrchestratorEngine,
    _UnrecoverableSchedulerError,
)
from luml_agent.services.orchestrator.models import (
    NodeStatus,
    RunStatus,
)
from luml_agent.services.orchestrator.registry import NodeRegistry
from luml_agent.services.pty_manager import PtyManager
from luml_agent.services.worktree import (
    auto_commit_changes,
    create_worktree,
    remove_worktree,
    setup_shared_paths,
)

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "t@t.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "t@t.com",
}


def _git(args: list[str], cwd: str | Path) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd, capture_output=True, env=GIT_ENV,
    )


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "t@t.com"], repo)
    _git(["config", "user.name", "Test"], repo)
    (repo / "README.md").write_text("# Test")
    _git(["add", "."], repo)
    _git(["commit", "-m", "initial"], repo)
    return repo


@pytest.fixture
def db() -> Database:
    return Database()


@pytest.fixture
def pty() -> PtyManager:
    mgr = PtyManager()
    yield mgr  # type: ignore[misc]
    mgr.shutdown()


@pytest.fixture
def engine(
    db: Database, pty: PtyManager,
) -> OrchestratorEngine:
    return OrchestratorEngine(
        db=db, pty=pty, registry=NodeRegistry(),
    )


# --- Worktree cleanup tests ---


class TestWorktreeCleanupOnMerge:
    @pytest.mark.asyncio
    async def test_worktrees_removed_after_merge(
        self, git_repo: Path, db: Database,
    ) -> None:
        repo_obj = db.add_repository("r", str(git_repo))
        run = db.add_run(
            repo_obj.id, "run1", "obj", base_branch="main",
        )
        db.update_run_status(run.id, RunStatus.RUNNING)

        wt_path, branch = await create_worktree(
            git_repo, "test", "main",
        )
        (Path(wt_path) / "new.txt").write_text("hi")
        _git(["add", "."], wt_path)
        _git(["commit", "-m", "change"], wt_path)

        node = db.add_run_node(
            run.id, None, "implement", 0,
            worktree_path=wt_path, branch=branch,
        )
        db.update_node_status(node.id, NodeStatus.SUCCEEDED)
        db.update_run_best_node(run.id, node.id)

        eng = MagicMock(spec=OrchestratorEngine)
        eng.cancel_run = AsyncMock()
        handler = RunHandler(
            db.runs, db.nodes, db.repositories, eng,
        )
        await handler.merge(run.id)
        assert not Path(wt_path).exists()

    @pytest.mark.asyncio
    async def test_cleanup_error_does_not_fail_merge(
        self, git_repo: Path, db: Database,
    ) -> None:
        repo_obj = db.add_repository("r", str(git_repo))
        run = db.add_run(
            repo_obj.id, "run1", "obj", base_branch="main",
        )

        wt_path, branch = await create_worktree(
            git_repo, "test", "main",
        )
        (Path(wt_path) / "new.txt").write_text("hi")
        _git(["add", "."], wt_path)
        _git(["commit", "-m", "change"], wt_path)

        node = db.add_run_node(
            run.id, None, "implement", 0,
            worktree_path=wt_path, branch=branch,
        )
        db.update_node_status(node.id, NodeStatus.SUCCEEDED)
        db.update_run_best_node(run.id, node.id)

        eng = MagicMock(spec=OrchestratorEngine)
        handler = RunHandler(
            db.runs, db.nodes, db.repositories, eng,
        )
        with patch(
            "luml_agent.handlers.run.remove_worktree",
            side_effect=RuntimeError("boom"),
        ):
            result = await handler.merge(run.id)
        assert result is not None


class TestWorktreeCleanupOnDelete:
    @pytest.mark.asyncio
    async def test_worktrees_removed_on_delete(
        self, git_repo: Path, db: Database,
    ) -> None:
        repo_obj = db.add_repository("r", str(git_repo))
        run = db.add_run(
            repo_obj.id, "run1", "obj", base_branch="main",
        )

        wt_path, branch = await create_worktree(
            git_repo, "del-test", "main",
        )
        db.add_run_node(
            run.id, None, "implement", 0,
            worktree_path=wt_path, branch=branch,
        )

        eng = MagicMock(spec=OrchestratorEngine)
        handler = RunHandler(
            db.runs, db.nodes, db.repositories, eng,
        )
        await handler.delete(run.id)
        assert not Path(wt_path).exists()


class TestWorktreeCleanupOnCancel:
    @pytest.mark.asyncio
    async def test_worktrees_removed_on_cancel(
        self, git_repo: Path, db: Database,
    ) -> None:
        repo_obj = db.add_repository("r", str(git_repo))
        run = db.add_run(
            repo_obj.id, "run1", "obj", base_branch="main",
        )
        db.update_run_status(run.id, RunStatus.RUNNING)

        wt_path, branch = await create_worktree(
            git_repo, "cancel-test", "main",
        )
        db.add_run_node(
            run.id, None, "implement", 0,
            worktree_path=wt_path, branch=branch,
        )

        eng = MagicMock(spec=OrchestratorEngine)
        eng.cancel_run = AsyncMock()
        handler = RunHandler(
            db.runs, db.nodes, db.repositories, eng,
        )
        await handler.cancel(run.id)
        assert not Path(wt_path).exists()


# --- Shared paths tests ---


class TestSharedPaths:
    def test_symlink_created_for_existing_path(
        self, git_repo: Path, tmp_path: Path,
    ) -> None:
        data_dir = git_repo / "data"
        data_dir.mkdir()
        (data_dir / "train.csv").write_text("a,b\n1,2")

        wt = tmp_path / "worktree"
        wt.mkdir()
        (wt / "data").mkdir()

        linked = setup_shared_paths(git_repo, wt, ["data"])
        assert linked == ["data"]
        assert (wt / "data").is_symlink()
        assert (wt / "data").resolve() == data_dir.resolve()
        assert (wt / "data" / "train.csv").read_text() == "a,b\n1,2"

    def test_skips_nonexistent_path(
        self, git_repo: Path, tmp_path: Path,
    ) -> None:
        wt = tmp_path / "worktree"
        wt.mkdir()
        linked = setup_shared_paths(git_repo, wt, ["data"])
        assert linked == []
        assert not (wt / "data").exists()

    @pytest.mark.asyncio
    async def test_shared_paths_added_to_gitignore(
        self, git_repo: Path,
    ) -> None:
        data_dir = git_repo / "data"
        data_dir.mkdir()
        (data_dir / "file.bin").write_text("big data")
        _git(["add", "."], git_repo)
        _git(["commit", "-m", "add data"], git_repo)

        wt_path, branch = await create_worktree(
            git_repo, "shared-test", "main",
            shared_paths=["data"],
        )
        wt = Path(wt_path)
        assert (wt / "data").is_symlink()

        gitignore = (wt / ".gitignore").read_text()
        assert "data/" in gitignore
        assert ".luml-agent/" in gitignore

        await remove_worktree(git_repo, wt_path, branch)


# --- Auto-commit tests ---


class TestAutoCommit:
    @pytest.mark.asyncio
    async def test_auto_commit_dirty_worktree(
        self, git_repo: Path,
    ) -> None:
        wt_path, branch = await create_worktree(
            git_repo, "autocommit-test", "main",
        )
        wt = Path(wt_path)
        (wt / "new_file.py").write_text("print('hello')")

        committed = await auto_commit_changes(wt_path)
        assert committed is True

        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=wt_path, capture_output=True, text=True,
        )
        assert result.stdout.strip() == ""

        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=wt_path, capture_output=True, text=True,
        )
        assert "luml-agent: auto-commit" in result.stdout

        await remove_worktree(git_repo, wt_path, branch)

    @pytest.mark.asyncio
    async def test_no_auto_commit_when_clean(
        self, git_repo: Path,
    ) -> None:
        wt_path, branch = await create_worktree(
            git_repo, "clean-test", "main",
        )
        _git(["add", "-A"], wt_path)
        _git(["commit", "-m", "setup"], wt_path)

        committed = await auto_commit_changes(wt_path)
        assert committed is False

        await remove_worktree(git_repo, wt_path, branch)

    @pytest.mark.asyncio
    async def test_auto_commit_after_debug(
        self, git_repo: Path,
    ) -> None:
        wt_path, branch = await create_worktree(
            git_repo, "debug-commit", "main",
        )
        wt = Path(wt_path)
        (wt / "fix.py").write_text("fixed = True")

        committed = await auto_commit_changes(wt_path)
        assert committed is True

        await remove_worktree(git_repo, wt_path, branch)


# --- Merge conflict detection tests ---


class TestMergeConflictDetection:
    @pytest.mark.asyncio
    async def test_merge_conflict_raises_with_file_list(
        self, git_repo: Path,
    ) -> None:
        _git(["checkout", "-b", "conflict-branch"], git_repo)
        (git_repo / "README.md").write_text("branch version")
        _git(["add", "."], git_repo)
        _git(["commit", "-m", "branch change"], git_repo)
        _git(["checkout", "main"], git_repo)

        (git_repo / "README.md").write_text("main version")
        _git(["add", "."], git_repo)
        _git(["commit", "-m", "main change"], git_repo)

        with pytest.raises(MergeConflictError) as exc_info:
            await merge_branch(
                git_repo, "conflict-branch", "main",
            )

        assert exc_info.value.status_code == 409
        assert "README.md" in exc_info.value.conflicting_files

    @pytest.mark.asyncio
    async def test_non_conflict_failure_raises_runtime(
        self, git_repo: Path,
    ) -> None:
        with pytest.raises(RuntimeError, match="Merge failed"):
            await merge_branch(
                git_repo, "nonexistent-branch", "main",
            )


# --- Scheduler resilience tests ---


class TestSchedulerResilience:
    @pytest.mark.asyncio
    async def test_stops_on_unrecoverable_error(
        self, db: Database, pty: PtyManager,
    ) -> None:
        repo_obj = db.add_repository("r", "/tmp/fake")
        run = db.add_run(repo_obj.id, "run1", "obj")
        db.update_run_status(run.id, RunStatus.RUNNING)
        db.add_run_node(run.id, None, "implement", 0)

        eng = OrchestratorEngine(
            db=db, pty=pty, registry=NodeRegistry(),
        )

        with (
            patch.object(
                db, "list_runs",
                side_effect=RuntimeError("DB gone"),
            ),
            pytest.raises(_UnrecoverableSchedulerError),
        ):
            await eng._schedule_tick()

    @pytest.mark.asyncio
    async def test_fail_all_running_runs(
        self, db: Database, pty: PtyManager,
    ) -> None:
        repo_obj = db.add_repository("r", "/tmp/fake")
        run = db.add_run(repo_obj.id, "run1", "obj")
        db.update_run_status(run.id, RunStatus.RUNNING)
        node = db.add_run_node(run.id, None, "implement", 0)

        eng = OrchestratorEngine(
            db=db, pty=pty, registry=NodeRegistry(),
        )
        await eng._fail_all_running_runs()

        refreshed_run = db.get_run(run.id)
        assert refreshed_run is not None
        assert refreshed_run.status == RunStatus.FAILED

        refreshed_node = db.get_run_node(node.id)
        assert refreshed_node is not None
        assert refreshed_node.status == NodeStatus.FAILED

    @pytest.mark.asyncio
    async def test_recoverable_error_continues(
        self, db: Database, pty: PtyManager,
    ) -> None:
        repo_obj = db.add_repository("r", "/tmp/fake")
        run = db.add_run(repo_obj.id, "run1", "obj")
        db.update_run_status(run.id, RunStatus.RUNNING)

        eng = OrchestratorEngine(
            db=db, pty=pty, registry=NodeRegistry(),
        )

        call_count = 0

        def failing_candidates(
            run_id: str, slots: int,
        ) -> list:
            nonlocal call_count
            call_count += 1
            raise ValueError("single node error")

        eng._get_next_candidates = failing_candidates  # type: ignore[assignment]

        with patch(
            "luml_agent.services.orchestrator.engine.logger",
        ):
            try:
                await eng._schedule_tick()
            except _UnrecoverableSchedulerError:
                pytest.fail(
                    "Should not raise unrecoverable",
                )
            except ValueError:
                pass

        assert call_count == 1


# --- Config tests ---


class TestExcludePatternsRemoved:
    def test_no_exclude_patterns_on_config(self) -> None:
        fields = {
            f.name
            for f in AppConfig.__dataclass_fields__.values()
        }
        assert "exclude_patterns" not in fields

    def test_shared_paths_default(self) -> None:
        config = AppConfig(
            data_dir=Path("/tmp"),
            db_path=Path("/tmp/db"),
        )
        assert config.shared_paths == ["data"]

    def test_shared_paths_custom(self) -> None:
        config = AppConfig(
            data_dir=Path("/tmp"),
            db_path=Path("/tmp/db"),
            shared_paths=["data", "checkpoints"],
        )
        assert config.shared_paths == ["data", "checkpoints"]
