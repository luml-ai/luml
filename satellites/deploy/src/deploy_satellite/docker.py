"""Docker service for managing model containers."""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

import aiodocker
from aiodocker.exceptions import DockerError
from luml_satellite_sdk import ContainerNotFoundError, ContainerNotRunningError

if TYPE_CHECKING:
    from aiodocker.containers import DockerContainer

logger = logging.getLogger(__name__)


class DockerService:
    """Service for managing Docker containers for model deployments."""

    def __init__(
        self,
        *,
        network_name: str = "satellite_satellite-network",
        model_server_port: int = 8080,
    ) -> None:
        """Initialize the Docker service.

        Args:
            network_name: Docker network name for containers.
            model_server_port: Default port for model servers.
        """
        self.client = aiodocker.Docker()
        self.network_name = network_name
        self.model_server_port = model_server_port

    async def __aenter__(self) -> DockerService:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        await self.client.close()

    async def run_model_container(
        self,
        *,
        image: str,
        name: str,
        container_port: int | None = None,
        labels: dict[str, str] | None = None,
        env: dict[str, str] | None = None,
        restart: str = "on-failure",
    ) -> DockerContainer:
        """Create and start a model container.

        Args:
            image: Docker image to use.
            name: Container name.
            container_port: Port to expose (defaults to model_server_port).
            labels: Container labels.
            env: Environment variables.
            restart: Restart policy.

        Returns:
            The created and started container.
        """
        port = container_port or self.model_server_port
        base_env = {
            "SATELLITE_AGENT_URL": f"http://satellite-agent:{port}",
        }
        if env:
            base_env.update(env)

        config = {
            "Image": image,
            "Labels": labels or {},
            "ExposedPorts": {f"{port}/tcp": {}},
            "Env": [f"{k}={v}" for k, v in base_env.items()],
            "HostConfig": {
                "RestartPolicy": {"Name": restart, "MaximumRetryCount": 3},
                "NetworkMode": self.network_name,
            },
        }

        container = await self.client.containers.create_or_replace(
            config=config,
            name=name,  # type: ignore[arg-type]
        )
        await container.start()

        return container

    async def remove_model_container(
        self, *, deployment_id: UUID
    ) -> tuple[bool, str | None]:
        """Remove a model container.

        Args:
            deployment_id: The deployment ID used to name the container.

        Returns:
            Tuple of (success, model_id) where model_id is extracted from labels.
        """
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
        """Check if a model is currently in use by any container.

        Args:
            model_id: The model ID to check.

        Returns:
            True if the model is in use, False otherwise.
        """
        containers = await self.client.containers.list(all=True)
        for container in containers:
            info = await container.show()
            labels = info.get("Config", {}).get("Labels", {})
            if labels.get("df.model_id") == model_id:
                return True
        return False

    async def _container_for_model_cache_clean_up(
        self, model_id: str
    ) -> DockerContainer:
        """Create a temporary container to clean up model cache.

        Args:
            model_id: The model ID whose cache should be cleaned.

        Returns:
            The cleanup container after it has completed.
        """
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
        container = await self.client.containers.create(config=config)  # type: ignore[arg-type]
        await container.start()
        await container.wait()

        return container

    async def check_container_running(self, deployment_id: str) -> None:
        """Check if a container is running.

        Args:
            deployment_id: The deployment ID to check.

        Raises:
            ContainerNotFoundError: If the container doesn't exist.
            ContainerNotRunningError: If the container exists but isn't running.
        """
        try:
            container = await self.client.containers.get(f"sat-{deployment_id}")
        except DockerError as e:
            raise ContainerNotFoundError(deployment_id) from e

        container_info = await container.show()
        status = container_info["State"]["Status"]

        if status != "running":
            raise ContainerNotRunningError(deployment_id, status)

    async def cleanup_model_cache(self, model_id: str) -> None:
        """Clean up cached model files if the model is no longer in use.

        Args:
            model_id: The model ID whose cache should be cleaned.
        """
        if await self.is_model_in_use(model_id):
            logger.info(
                f'[DockerService] Model "{model_id}" is still in use, '
                "skipping cache cleanup."
            )
            return

        try:
            container = await self._container_for_model_cache_clean_up(model_id)

            with contextlib.suppress(DockerError):
                await container.delete(force=True)

            logger.info(
                f'[DockerService] Successfully cleaned cache for model "{model_id}".'
            )
        except DockerError as error:
            logger.error(f"[DockerService] Error cleaning model cache.\n{error!s}")
