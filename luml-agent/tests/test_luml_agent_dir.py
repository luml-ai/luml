import os
import subprocess
from pathlib import Path

import pytest

from luml_agent.services.orchestrator.utils import (
    ensure_global_luml_dir,
    ensure_luml_agent_dir,
)
from luml_agent.services.worktree import _OBSOLETE_ENTRIES, _setup_gitignore


def test_ensure_luml_agent_dir_creates_dir(tmp_path: Path) -> None:
    result = ensure_luml_agent_dir(str(tmp_path))
    assert result == tmp_path / ".luml-agent"
    assert result.is_dir()


def test_ensure_luml_agent_dir_idempotent(tmp_path: Path) -> None:
    first = ensure_luml_agent_dir(str(tmp_path))
    (first / "some_file.txt").write_text("keep me")
    second = ensure_luml_agent_dir(str(tmp_path))
    assert first == second
    assert (second / "some_file.txt").read_text() == "keep me"


def test_ensure_global_luml_dir_creates_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = ensure_global_luml_dir()
    assert result == tmp_path / ".luml-agent"
    assert (tmp_path / ".luml-agent" / "experiments").is_dir()


def test_ensure_global_luml_dir_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    ensure_global_luml_dir()
    (tmp_path / ".luml-agent" / "uploads.db").write_text("")
    ensure_global_luml_dir()
    assert (tmp_path / ".luml-agent" / "uploads.db").exists()


def test_setup_gitignore_creates_new(tmp_path: Path) -> None:
    _setup_gitignore(tmp_path)
    gitignore = tmp_path / ".gitignore"
    assert gitignore.exists()
    assert ".luml-agent/" in gitignore.read_text()


def test_setup_gitignore_appends_to_existing(tmp_path: Path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("node_modules/\n.env\n")
    _setup_gitignore(tmp_path)
    content = gitignore.read_text()
    assert "node_modules/" in content
    assert ".env" in content
    assert ".luml-agent/" in content


def test_setup_gitignore_idempotent(tmp_path: Path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("node_modules/\n")
    _setup_gitignore(tmp_path)
    _setup_gitignore(tmp_path)
    content = gitignore.read_text()
    assert content.count(".luml-agent/") == 1


def test_setup_gitignore_removes_obsolete_entries(tmp_path: Path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(
        "node_modules/\n.luml-fork.json\n.proposals/\nresult.json\n.env\n",
    )
    _setup_gitignore(tmp_path)
    content = gitignore.read_text()
    for entry in _OBSOLETE_ENTRIES:
        assert entry not in content.splitlines()
    assert ".luml-agent/" in content
    assert "node_modules/" in content
    assert ".env" in content


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
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=repo, capture_output=True,
    )
    return repo


@pytest.mark.asyncio
async def test_create_worktree_sets_up_gitignore(git_repo: Path) -> None:
    from luml_agent.services.worktree import create_worktree, remove_worktree

    worktree_path, branch = await create_worktree(
        git_repo, "gitignore-test", "main",
    )
    gitignore = Path(worktree_path) / ".gitignore"
    assert gitignore.exists()
    assert ".luml-agent/" in gitignore.read_text()

    await remove_worktree(git_repo, worktree_path, branch)


@pytest.mark.asyncio
async def test_create_worktree_removes_old_gitignore_entries(
    git_repo: Path,
) -> None:
    from luml_agent.services.worktree import create_worktree, remove_worktree

    (git_repo / ".gitignore").write_text(
        ".proposals/\n.luml-fork.json\nresult.json\n",
    )
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "add gitignore"],
        cwd=git_repo,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "t@t.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "t@t.com",
        },
    )

    worktree_path, branch = await create_worktree(
        git_repo, "old-entries-test", "main",
    )
    content = (Path(worktree_path) / ".gitignore").read_text()
    for entry in _OBSOLETE_ENTRIES:
        assert entry not in content.splitlines()
    assert ".luml-agent/" in content

    await remove_worktree(git_repo, worktree_path, branch)
