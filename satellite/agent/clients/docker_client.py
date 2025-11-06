import contextlib
import logging
from typing import Self
from uuid import UUID

import aiodocker
from aiodocker.containers import DockerContainer
from aiodocker.exceptions import DockerError

from agent.settings import config as config_settings

logger = logging.getLogger(__name__)


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
        container_port: int = config_settings.MODEL_SERVER_PORT,
        labels: dict[str, str] | None = None,
        env: dict[str, str] | None = None,
        restart: str = "unless-stopped",
    ) -> DockerContainer:
        base_env = {
            "SATELLITE_AGENT_URL": f"http://satellite-agent:{container_port}",
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
                # "Binds": [
                #     "satellite-models-cache:/app/models",
                # ],
            },
        }

        container = await self.client.containers.create_or_replace(config=config, name=name)
        await container.start()

        return container

    async def remove_model_container(self, *, deployment_id: UUID) -> tuple[bool, str | None]:
        container_name = f"sat-{deployment_id}"
        try:
            container = await self.client.containers.get(container_name)
        except DockerError:
            return False, None

        info = await container.show()
        labels = info.get("Config", {}).get("Labels", {})
        model_id = labels.get("df.model_id")

        with contextlib.suppress(DockerError):
            await container.stop()

        with contextlib.suppress(DockerError):
            await container.delete(force=True)

        return True, model_id

    async def is_model_in_use(self, model_id: str) -> bool:
        containers = await self.client.containers.list(all=True)
        for container in containers:
            info = await container.show()
            labels = info.get("Config", {}).get("Labels", {})
            if labels.get("df.model_id") == model_id:
                return True
        return False

    async def _container_for_model_cache_clean_up(self, model_id: str) -> DockerContainer:
        image_name = "alpine:latest"

        try:
            await self.client.images.get(image_name)
        except DockerError:
            logger.info("[DockerService] Pulling alpine:latest image...")
            await self.client.images.pull(image_name)

        config = {
            "Image": image_name,
            "Cmd": ["rm", "-rf", f"/app/models/{model_id}"],
            "HostConfig": {
                "Binds": ["satellite-models-cache:/app/models"],
            },
        }
        container = await self.client.containers.create(config=config)
        await container.start()
        await container.wait()

        return container

    async def cleanup_model_cache(self, model_id: str) -> None:
        if await self.is_model_in_use(model_id):
            logger.info(
                f'[DockerService] Model "{model_id}" is still in use, skipping cache cleanup.'
            )
            return

        try:
            container = await self._container_for_model_cache_clean_up(model_id)

            with contextlib.suppress(DockerError):
                await container.delete(force=True)

            logger.info(f'[DockerService] Successfully cleaned cache for model "{model_id}".')
        except DockerError as error:
            logger.error(f"[DockerService] Error cleaning model cache.\n{str(error)}")
