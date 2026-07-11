import os
import subprocess
from pathlib import Path

import pytest

from luml_prisma.infra.exceptions import MergeConflictError
from luml_prisma.services.merge import (
    can_fast_forward,
    get_branch_diff_stats,
    get_merge_preview,
    merge_branch,
)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "t@t.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "t@t.com",
    }
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=repo, capture_output=True, env=env,
    )
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"],
        cwd=repo, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo, capture_output=True,
    )
    (repo / "README.md").write_text("# Test")
    subprocess.run(
        ["git", "add", "."],
        cwd=repo, capture_output=True, env=env,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=repo, capture_output=True, env=env,
    )
    return repo


def _create_branch_with_commit(
    repo: Path, branch: str, filename: str, content: str,
) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "t@t.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "t@t.com",
    }
    subprocess.run(
        ["git", "checkout", "-b", branch],
        cwd=repo, capture_output=True, env=env,
    )
    (repo / filename).write_text(content)
    subprocess.run(
        ["git", "add", "."],
        cwd=repo, capture_output=True, env=env,
    )
    subprocess.run(
        ["git", "commit", "-m", f"add {filename}"],
        cwd=repo, capture_output=True, env=env,
    )
    subprocess.run(
        ["git", "checkout", "main"],
        cwd=repo, capture_output=True, env=env,
    )


@pytest.mark.asyncio
async def test_get_branch_diff_stats(git_repo: Path) -> None:
    _create_branch_with_commit(
        git_repo, "feature", "new.txt", "hello\nworld\n",
    )
    stats = await get_branch_diff_stats(git_repo, "feature", "main")
    assert stats.commits_ahead == 1
    assert stats.files_changed == 1
    assert stats.insertions >= 1


@pytest.mark.asyncio
async def test_can_fast_forward_true(git_repo: Path) -> None:
    _create_branch_with_commit(
        git_repo, "ff-branch", "ff.txt", "content",
    )
    result = await can_fast_forward(git_repo, "ff-branch", "main")
    assert result is True


@pytest.mark.asyncio
async def test_can_fast_forward_false(git_repo: Path) -> None:
    _create_branch_with_commit(
        git_repo, "diverge", "diverge.txt", "content",
    )
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "t@t.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "t@t.com",
    }
    (git_repo / "main-change.txt").write_text("main changed")
    subprocess.run(
        ["git", "add", "."],
        cwd=git_repo, capture_output=True, env=env,
    )
    subprocess.run(
        ["git", "commit", "-m", "main change"],
        cwd=git_repo, capture_output=True, env=env,
    )
    result = await can_fast_forward(git_repo, "diverge", "main")
    assert result is False


@pytest.mark.asyncio
async def test_get_merge_preview(git_repo: Path) -> None:
    _create_branch_with_commit(
        git_repo, "preview-branch", "preview.txt", "data",
    )
    preview = await get_merge_preview(
        git_repo, "preview-branch", "main",
    )
    assert preview.branch == "preview-branch"
    assert preview.base_branch == "main"
    assert preview.stats.commits_ahead == 1
    assert len(preview.commit_messages) == 1
    assert "preview.txt" in preview.changed_files


@pytest.mark.asyncio
async def test_merge_branch(git_repo: Path) -> None:
    _create_branch_with_commit(
        git_repo, "merge-me", "merged.txt", "merged content",
    )
    await merge_branch(git_repo, "merge-me", "main")
    assert (git_repo / "merged.txt").exists()
    assert (git_repo / "merged.txt").read_text() == "merged content"


@pytest.mark.asyncio
async def test_merge_conflict_aborts(git_repo: Path) -> None:
    _create_branch_with_commit(
        git_repo, "conflict-branch", "README.md",
        "branch version",
    )
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "t@t.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "t@t.com",
    }
    (git_repo / "README.md").write_text("main version")
    subprocess.run(
        ["git", "add", "."],
        cwd=git_repo, capture_output=True, env=env,
    )
    subprocess.run(
        ["git", "commit", "-m", "conflict"],
        cwd=git_repo, capture_output=True, env=env,
    )

    with pytest.raises(MergeConflictError):
        await merge_branch(git_repo, "conflict-branch", "main")
