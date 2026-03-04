from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from luml_agent.config import AppConfig
from luml_agent.handlers.node import NodeHandler
from luml_agent.handlers.repository import RepositoryHandler
from luml_agent.handlers.run import RunHandler
from luml_agent.handlers.task import TaskHandler
from luml_agent.models import Database
from luml_agent.orchestrator.engine import OrchestratorEngine
from luml_agent.orchestrator.registry import register_all_handlers
from luml_agent.pty_manager import PtyManager
from luml_agent.server import app


@pytest.fixture
def db() -> Database:
    return Database()


@pytest.fixture
async def client(
    tmp_path: Path,
) -> AsyncGenerator[AsyncClient, None]:
    db = Database()
    pty = PtyManager()
    config = AppConfig(data_dir=tmp_path, db_path=tmp_path / "test.db")
    registry = register_all_handlers()
    engine = OrchestratorEngine(db=db, pty=pty, registry=registry)

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    repository = db.add_repository("test", str(repo))
    app.state._test_repository_id = repository.id

    app.state.config = config
    app.state.db = db
    app.state.pty = pty
    app.state.engine = engine
    app.state.repository_handler = RepositoryHandler(
        repository_repo=db.repositories,
        task_repo=db.tasks,
        pty=pty,
    )
    app.state.task_handler = TaskHandler(
        task_repo=db.tasks,
        repository_repo=db.repositories,
        pty=pty,
        config=config,
    )
    app.state.run_handler = RunHandler(
        run_repo=db.runs,
        node_repo=db.nodes,
        repository_repo=db.repositories,
        engine=engine,
    )
    app.state.node_handler = NodeHandler(
        node_repo=db.nodes,
        pty=pty,
        engine=engine,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test",
    ) as c:
        yield c

    pty.shutdown()


# -- Repository-level tests --


def test_task_position_default_none(db: Database) -> None:
    repo = db.add_repository("proj", "/tmp/p", "main")
    task = db.add_task(repo.id, "t", "b", "/wt", "claude")
    assert task.position is None


def test_task_update_positions(db: Database) -> None:
    repo = db.add_repository("proj", "/tmp/p", "main")
    t1 = db.add_task(repo.id, "t1", "b1", "/wt1", "claude")
    t2 = db.add_task(repo.id, "t2", "b2", "/wt2", "claude")
    t3 = db.add_task(repo.id, "t3", "b3", "/wt3", "claude")

    db.tasks.update_positions([
        (t3.id, 0), (t1.id, 1), (t2.id, 2),
    ])

    tasks = db.list_tasks(repo.id)
    names = [t.name for t in tasks]
    assert names == ["t3", "t1", "t2"]


def test_task_list_order_positioned_before_unpositioned(
    db: Database,
) -> None:
    repo = db.add_repository("proj", "/tmp/p", "main")
    db.add_task(repo.id, "unpositioned", "b1", "/wt1", "claude")
    t2 = db.add_task(repo.id, "positioned", "b2", "/wt2", "claude")

    db.tasks.update_positions([(t2.id, 0)])

    tasks = db.list_tasks(repo.id)
    assert tasks[0].name == "positioned"
    assert tasks[1].name == "unpositioned"


def test_run_position_default_none(db: Database) -> None:
    repo = db.add_repository("proj", "/tmp/p", "main")
    run = db.add_run(repo.id, "r", "obj")
    assert run.position is None


def test_run_update_positions(db: Database) -> None:
    repo = db.add_repository("proj", "/tmp/p", "main")
    r1 = db.add_run(repo.id, "r1", "obj1")
    r2 = db.add_run(repo.id, "r2", "obj2")
    r3 = db.add_run(repo.id, "r3", "obj3")

    db.runs.update_positions([
        (r3.id, 0), (r1.id, 1), (r2.id, 2),
    ])

    runs = db.list_runs(repo.id)
    names = [r.name for r in runs]
    assert names == ["r3", "r1", "r2"]


# -- API endpoint tests --


@pytest.mark.asyncio
async def test_reorder_tasks_endpoint(
    client: AsyncClient,
) -> None:
    db: Database = app.state.db
    repo_id = (await client.get("/api/repositories")).json()[0]["id"]

    t1 = db.add_task(repo_id, "a", "b1", "/wt1", "claude", status="pending")
    t2 = db.add_task(repo_id, "b", "b2", "/wt2", "claude", status="pending")
    t3 = db.add_task(repo_id, "c", "b3", "/wt3", "claude", status="pending")

    resp = await client.patch(
        "/api/tasks/reorder",
        json={"items": [
            {"id": t3.id, "position": 0},
            {"id": t1.id, "position": 1},
            {"id": t2.id, "position": 2},
        ]},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    resp = await client.get("/api/tasks")
    task_names = [t["name"] for t in resp.json()]
    assert task_names == ["c", "a", "b"]


@pytest.mark.asyncio
async def test_reorder_runs_endpoint(
    client: AsyncClient,
) -> None:
    repo_id = (await client.get("/api/repositories")).json()[0]["id"]

    ids = []
    for name in ["r1", "r2", "r3"]:
        resp = await client.post(
            "/api/runs",
            json={
                "repository_id": repo_id,
                "name": name,
                "objective": "",
            },
        )
        assert resp.status_code == 201
        ids.append(resp.json()["id"])

    resp = await client.patch(
        "/api/runs/reorder",
        json={"items": [
            {"id": ids[2], "position": 0},
            {"id": ids[1], "position": 1},
            {"id": ids[0], "position": 2},
        ]},
    )
    assert resp.status_code == 200

    resp = await client.get("/api/runs")
    run_names = [r["name"] for r in resp.json()]
    assert run_names == ["r3", "r2", "r1"]


@pytest.mark.asyncio
async def test_task_position_in_response(
    client: AsyncClient,
) -> None:
    db: Database = app.state.db
    repo_id = (await client.get("/api/repositories")).json()[0]["id"]

    task = db.add_task(repo_id, "t", "b", "/wt", "claude", status="pending")
    resp = await client.get(f"/api/tasks/{task.id}")
    assert resp.json()["position"] is None

    await client.patch(
        "/api/tasks/reorder",
        json={"items": [{"id": task.id, "position": 5}]},
    )

    resp = await client.get(f"/api/tasks/{task.id}")
    assert resp.json()["position"] == 5


@pytest.mark.asyncio
async def test_run_position_in_response(
    client: AsyncClient,
) -> None:
    repo_id = (await client.get("/api/repositories")).json()[0]["id"]
    resp = await client.post(
        "/api/runs",
        json={
            "repository_id": repo_id,
            "name": "r",
            "objective": "",
        },
    )
    run = resp.json()
    assert run["position"] is None

    await client.patch(
        "/api/runs/reorder",
        json={"items": [{"id": run["id"], "position": 3}]},
    )

    resp = await client.get(f"/api/runs/{run['id']}")
    assert resp.json()["position"] == 3
