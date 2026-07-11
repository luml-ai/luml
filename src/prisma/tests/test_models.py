import pytest

from luml_prisma.database import Database, TaskStatus
from luml_prisma.infra.exceptions import InvalidOperationError


@pytest.fixture
def db() -> Database:
    return Database()


def test_add_and_get_repository(db: Database) -> None:
    repo = db.add_repository("test-proj", "/tmp/test")
    assert repo.id is not None
    assert repo.name == "test-proj"
    fetched = db.get_repository(repo.id)
    assert fetched is not None
    assert fetched.name == "test-proj"


def test_list_repositories(db: Database) -> None:
    db.add_repository("alpha", "/tmp/a")
    db.add_repository("beta", "/tmp/b")
    repos = db.list_repositories()
    assert len(repos) == 2
    names = [p.name for p in repos]
    assert "alpha" in names
    assert "beta" in names


def test_remove_repository_cascades_tasks(db: Database) -> None:
    repo = db.add_repository("proj", "/tmp/p")
    db.add_task(
        repository_id=repo.id,
        name="task1",
        branch="agent/task1",
        worktree_path="/tmp/wt",
        agent_id="claude",
    )
    db.remove_repository(repo.id)
    assert db.get_repository(repo.id) is None
    assert db.list_tasks(repo.id) == []


def test_add_and_get_task(db: Database) -> None:
    repo = db.add_repository("proj", "/tmp/p")
    task = db.add_task(
        repository_id=repo.id,
        name="fix-bug",
        branch="agent/fix-bug-abc",
        worktree_path="/tmp/wt/fix-bug",
        agent_id="claude",
        prompt="Fix the auth bug",
        tmux_session="wa-fix-bug-abc",
    )
    assert task.id is not None
    assert task.status == TaskStatus.RUNNING
    fetched = db.get_task(task.id)
    assert fetched is not None
    assert fetched.name == "fix-bug"
    assert fetched.prompt == "Fix the auth bug"


def test_list_tasks_by_repository(db: Database) -> None:
    p1 = db.add_repository("p1", "/tmp/p1")
    p2 = db.add_repository("p2", "/tmp/p2")
    db.add_task(p1.id, "t1", "b1", "/wt1", "claude")
    db.add_task(p1.id, "t2", "b2", "/wt2", "codex")
    db.add_task(p2.id, "t3", "b3", "/wt3", "claude")

    assert len(db.list_tasks(p1.id)) == 2
    assert len(db.list_tasks(p2.id)) == 1
    assert len(db.list_tasks()) == 3


def test_update_task_status(db: Database) -> None:
    repo = db.add_repository("proj", "/tmp/p")
    task = db.add_task(repo.id, "t", "b", "/wt", "claude")
    db.update_task_status(task.id, TaskStatus.SUCCEEDED)
    updated = db.get_task(task.id)
    assert updated.status == TaskStatus.SUCCEEDED


def test_update_task_tmux_session(db: Database) -> None:
    repo = db.add_repository("proj", "/tmp/p")
    task = db.add_task(repo.id, "t", "b", "/wt", "claude")
    db.update_task_tmux_session(task.id, "new-session")
    updated = db.get_task(task.id)
    assert updated.tmux_session == "new-session"


def test_remove_task(db: Database) -> None:
    repo = db.add_repository("proj", "/tmp/p")
    task = db.add_task(repo.id, "t", "b", "/wt", "claude")
    db.remove_task(task.id)
    assert db.get_task(task.id) is None


def test_get_nonexistent_repository(db: Database) -> None:
    assert db.get_repository("nonexistent") is None


def test_get_nonexistent_task(db: Database) -> None:
    assert db.get_task("nonexistent") is None


def test_repository_unique_path(db: Database) -> None:
    db.add_repository("p1", "/tmp/unique")
    with pytest.raises(InvalidOperationError):
        db.add_repository("p2", "/tmp/unique")


def test_task_timestamps_set(db: Database) -> None:
    repo = db.add_repository("proj", "/tmp/p")
    task = db.add_task(repo.id, "t", "b", "/wt", "claude")
    assert task.created_at
    assert task.updated_at
