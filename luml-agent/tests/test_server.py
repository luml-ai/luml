import asyncio
import shutil
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from luml_agent.config import AppConfig
from luml_agent.handlers.repository import RepositoryHandler
from luml_agent.handlers.task import TaskHandler
from luml_agent.database import Database, TaskStatus
from luml_agent.services.pty_manager import PtyManager
from luml_agent.server import app

needs_git = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available",
)


@pytest.fixture
def tmp_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        data_dir=tmp_path, db_path=tmp_path / "test.db",
    )


@pytest.fixture
def db() -> Database:
    return Database()


@pytest.fixture
def pty() -> PtyManager:
    mgr = PtyManager()
    yield mgr
    mgr.shutdown()


@pytest.fixture
async def client(
    tmp_config: AppConfig,
    db: Database,
    pty: PtyManager,
) -> AsyncGenerator[AsyncClient, None]:
    app.state.config = tmp_config
    app.state.db = db
    app.state.pty = pty
    app.state.repository_handler = RepositoryHandler(
        repository_repo=db.repositories,
        task_repo=db.tasks,
        pty=pty,
    )
    app.state.task_handler = TaskHandler(
        task_repo=db.tasks,
        repository_repo=db.repositories,
        pty=pty,
        config=tmp_config,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test",
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_list_repositories_empty(
    client: AsyncClient,
) -> None:
    resp = await client.get("/api/repositories")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_repository(
    client: AsyncClient, tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    resp = await client.post(
        "/api/repositories",
        json={
            "name": "test",
            "path": str(repo),
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test"
    assert isinstance(data["id"], str)
    assert "base_branch" not in data


@pytest.mark.asyncio
async def test_create_repository_invalid_path(
    client: AsyncClient, tmp_path: Path,
) -> None:
    resp = await client.post(
        "/api/repositories",
        json={
            "name": "bad",
            "path": str(tmp_path / "nonexistent"),
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_repository(
    client: AsyncClient, tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    create_resp = await client.post(
        "/api/repositories",
        json={
            "name": "test",
            "path": str(repo),
        },
    )
    repository_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/repositories/{repository_id}")
    assert resp.status_code == 200
    resp = await client.get("/api/repositories")
    assert resp.json() == []


@pytest.mark.asyncio
async def test_delete_repository_not_found(
    client: AsyncClient,
) -> None:
    resp = await client.delete("/api/repositories/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_tasks_empty(
    client: AsyncClient,
) -> None:
    resp = await client.get("/api/tasks")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_task_not_found(
    client: AsyncClient,
) -> None:
    resp = await client.get("/api/tasks/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_task_status(
    client: AsyncClient, db: Database,
) -> None:
    repo = db.add_repository("p", "/tmp")
    task = db.add_task(
        repository_id=repo.id,
        name="t",
        branch="b",
        worktree_path="/tmp",
        agent_id="claude",
        prompt="",
        status=TaskStatus.RUNNING,
    )
    resp = await client.patch(
        f"/api/tasks/{task.id}/status", json={"status": "succeeded"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "succeeded"


@pytest.mark.asyncio
async def test_update_task_status_invalid(
    client: AsyncClient, db: Database,
) -> None:
    repo = db.add_repository("p", "/tmp")
    task = db.add_task(
        repository_id=repo.id,
        name="t",
        branch="b",
        worktree_path="/tmp",
        agent_id="claude",
        prompt="",
        status=TaskStatus.RUNNING,
    )
    resp = await client.patch(
        f"/api/tasks/{task.id}/status",
        json={"status": "invalid"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_task_base_branch_default(
    db: Database,
) -> None:
    repo = db.add_repository("p", "/tmp")
    task = db.add_task(
        repository_id=repo.id,
        name="t",
        branch="b",
        worktree_path="/tmp",
        agent_id="claude",
        prompt="",
        status=TaskStatus.RUNNING,
    )
    assert task.base_branch == "main"


@pytest.mark.asyncio
async def test_task_base_branch_explicit(
    db: Database,
) -> None:
    repo = db.add_repository("p", "/tmp")
    task = db.add_task(
        repository_id=repo.id,
        name="t",
        branch="b",
        worktree_path="/tmp",
        agent_id="claude",
        prompt="",
        status=TaskStatus.RUNNING,
        base_branch="develop",
    )
    assert task.base_branch == "develop"


@pytest.mark.asyncio
async def test_task_out_includes_base_branch(
    client: AsyncClient, db: Database,
) -> None:
    repo = db.add_repository("p", "/tmp")
    task = db.add_task(
        repository_id=repo.id,
        name="t",
        branch="b",
        worktree_path="/tmp",
        agent_id="claude",
        prompt="",
        status=TaskStatus.RUNNING,
        base_branch="develop",
    )
    resp = await client.get(f"/api/tasks/{task.id}")
    assert resp.status_code == 200
    assert resp.json()["base_branch"] == "develop"


@pytest.mark.asyncio
async def test_list_agents(client: AsyncClient) -> None:
    resp = await client.get("/api/agents")
    assert resp.status_code == 200
    agents = resp.json()
    assert len(agents) >= 3
    ids = {a["id"] for a in agents}
    assert "claude" in ids


@pytest.mark.asyncio
async def test_list_available_agents(
    client: AsyncClient,
) -> None:
    resp = await client.get("/api/agents/available")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_orphaned_tasks_marked_error() -> None:
    db = Database()
    repo = db.add_repository("p", "/tmp")
    task = db.add_task(
        repository_id=repo.id,
        name="orphan",
        branch="b",
        worktree_path="/tmp",
        agent_id="claude",
        prompt="",
        status=TaskStatus.RUNNING,
    )
    task_before = db.get_task(task.id)
    assert task_before.status == TaskStatus.RUNNING

    for t in db.list_tasks():
        if t.status == TaskStatus.RUNNING:
            db.update_task_status(t.id, TaskStatus.FAILED)

    task_after = db.get_task(task.id)
    assert task_after.status == TaskStatus.FAILED


@pytest.mark.asyncio
async def test_open_terminal_not_found(
    client: AsyncClient,
) -> None:
    resp = await client.post("/api/tasks/nonexistent/terminal")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_open_terminal_shell_mode(
    client: AsyncClient,
    db: Database,
    pty: PtyManager,
    tmp_path: Path,
) -> None:
    repo = db.add_repository("p", "/tmp")
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    task = db.add_task(
        repository_id=repo.id,
        name="t",
        branch="b",
        worktree_path=str(worktree),
        agent_id="claude",
        prompt="",
        status=TaskStatus.SUCCEEDED,
    )
    resp = await client.post(
        f"/api/tasks/{task.id}/terminal", params={"mode": "shell"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_alive"] is True
    assert data["session_id"] is not None
    assert data["status"] == "succeeded"
    session_id = data["session_id"]
    assert pty.get_session_type(session_id) == "shell"
    pty.terminate(session_id)


@pytest.mark.asyncio
async def test_open_terminal_returns_existing(
    client: AsyncClient,
    db: Database,
    pty: PtyManager,
    tmp_path: Path,
) -> None:
    repo = db.add_repository("p", "/tmp")
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    task = db.add_task(
        repository_id=repo.id,
        name="t",
        branch="b",
        worktree_path=str(worktree),
        agent_id="claude",
        prompt="",
        status=TaskStatus.SUCCEEDED,
    )
    session = pty.spawn(
        task.id,
        ["sleep", "60"],
        cwd=str(worktree),
        session_type="shell",
    )
    resp = await client.post(
        f"/api/tasks/{task.id}/terminal", params={"mode": "shell"},
    )
    assert resp.status_code == 200
    assert resp.json()["session_id"] == session.session_id
    pty.terminate(session.session_id)


@pytest.mark.asyncio
async def test_open_terminal_missing_worktree(
    client: AsyncClient, db: Database,
) -> None:
    repo = db.add_repository("p", "/tmp")
    task = db.add_task(
        repository_id=repo.id,
        name="t",
        branch="b",
        worktree_path="/nonexistent/path",
        agent_id="claude",
        prompt="",
        status=TaskStatus.SUCCEEDED,
    )
    resp = await client.post(f"/api/tasks/{task.id}/terminal")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_open_terminal_agent_mode(
    client: AsyncClient,
    db: Database,
    pty: PtyManager,
    tmp_path: Path,
) -> None:
    repo = db.add_repository("p", "/tmp")
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    task = db.add_task(
        repository_id=repo.id,
        name="t",
        branch="b",
        worktree_path=str(worktree),
        agent_id="claude",
        prompt="do stuff",
        status=TaskStatus.SUCCEEDED,
    )
    resp = await client.post(
        f"/api/tasks/{task.id}/terminal",
        params={"mode": "agent"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_alive"] is True
    assert data["status"] == "running"
    session_id = data["session_id"]
    assert pty.get_session_type(session_id) == "agent"
    pty.terminate(session_id)


@pytest.mark.asyncio
async def test_open_terminal_default_is_agent(
    client: AsyncClient,
    db: Database,
    pty: PtyManager,
    tmp_path: Path,
) -> None:
    repo = db.add_repository("p", "/tmp")
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    task = db.add_task(
        repository_id=repo.id,
        name="t",
        branch="b",
        worktree_path=str(worktree),
        agent_id="claude",
        prompt="",
        status=TaskStatus.SUCCEEDED,
    )
    resp = await client.post(f"/api/tasks/{task.id}/terminal")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    assert pty.get_session_type(data["session_id"]) == "agent"
    pty.terminate(data["session_id"])


@pytest.mark.asyncio
async def test_open_terminal_data_flows(
    client: AsyncClient,
    db: Database,
    pty: PtyManager,
    tmp_path: Path,
) -> None:
    repo = db.add_repository("p", "/tmp")
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    task = db.add_task(
        repository_id=repo.id,
        name="t",
        branch="b",
        worktree_path=str(worktree),
        agent_id="claude",
        prompt="",
        status=TaskStatus.SUCCEEDED,
    )
    resp = await client.post(
        f"/api/tasks/{task.id}/terminal", params={"mode": "shell"},
    )
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    await asyncio.sleep(0.3)
    pty.write(session_id, b"echo __DATA_FLOWS__\n")
    await asyncio.sleep(0.5)

    scrollback = pty.get_scrollback(session_id)
    assert b"__DATA_FLOWS__" in scrollback
    pty.terminate(session_id)


@pytest.mark.asyncio
async def test_browse_default(
    client: AsyncClient,
) -> None:
    resp = await client.get("/api/browse")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current"] == str(Path.home())
    assert isinstance(data["dirs"], list)
    assert "parent" in data
    assert "is_git" in data


@pytest.mark.asyncio
async def test_browse_specific_path(
    client: AsyncClient, tmp_path: Path,
) -> None:
    sub = tmp_path / "subdir"
    sub.mkdir()
    resp = await client.get(
        "/api/browse", params={"path": str(tmp_path)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["current"] == str(tmp_path)
    names = [d["name"] for d in data["dirs"]]
    assert "subdir" in names


@pytest.mark.asyncio
async def test_browse_git_detection(
    client: AsyncClient, tmp_path: Path,
) -> None:
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / ".git").mkdir()
    plain = tmp_path / "plain"
    plain.mkdir()
    resp = await client.get(
        "/api/browse", params={"path": str(tmp_path)},
    )
    data = resp.json()
    entries = {d["name"]: d for d in data["dirs"]}
    assert entries["myrepo"]["is_git"] is True
    assert entries["plain"]["is_git"] is False


@pytest.mark.asyncio
async def test_browse_nonexistent(
    client: AsyncClient, tmp_path: Path,
) -> None:
    resp = await client.get(
        "/api/browse",
        params={"path": str(tmp_path / "nope")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_browse_hidden_dirs_filtered(
    client: AsyncClient, tmp_path: Path,
) -> None:
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "visible").mkdir()
    resp = await client.get(
        "/api/browse", params={"path": str(tmp_path)},
    )
    data = resp.json()
    names = [d["name"] for d in data["dirs"]]
    assert "visible" in names
    assert ".hidden" not in names


@pytest.mark.asyncio
async def test_browse_parent_at_root(
    client: AsyncClient,
) -> None:
    resp = await client.get(
        "/api/browse", params={"path": "/"},
    )
    data = resp.json()
    assert data["parent"] is None


@pytest.mark.asyncio
async def test_browse_current_dir_git(
    client: AsyncClient, tmp_path: Path,
) -> None:
    (tmp_path / ".git").mkdir()
    resp = await client.get(
        "/api/browse", params={"path": str(tmp_path)},
    )
    data = resp.json()
    assert data["is_git"] is True


@needs_git
@pytest.mark.asyncio
async def test_list_branches(
    client: AsyncClient, tmp_path: Path,
) -> None:
    repo = tmp_path / "gitrepo"
    repo.mkdir()
    proc = await asyncio.create_subprocess_exec(
        "git", "init", "-b", "main",
        cwd=str(repo),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    proc = await asyncio.create_subprocess_exec(
        "git", "commit", "--allow-empty", "-m", "init",
        cwd=str(repo),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    proc = await asyncio.create_subprocess_exec(
        "git", "branch", "develop",
        cwd=str(repo),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    resp = await client.get(
        "/api/browse/branches",
        params={"path": str(repo)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "branches" in data
    assert "main" in data["branches"]
    assert "develop" in data["branches"]
    assert data["branches"] == sorted(data["branches"])


@pytest.mark.asyncio
async def test_list_branches_not_git(
    client: AsyncClient, tmp_path: Path,
) -> None:
    resp = await client.get(
        "/api/browse/branches",
        params={"path": str(tmp_path)},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_branches_nonexistent(
    client: AsyncClient, tmp_path: Path,
) -> None:
    resp = await client.get(
        "/api/browse/branches",
        params={"path": str(tmp_path / "nope")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_task_dict_includes_session_id(
    client: AsyncClient,
    db: Database,
    pty: PtyManager,
) -> None:
    repo = db.add_repository("p", "/tmp")
    task = db.add_task(
        repository_id=repo.id,
        name="t",
        branch="b",
        worktree_path="/tmp",
        agent_id="claude",
        prompt="",
        status=TaskStatus.RUNNING,
    )
    session = pty.spawn(task.id, ["sleep", "60"], cwd="/tmp")
    resp = await client.get(f"/api/tasks/{task.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session.session_id
    assert data["is_alive"] is True
    pty.terminate(session.session_id)


@pytest.mark.asyncio
async def test_cors_allows_localhost_any_port(
    client: AsyncClient,
) -> None:
    resp = await client.options(
        "/api/health/",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


@pytest.mark.asyncio
async def test_cors_allows_luml_subdomain(
    client: AsyncClient,
) -> None:
    resp = await client.options(
        "/api/health/",
        headers={
            "Origin": "https://app.luml.ai",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-allow-origin") == "https://app.luml.ai"


@pytest.mark.asyncio
async def test_cors_rejects_unknown_origin(
    client: AsyncClient,
) -> None:
    resp = await client.options(
        "/api/health/",
        headers={
            "Origin": "https://evil.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in resp.headers
