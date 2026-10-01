"""The local prisma engine: process management, REST client, scripted runs."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from luml_prisma.demo.scenario import Scenario

from luml_demo.config import DemoConfig, ScenarioSpec
from luml_demo.shell import say, wait_for

RUN_TERMINAL_STATES = {"succeeded", "failed", "canceled", "merged"}


class Engine:
    def __init__(self, config: DemoConfig) -> None:
        self.config = config
        self.pid_file = config.home / "prisma.pid"
        self.log_file = config.logs_dir / "prisma.log"

    def healthy(self) -> bool:
        try:
            response = httpx.get(f"{self.config.prisma_url}/api/health/", timeout=3)
        except httpx.HTTPError:
            return False
        return response.status_code == 200

    def start(self, *, speed: float) -> None:
        if self.healthy():
            raise RuntimeError(
                f"a prisma engine already answers on {self.config.prisma_url}; "
                "stop it first (luml-demo prisma stop) so the demo agents are on its PATH"
            )
        venv_bin = Path(sys.executable).parent
        env = dict(os.environ)
        env["PATH"] = f"{venv_bin}:{env.get('PATH', '')}"
        env["PRISMA_DEMO_SPEED"] = str(speed)
        env["LUML_EXPERIMENTS_DIR"] = str(self.config.experiments_dir)
        env["LUML_PRISMA_CORS_ORIGINS"] = f"{self.config.web_url},http://127.0.0.1:{self.config.web_port}"
        self.config.logs_dir.mkdir(parents=True, exist_ok=True)
        self.config.experiments_dir.mkdir(parents=True, exist_ok=True)
        log = self.log_file.open("ab")
        process = subprocess.Popen(
            [str(venv_bin / "luml-prisma")],
            stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True,
        )
        self.pid_file.write_text(str(process.pid))
        say(f"prisma engine started (pid {process.pid}, speed {speed}, log {self.log_file})")
        wait_for("prisma engine", self.healthy, timeout=60, interval=1)

    def stop(self) -> None:
        if not self.pid_file.exists():
            return
        pid = int(self.pid_file.read_text().strip() or 0)
        self.pid_file.unlink()
        if pid <= 0:
            return
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except ProcessLookupError:
            return
        for _ in range(50):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.2)
        say(f"prisma engine stopped (pid {pid})")


class PrismaClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.Client(base_url=base_url.rstrip("/") + "/api", timeout=60)

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = self._client.request(method, path, **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text[:400]}")
        return response

    def available_agents(self) -> list[str]:
        return [str(agent["id"]) for agent in self._request("GET", "/agents/available").json()]

    def repositories(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/repositories").json())

    def create_repository(self, name: str, path: Path) -> dict[str, Any]:
        return dict(self._request("POST", "/repositories", json={"name": name, "path": str(path)}).json())

    def ensure_repository(self, name: str, path: Path) -> str:
        for repository in self.repositories():
            if Path(repository["path"]).resolve() == path.resolve():
                return str(repository["id"])
        return str(self.create_repository(name, path)["id"])

    def delete_repository(self, repository_id: str) -> None:
        self._request("DELETE", f"/repositories/{repository_id}")

    def delete_run(self, run_id: str) -> None:
        self._request("DELETE", f"/runs/{run_id}")

    def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return dict(self._request("POST", "/runs", json=payload).json())

    def start_run(self, run_id: str) -> None:
        self._request("POST", f"/runs/{run_id}/start")

    def run(self, run_id: str) -> dict[str, Any]:
        return dict(self._request("GET", f"/runs/{run_id}").json())

    def graph(self, run_id: str) -> dict[str, Any]:
        return dict(self._request("GET", f"/runs/{run_id}/graph").json())


def run_payload(scenario: Scenario, spec: ScenarioSpec, repository_id: str, name: str) -> dict[str, Any]:
    return {
        "repository_id": repository_id,
        "name": name,
        "objective": scenario.objective.strip(),
        "base_branch": "main",
        "agent_id": scenario.agent_id,
        "run_command": scenario.run_command,
        "max_depth": 2,
        "max_children_per_fork": spec.max_children,
        "max_debug_retries": 2,
        "max_concurrency": 1,
        "auto_mode": True,
        "auto_terminate_timeout": 30,
        "primary_metric": "metric",
    }


def run_to_completion(client: PrismaClient, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    run = client.create_run(payload)
    run_id = str(run["id"])
    client.start_run(run_id)
    say(f"prisma run {payload['name']} started ({run_id})")
    seen: set[str] = set()

    def finished() -> bool:
        current = client.run(run_id)
        for node in client.graph(run_id)["nodes"]:
            key = f"{node['id']}:{node['status']}"
            if key not in seen:
                seen.add(key)
                say(f"  node {node['node_type']:<9} {node['status']:<10} depth={node.get('depth')}")
        return str(current["status"]) in RUN_TERMINAL_STATES

    wait_for(f"prisma run {payload['name']}", finished, timeout=timeout, interval=5)
    final = client.run(run_id)
    if str(final["status"]) != "succeeded":
        raise RuntimeError(f"prisma run {run_id} ended as {final['status']}")
    return final


@dataclass(frozen=True)
class RunArtifact:
    node_id: str
    variant: str
    worktree: Path
    artifact_path: Path
    metrics: dict[str, float]
    experiment_ids: list[str]
    winner: bool


def _variant_of(worktree: Path) -> str:
    state_file = worktree / ".prisma" / "demo-state.json"
    if not state_file.exists():
        return worktree.name
    return str(json.loads(state_file.read_text()).get("variant") or worktree.name)


def collect_artifacts(client: PrismaClient, run_id: str) -> list[RunArtifact]:
    """Every successful run node's packaged model, oldest first, winner flagged."""
    run = client.run(run_id)
    best = str(run.get("best_node_id") or "")
    nodes = client.graph(run_id)["nodes"]
    artifacts: list[RunArtifact] = []
    for node in sorted(nodes, key=lambda n: str(n.get("created_at", ""))):
        if node["node_type"] != "run" or node["status"] != "succeeded":
            continue
        worktree = Path(node.get("worktree_path") or "")
        artifact = worktree / ".prisma" / "artifact.luml"
        if not artifact.exists():
            say(f"  run node {node['id']} has no artifact at {artifact}; skipping")
            continue
        # The run node keeps what result.json reported under result["artifacts"].
        result = node.get("result") or {}
        reported = {**result, **(result.get("artifacts") or {})}
        experiment_ids = reported.get("experiment_ids") or (
            [reported["experiment_id"]] if reported.get("experiment_id") else []
        )
        artifacts.append(RunArtifact(
            node_id=str(node["id"]),
            variant=_variant_of(worktree),
            worktree=worktree,
            artifact_path=artifact,
            metrics={k: float(v) for k, v in (reported.get("metrics") or {}).items()},
            experiment_ids=[str(e) for e in experiment_ids],
            winner=str(node["id"]) == best,
        ))
    return artifacts
