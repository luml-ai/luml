from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from luml_agent.config import load_config
from luml_agent.handlers.node import NodeHandler
from luml_agent.handlers.repository import RepositoryHandler
from luml_agent.handlers.run import RunHandler
from luml_agent.models import Database
from luml_agent.orchestrator.engine import OrchestratorEngine
from luml_agent.orchestrator.registry import (
    register_all_handlers,
)
from luml_agent.pty_manager import PtyManager
from luml_agent.server import app


@pytest.fixture
async def client(
    tmp_path: Path,
) -> AsyncGenerator[AsyncClient, None]:
    db = Database()
    pty = PtyManager()
    config = load_config()
    registry = register_all_handlers()
    engine = OrchestratorEngine(
        db=db, pty=pty, registry=registry,
    )

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


@pytest.fixture
async def repository_id(client: AsyncClient) -> str:
    resp = await client.get("/api/repositories")
    return resp.json()[0]["id"]


class TestRunEndpoints:
    @pytest.mark.asyncio
    async def test_create_run(
        self, client: AsyncClient, repository_id: str,
    ) -> None:
        resp = await client.post(
            "/api/runs",
            json={
                "repository_id": repository_id,
                "name": "test-run",
                "objective": "do stuff",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "test-run"
        assert data["status"] == "pending"
        assert data["objective"] == "do stuff"

    @pytest.mark.asyncio
    async def test_create_run_repository_not_found(
        self, client: AsyncClient,
    ) -> None:
        resp = await client.post(
            "/api/runs",
            json={
                "repository_id": "nonexistent",
                "name": "r",
                "objective": "",
            },
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_runs(
        self, client: AsyncClient, repository_id: str,
    ) -> None:
        await client.post(
            "/api/runs",
            json={
                "repository_id": repository_id,
                "name": "a",
                "objective": "",
            },
        )
        await client.post(
            "/api/runs",
            json={
                "repository_id": repository_id,
                "name": "b",
                "objective": "",
            },
        )

        resp = await client.get("/api/runs")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    @pytest.mark.asyncio
    async def test_list_runs_by_repository(
        self, client: AsyncClient, repository_id: str,
    ) -> None:
        await client.post(
            "/api/runs",
            json={
                "repository_id": repository_id,
                "name": "a",
                "objective": "",
            },
        )

        resp = await client.get(
            "/api/runs", params={"repository_id": repository_id},
        )
        assert len(resp.json()) == 1

        resp = await client.get(
            "/api/runs", params={"repository_id": "nonexistent"},
        )
        assert len(resp.json()) == 0

    @pytest.mark.asyncio
    async def test_get_run(
        self, client: AsyncClient, repository_id: str,
    ) -> None:
        create_resp = await client.post(
            "/api/runs",
            json={
                "repository_id": repository_id,
                "name": "r",
                "objective": "obj",
            },
        )
        run_id = create_resp.json()["id"]

        resp = await client.get(f"/api/runs/{run_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "r"

    @pytest.mark.asyncio
    async def test_get_run_not_found(
        self, client: AsyncClient,
    ) -> None:
        resp = await client.get("/api/runs/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_start_run(
        self, client: AsyncClient, repository_id: str,
    ) -> None:
        create_resp = await client.post(
            "/api/runs",
            json={
                "repository_id": repository_id,
                "name": "r",
                "objective": "",
            },
        )
        run_id = create_resp.json()["id"]

        resp = await client.post(
            f"/api/runs/{run_id}/start",
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    @pytest.mark.asyncio
    async def test_cancel_run(
        self, client: AsyncClient, repository_id: str,
    ) -> None:
        create_resp = await client.post(
            "/api/runs",
            json={
                "repository_id": repository_id,
                "name": "r",
                "objective": "",
            },
        )
        run_id = create_resp.json()["id"]
        await client.post(f"/api/runs/{run_id}/start")

        resp = await client.post(
            f"/api/runs/{run_id}/cancel",
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "canceled"


class TestGraphEndpoint:
    @pytest.mark.asyncio
    async def test_get_run_graph(
        self, client: AsyncClient, repository_id: str,
    ) -> None:
        create_resp = await client.post(
            "/api/runs",
            json={
                "repository_id": repository_id,
                "name": "r",
                "objective": "",
            },
        )
        run_id = create_resp.json()["id"]

        resp = await client.get(
            f"/api/runs/{run_id}/graph",
        )
        assert resp.status_code == 200
        graph = resp.json()
        assert "nodes" in graph
        assert "edges" in graph
        assert len(graph["nodes"]) == 1
        assert (
            graph["nodes"][0]["node_type"] == "implement"
        )

    @pytest.mark.asyncio
    async def test_get_run_graph_not_found(
        self, client: AsyncClient,
    ) -> None:
        resp = await client.get("/api/runs/nonexistent/graph")
        assert resp.status_code == 404


class TestEventsEndpoint:
    @pytest.mark.asyncio
    async def test_get_events(
        self, client: AsyncClient, repository_id: str,
    ) -> None:
        create_resp = await client.post(
            "/api/runs",
            json={
                "repository_id": repository_id,
                "name": "r",
                "objective": "",
            },
        )
        run_id = create_resp.json()["id"]

        resp = await client.get(
            f"/api/runs/{run_id}/events",
        )
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) >= 2

    @pytest.mark.asyncio
    async def test_get_events_after_seq(
        self, client: AsyncClient, repository_id: str,
    ) -> None:
        create_resp = await client.post(
            "/api/runs",
            json={
                "repository_id": repository_id,
                "name": "r",
                "objective": "",
            },
        )
        run_id = create_resp.json()["id"]

        all_events = (
            await client.get(
                f"/api/runs/{run_id}/events",
            )
        ).json()
        last_seq = all_events[-1]["seq"]

        resp = await client.get(
            f"/api/runs/{run_id}/events",
            params={"after_seq": last_seq},
        )
        assert len(resp.json()) == 0


class TestRestartRun:
    @pytest.mark.asyncio
    async def test_restart_failed_run(
        self, client: AsyncClient, repository_id: str,
    ) -> None:
        create_resp = await client.post(
            "/api/runs",
            json={
                "repository_id": repository_id,
                "name": "r",
                "objective": "do stuff",
            },
        )
        run_id = create_resp.json()["id"]
        await client.post(f"/api/runs/{run_id}/start")
        await client.post(f"/api/runs/{run_id}/cancel")

        resp = await client.post(
            f"/api/runs/{run_id}/restart",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["objective"] == "do stuff"

        graph = (
            await client.get(
                f"/api/runs/{run_id}/graph",
            )
        ).json()
        assert len(graph["nodes"]) == 1
        assert graph["nodes"][0]["status"] == "queued"

    @pytest.mark.asyncio
    async def test_restart_running_run_rejected(
        self, client: AsyncClient, repository_id: str,
    ) -> None:
        create_resp = await client.post(
            "/api/runs",
            json={
                "repository_id": repository_id,
                "name": "r",
                "objective": "",
            },
        )
        run_id = create_resp.json()["id"]
        await client.post(f"/api/runs/{run_id}/start")

        resp = await client.post(
            f"/api/runs/{run_id}/restart",
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_restart_not_found(
        self, client: AsyncClient,
    ) -> None:
        resp = await client.post("/api/runs/nonexistent/restart")
        assert resp.status_code == 404


class TestDeleteRun:
    @pytest.mark.asyncio
    async def test_delete_completed_run(
        self, client: AsyncClient, repository_id: str,
    ) -> None:
        create_resp = await client.post(
            "/api/runs",
            json={
                "repository_id": repository_id,
                "name": "r",
                "objective": "",
            },
        )
        run_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/runs/{run_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        resp = await client.get(f"/api/runs/{run_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_running_run_rejected(
        self, client: AsyncClient, repository_id: str,
    ) -> None:
        create_resp = await client.post(
            "/api/runs",
            json={
                "repository_id": repository_id,
                "name": "r",
                "objective": "",
            },
        )
        run_id = create_resp.json()["id"]
        await client.post(f"/api/runs/{run_id}/start")

        resp = await client.delete(f"/api/runs/{run_id}")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_not_found(
        self, client: AsyncClient,
    ) -> None:
        resp = await client.delete("/api/runs/nonexistent")
        assert resp.status_code == 404


class TestNodeEndpoints:
    @pytest.mark.asyncio
    async def test_node_input_not_found(
        self, client: AsyncClient,
    ) -> None:
        resp = await client.post(
            "/api/nodes/nonexistent/input",
            json={"text": "hello"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_node_action_not_found(
        self, client: AsyncClient,
    ) -> None:
        resp = await client.post(
            "/api/nodes/nonexistent/action",
            json={"action": "cancel"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_node_action_unknown(
        self, client: AsyncClient, repository_id: str,
    ) -> None:
        create_resp = await client.post(
            "/api/runs",
            json={
                "repository_id": repository_id,
                "name": "r",
                "objective": "",
            },
        )
        run_id = create_resp.json()["id"]
        graph = (
            await client.get(
                f"/api/runs/{run_id}/graph",
            )
        ).json()
        node_id = graph["nodes"][0]["id"]

        resp = await client.post(
            f"/api/nodes/{node_id}/action",
            json={"action": "invalid"},
        )
        assert resp.status_code == 400
