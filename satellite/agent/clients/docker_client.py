import contextlib
from typing import Self
from uuid import UUID

import aiodocker
from aiodocker.containers import DockerContainer
from aiodocker.exceptions import DockerError

from agent.settings import config as sat_config


class DockerService:
    def __init__(self) -> None:
        self.client = aiodocker.Docker()
        self.network_name = "satellite_satellite-network"

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001, ANN201
        await self.client.close()

    async def run_model_container(
        self,
        *,
        image: str,
        name: str,
        container_port: int,
        labels: dict[str, str] | None = None,
        env: dict[str, str] | None = None,
        restart: str = "unless-stopped",
    ) -> DockerContainer:
        base_env = {
            "SATELLITE_AGENT_URL": f"http://satellite-agent:{int(sat_config.AUTH_PORT)}",
        }
        if env:
            base_env.update(env)

        config = {
            "Image": image,
            "Labels": labels or {},
            "ExposedPorts": {f"{container_port}/tcp": {}},
            "Env": [f"{k}={v}" for k, v in base_env.items()],
            "HostConfig": {
                "RestartPolicy": {"Name": restart},
                "NetworkMode": self.network_name,
                # TODO: enable
                # "Binds": [
                #     "satellite-models-cache:/app/models",
                # ],
            },
        }

        container = await self.client.containers.create_or_replace(config=config, name=name)
        await container.start()

        return container

    async def remove_model_container(self, *, deployment_id: UUID) -> bool:
        container_name = f"sat-{deployment_id}"
        try:
            container = await self.client.containers.get(container_name)
        except DockerError:
            return False

        with contextlib.suppress(DockerError):
            await container.stop()

        with contextlib.suppress(DockerError):
            await container.delete(force=True)

        return True
