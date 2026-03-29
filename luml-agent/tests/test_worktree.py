import os
import subprocess
from pathlib import Path

import pytest

from luml_agent.services.worktree import (
    create_worktree,
    generate_short_id,
    get_worktree_status,
    preserve_env_files,
    remove_worktree,
    slugify,
)


def test_slugify() -> None:
    assert slugify("Fix Auth Bug") == "fix-auth-bug"
    assert slugify("  Hello World  ") == "hello-world"
    assert slugify("add-feature_v2") == "add-feature-v2"
    assert slugify("CamelCase") == "camelcase"
    assert slugify("a!!b@@c") == "a-b-c"


def test_generate_short_id() -> None:
    a = generate_short_id()
    b = generate_short_id()
    assert len(a) == 6
    assert a != b


def test_preserve_env_files(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()

    (source / ".env").write_text("SECRET=123")
    (source / ".env.local").write_text("LOCAL=yes")

    copied = preserve_env_files(source, dest)
    assert ".env" in copied
    assert ".env.local" in copied
    assert (dest / ".env").read_text() == "SECRET=123"
    assert (dest / ".env.local").read_text() == "LOCAL=yes"


def test_preserve_env_files_no_files(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()
    copied = preserve_env_files(source, dest)
    assert copied == []


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=repo, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo, capture_output=True,
    )
    (repo / "README.md").write_text("# Test")
    subprocess.run(
        ["git", "add", "."],
        cwd=repo, capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=repo, capture_output=True,
    )
    return repo


@pytest.mark.asyncio
async def test_create_and_remove_worktree(
    git_repo: Path,
) -> None:
    worktree_path, branch = await create_worktree(
        git_repo, "test-feature", "main",
    )
    assert Path(worktree_path).exists()
    assert branch.startswith("luml-agent/")
    assert "test-feature" in branch

    await remove_worktree(git_repo, worktree_path, branch)
    assert not Path(worktree_path).exists()


@pytest.mark.asyncio
async def test_create_worktree_copies_env(
    git_repo: Path,
) -> None:
    (git_repo / ".env").write_text("KEY=val")

    worktree_path, branch = await create_worktree(
        git_repo, "env-test", "main",
    )
    assert (
        (Path(worktree_path) / ".env").read_text() == "KEY=val"
    )

    await remove_worktree(git_repo, worktree_path, branch)


@pytest.mark.asyncio
async def test_remove_worktree_safety_check(
    git_repo: Path,
) -> None:
    with pytest.raises(
        ValueError, match="Cannot remove the main repository",
    ):
        await remove_worktree(
            git_repo, str(git_repo), "main",
        )


@pytest.mark.asyncio
async def test_get_worktree_status(
    git_repo: Path,
) -> None:
    worktree_path, branch = await create_worktree(
        git_repo, "status-test", "main",
    )

    (Path(worktree_path) / "new_file.txt").write_text("hello")
    subprocess.run(
        ["git", "add", "."],
        cwd=worktree_path, capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "add file"],
        cwd=worktree_path,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "t@t.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "t@t.com",
        },
    )

    status = await get_worktree_status(
        git_repo, branch, "main",
    )
    assert status.branch == branch
    assert status.commits_ahead == 1
    assert status.changed_files == 2  # new_file.txt + .gitignore

    await remove_worktree(git_repo, worktree_path, branch)
