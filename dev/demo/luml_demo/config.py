"""Demo environment configuration: ports, paths, satellites and scenarios."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

ENV_PREFIX = "LUML_DEMO_"
REPO_ROOT = Path(__file__).resolve().parents[3]


def _env(name: str, default: str) -> str:
    return os.environ.get(ENV_PREFIX + name, default)


def _env_int(name: str, default: int) -> int:
    return int(_env(name, str(default)))


@dataclass(frozen=True)
class SatelliteSpec:
    slug: str
    name: str
    description: str
    port: int
    greptime_port: int
    otlp_port: int


@dataclass(frozen=True)
class ScenarioSpec:
    """How one prisma scenario maps onto the registry and the satellites."""

    name: str
    model_name: str
    track_name: str
    deploy_winner_to: str
    deploy_runner_up_to: str | None
    primary_metric: str
    max_children: int = 3
    dataset_file: str | None = None


SCENARIOS: tuple[ScenarioSpec, ...] = (
    ScenarioSpec(
        name="churn",
        model_name="churn-scorer",
        track_name="churn-scorer",
        deploy_winner_to="prod",
        deploy_runner_up_to="staging",
        primary_metric="roc_auc",
        dataset_file="data/customers.csv",
    ),
    ScenarioSpec(
        name="autorag",
        model_name="support-assistant",
        track_name="support-assistant",
        deploy_winner_to="prod",
        deploy_runner_up_to=None,
        primary_metric="recall_at_3",
    ),
)

TRACK_STAGES = ("development", "staging", "production")


@dataclass(frozen=True)
class DemoConfig:
    repo_root: Path = REPO_ROOT
    home: Path = field(default_factory=lambda: Path(_env("HOME", "~/.luml/demo")).expanduser())
    compose_project: str = field(default_factory=lambda: _env("COMPOSE_PROJECT", "luml-demo"))
    api_port: int = field(default_factory=lambda: _env_int("API_PORT", 8000))
    web_port: int = field(default_factory=lambda: _env_int("WEB_PORT", 5173))
    pg_port: int = field(default_factory=lambda: _env_int("PG_PORT", 5432))
    minio_port: int = field(default_factory=lambda: _env_int("MINIO_PORT", 9000))
    minio_console_port: int = field(default_factory=lambda: _env_int("MINIO_CONSOLE_PORT", 9001))
    prisma_port: int = 8420
    lumlflow_port: int = field(default_factory=lambda: _env_int("LUMLFLOW_PORT", 5000))
    docker_host_ip: str = field(default_factory=lambda: _env("DOCKER_HOST_IP", ""))
    admin_email: str = "admin@example.com"
    admin_password: str = "admin12345"
    org_name: str = "Dev Org"
    orbit_name: str = field(default_factory=lambda: _env("ORBIT_NAME", "production-ml"))
    bucket_name: str = "dev-bucket"
    demo_speed: float = field(default_factory=lambda: float(_env("SPEED", "1.0")))
    history_hours: int = field(default_factory=lambda: _env_int("HISTORY_HOURS", 24))
    sat_port_base: int = field(default_factory=lambda: _env_int("SAT_PORT_BASE", 8081))
    greptime_port_base: int = field(default_factory=lambda: _env_int("GREPTIME_PORT_BASE", 14001))
    otlp_port_base: int = field(default_factory=lambda: _env_int("OTLP_PORT_BASE", 14317))

    @property
    def api_url(self) -> str:
        return f"http://localhost:{self.api_port}"

    @property
    def web_url(self) -> str:
        return f"http://localhost:{self.web_port}"

    @property
    def prisma_url(self) -> str:
        return f"http://127.0.0.1:{self.prisma_port}"

    @property
    def platform_url_for_docker(self) -> str:
        return f"http://host.docker.internal:{self.api_port}"

    @property
    def bucket_endpoint_for_docker(self) -> str:
        return f"{self.docker_host_ip or detect_docker_host_ip()}:{self.minio_port}"

    @property
    def experiments_dir(self) -> Path:
        return self.home / "experiments"

    @property
    def repos_dir(self) -> Path:
        return self.home / "repos"

    @property
    def sats_dir(self) -> Path:
        return self.home / "sats"

    @property
    def logs_dir(self) -> Path:
        return self.home / "logs"

    @property
    def state_path(self) -> Path:
        return self.home / "state.json"

    @property
    def satellites(self) -> tuple[SatelliteSpec, ...]:
        return (
            SatelliteSpec(
                slug="prod",
                name="prod-eu-west-1",
                description="Production inference node (Docker, eu-west-1)",
                port=self.sat_port_base,
                greptime_port=self.greptime_port_base,
                otlp_port=self.otlp_port_base,
            ),
            SatelliteSpec(
                slug="staging",
                name="staging-eu-west-1",
                description="Staging / canary node (Docker, eu-west-1)",
                port=self.sat_port_base + 1,
                greptime_port=self.greptime_port_base + 1,
                otlp_port=self.otlp_port_base + 1,
            ),
        )

    def satellite(self, slug: str) -> SatelliteSpec:
        for spec in self.satellites:
            if spec.slug == slug:
                return spec
        raise KeyError(slug)

    def scenario(self, name: str) -> ScenarioSpec:
        for spec in SCENARIOS:
            if spec.name == name:
                return spec
        raise KeyError(name)


def detect_docker_host_ip() -> str:
    """An address of this host that both the browser and Docker containers can reach.

    Published MinIO ports are bound on every host interface, and a container on any
    bridge network reaches the host through the docker0 gateway, so that address is
    the one presigned URLs have to carry.
    """
    try:
        output = subprocess.run(
            ["ip", "-4", "-o", "addr", "show", "docker0"],
            capture_output=True, text=True, check=False,
        ).stdout
    except FileNotFoundError:
        output = ""
    for token in output.split():
        if "/" in token and token[0].isdigit():
            return token.split("/")[0]
    return "172.17.0.1"
