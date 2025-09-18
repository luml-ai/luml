import asyncio
import socket
from contextlib import closing
from typing import Self

import aiodocker
import httpx
from agent.settings import config as sat_config
from aiodocker.containers import DockerContainer


def get_ephemeral_host_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class DockerService:
    def __init__(self) -> None:
        self.client = aiodocker.Docker()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001, ANN201
        await self.client.close()

    async def wait_http_ok(self, url: str, timeout_s: int = 45) -> bool:
        async with httpx.AsyncClient() as client:
            for _ in range(timeout_s):
                try:
                    r = await client.get(url)
                    if r.status_code == 200:
                        return True
                except Exception:
                    pass
                await asyncio.sleep(1)
        return False

    async def run_model_container(
        self,
        *,
        image: str,
        name: str,
        container_port: int,
        labels: dict[str, str] | None = None,
        env: dict[str, str] | None = None,
        restart: str = "unless-stopped",
    ) -> tuple[DockerContainer, int]:
        host_port = get_ephemeral_host_port()

        base_env = {
            "SATELLITE_AGENT_URL": f"http://host.docker.internal:{int(sat_config.AUTH_PORT)}",
        }
        if env:
            base_env.update(env)

        config = {
            "Image": image,
            "Labels": labels or {},
            "ExposedPorts": {f"{container_port}/tcp": {}},
            "Env": [f"{k}={v}" for k, v in base_env.items()],
            "HostConfig": {
                "PortBindings": {f"{container_port}/tcp": [{"HostPort": str(host_port)}]},
                "RestartPolicy": {"Name": restart},
                "ExtraHosts": ["host.docker.internal:host-gateway"],
            },
        }
        container = await self.client.containers.create_or_replace(config=config, name=name)
        await container.start()
        return container, host_port
