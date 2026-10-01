import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from luml_demo import platform, prisma_engine


def _mock_platform(requests: list[tuple[str, str, Any]]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        requests.append((request.method, request.url.path, body))
        if request.url.path == "/v1/auth/signin":
            return httpx.Response(
                200, json={"detail": "ok", "user_id": "u1"},
                headers={"set-cookie": "access_token=jwt-123; HttpOnly; Secure; Path=/"},
            )
        if request.url.path == "/v1/users/me/api-keys":
            assert request.headers["authorization"] == "Bearer jwt-123"
            return httpx.Response(200, json={"key": "dfs_abc"})
        if request.url.path == "/v1/auth/api-keys/validate":
            return httpx.Response(204 if request.headers["authorization"] == "Bearer dfs_abc" else 401)
        if request.url.path.endswith("/satellites") and request.method == "POST":
            return httpx.Response(200, json={"satellite": {"id": "s1", "name": (body or {})["name"]},
                                             "api_key": "dfssat_tok"})
        if request.url.path.endswith("/deployments") and request.method == "POST":
            return httpx.Response(200, json={"id": "d1", **(body or {}), "status": "pending"})
        return httpx.Response(404, json={"detail": "nope"})

    return httpx.MockTransport(handler)


def test_platform_client_signin_api_key_and_creates() -> None:
    seen: list[tuple[str, str, Any]] = []
    transport = _mock_platform(seen)
    client = platform.PlatformClient("http://platform")
    client._client = httpx.Client(base_url="http://platform/v1", transport=transport)
    assert client.signin("a@b.c", "pw") == "jwt-123"
    assert client.user_id == "u1"
    assert client.create_api_key() == "dfs_abc"
    assert client.api_key_valid("dfs_abc")
    assert not client.api_key_valid("dfs_wrong")
    created = client.create_satellite("o", "r", "prod-eu-west-1", "desc")
    assert created["api_key"] == "dfssat_tok"
    deployment = client.create_deployment("o", "r", {"name": "churn-scorer", "artifact_id": "a"})
    assert deployment["id"] == "d1"
    assert seen[-1] == ("POST", "/v1/organizations/o/orbits/r/deployments",
                        {"name": "churn-scorer", "artifact_id": "a"})


def test_platform_client_raises_on_errors() -> None:
    client = platform.PlatformClient("http://platform", token="x")
    client._client = httpx.Client(base_url="http://platform/v1", transport=_mock_platform([]))
    with pytest.raises(RuntimeError, match="404"):
        client.organizations()


def _mock_prisma(graph_nodes: list[dict[str, Any]], best: str) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/runs/r1":
            return httpx.Response(200, json={"id": "r1", "status": "succeeded", "best_node_id": best})
        if request.url.path == "/api/runs/r1/graph":
            return httpx.Response(200, json={"nodes": graph_nodes, "edges": []})
        if request.url.path == "/api/repositories" and request.method == "GET":
            return httpx.Response(200, json=[{"id": "repo1", "name": "x", "path": "/tmp/x"}])
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_collect_artifacts_orders_runs_and_flags_winner(tmp_path: Path) -> None:
    worktrees = {}
    for variant in ("baseline", "gradient-boosting"):
        wt = tmp_path / variant
        (wt / ".prisma").mkdir(parents=True)
        (wt / ".prisma" / "artifact.luml").write_bytes(b"tar")
        (wt / ".prisma" / "demo-state.json").write_text(json.dumps({"variant": variant}))
        worktrees[variant] = wt
    missing = tmp_path / "failed"
    (missing / ".prisma").mkdir(parents=True)
    nodes = [
        {"id": "n2", "node_type": "run", "status": "succeeded", "created_at": "2026-10-01T10:05",
         "worktree_path": str(worktrees["gradient-boosting"]),
         "result": {"success": True, "artifacts": {"metrics": {"metric": 0.87, "roc_auc": 0.87},
                                                   "experiment_ids": ["e2"], "exit_code": 0}}},
        {"id": "n1", "node_type": "run", "status": "succeeded", "created_at": "2026-10-01T10:00",
         "worktree_path": str(worktrees["baseline"]),
         "result": {"metrics": {"metric": 0.83}, "experiment_ids": ["e1"]}},
        {"id": "n3", "node_type": "run", "status": "failed", "created_at": "2026-10-01T10:07",
         "worktree_path": str(missing), "result": {}},
        {"id": "n4", "node_type": "run", "status": "succeeded", "created_at": "2026-10-01T10:08",
         "worktree_path": str(missing), "result": {"metrics": {"metric": 0.5}}},
        {"id": "n0", "node_type": "implement", "status": "succeeded", "created_at": "2026-10-01T09:59",
         "worktree_path": str(worktrees["baseline"]), "result": {}},
    ]
    client = prisma_engine.PrismaClient("http://engine")
    client._client = httpx.Client(base_url="http://engine/api", transport=_mock_prisma(nodes, "n2"))
    artifacts = prisma_engine.collect_artifacts(client, "r1")
    assert [a.variant for a in artifacts] == ["baseline", "gradient-boosting"]
    assert [a.winner for a in artifacts] == [False, True]
    assert artifacts[0].experiment_ids == ["e1"]
    assert artifacts[1].experiment_ids == ["e2"]
    assert artifacts[1].metrics["roc_auc"] == 0.87


def test_ensure_repository_matches_existing_path() -> None:
    client = prisma_engine.PrismaClient("http://engine")
    client._client = httpx.Client(base_url="http://engine/api", transport=_mock_prisma([], ""))
    assert client.ensure_repository("x", Path("/tmp/x")) == "repo1"


def test_run_payload_uses_scenario_settings() -> None:
    from luml_prisma.demo.scenario import load_scenario, resolve_scenario_dir

    from luml_demo.config import SCENARIOS

    scenario = load_scenario(resolve_scenario_dir("churn"))
    spec = next(s for s in SCENARIOS if s.name == "churn")
    payload = prisma_engine.run_payload(scenario, spec, "repo1", "demo run")
    assert payload["agent_id"] == "demo-churn"
    assert payload["run_command"] == "uv run main.py"
    assert payload["max_children_per_fork"] == 3
    assert payload["auto_mode"] is True
    assert "roc_auc" in payload["objective"]
    assert "luml_collection_id" not in payload
    with_registry = prisma_engine.run_payload(
        scenario, spec, "repo1", "demo run",
        registry={"collection_id": "c", "organization_id": "o", "orbit_id": "r"},
    )
    assert with_registry["luml_collection_id"] == "c"
    assert with_registry["luml_orbit_id"] == "r"


def test_engine_environment_isolates_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from luml_demo.config import DemoConfig

    monkeypatch.setenv("LUML_DEMO_HOME", str(tmp_path))
    env = prisma_engine.engine_environment(DemoConfig())
    assert env["LUML_PRISMA_DATA_DIR"] == str(tmp_path / "prisma")
    assert env["LUML_EXPERIMENTS_DIR"] == str(tmp_path / "experiments")
    assert env["PATH"].split(":")[0].endswith("bin")


def test_post_upload_url_explains_a_claimed_upload() -> None:
    client = prisma_engine.PrismaClient("http://engine")
    client._client = httpx.Client(
        base_url="http://engine/api",
        transport=httpx.MockTransport(lambda request: httpx.Response(409, json={"detail": "claimed"})),
    )
    with pytest.raises(RuntimeError, match="Prisma run page"):
        client.post_upload_url("r1", "u1", "https://bucket/x")


def test_upload_outcome_reads_persisted_events() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/runs/r1/events"
        return httpx.Response(200, json=[
            {"seq": 1, "type": "node_updated", "data": {}},
            {"seq": 2, "type": "upload_failed", "data": {"upload_id": "u9"}},
            {"seq": 3, "type": "upload_completed", "data": {"upload_id": "u1"}},
        ])

    client = prisma_engine.PrismaClient("http://engine")
    client._client = httpx.Client(base_url="http://engine/api", transport=httpx.MockTransport(handler))
    assert client.upload_outcome("r1", "u1") == "completed"
    assert client.upload_outcome("r1", "u9") == "failed"
    assert client.upload_outcome("r1", "u5") is None
