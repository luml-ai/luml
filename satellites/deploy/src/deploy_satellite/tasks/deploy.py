"""Deploy task implementation for the deploy satellite."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse
from uuid import UUID

from aiodocker.exceptions import DockerError
from luml_satellite_sdk import (
    BaseTask,
    ContainerNotFoundError,
    ContainerNotRunningError,
    Deployment,
    DeploymentStatus,
    DeploymentUpdate,
    ErrorMessage,
    PlatformClient,
    SatelliteTaskStatus,
)

if TYPE_CHECKING:
    from aiodocker.containers import DockerContainer

    from deploy_satellite.docker import DockerService

logger = logging.getLogger(__name__)


class DeployTask(BaseTask):
    """Task for deploying a model container."""

    default_health_check_timeout = 1800

    def __init__(
        self,
        *,
        platform: PlatformClient,
        docker: DockerService,
        model_image: str,
        model_server_port: int = 8080,
    ) -> None:
        """Initialize the deploy task.

        Args:
            platform: Platform client for API calls.
            docker: Docker service for container management.
            model_image: Docker image to use for model containers.
            model_server_port: Port for model server.
        """
        self.platform = platform
        self.docker = docker
        self.model_image = model_image
        self.model_server_port = model_server_port

    @classmethod
    def get_task_type(cls) -> str:
        """Return the task type identifier."""
        return "deploy"

    async def execute(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Execute the deploy task.

        Args:
            task_data: Dictionary containing task data with keys:
                - id: Task ID
                - payload: Dict with deployment_id

        Returns:
            Dictionary with inference_url on success.

        Raises:
            Exception: If deployment fails.
        """
        task_id = task_data["id"]
        await self.platform.update_task_status(task_id, SatelliteTaskStatus.RUNNING)

        payload = task_data.get("payload") or {}
        dep_id = payload.get("deployment_id")

        if dep_id is None:
            error_message = ErrorMessage(
                reason="Failed to deploy model",
                error="Missing deployment_id in task.",
            )
            await self.platform.update_task_status(
                task_id, SatelliteTaskStatus.FAILED, error_message
            )
            return {"error": "Missing deployment_id"}

        try:
            dep, presigned_url = await self._get_deployment_artifacts(dep_id, task_id)
        except Exception:
            return {"error": "Failed to get deployment artifacts"}

        satellite_params = dep.satellite_parameters or {}
        health_check_timeout = satellite_params.get(
            "health_check_timeout", self.default_health_check_timeout
        )

        try:
            container = await self.docker.run_model_container(
                image=self.model_image,
                name=f"sat-{dep_id}",
                container_port=self.model_server_port,
                labels={
                    "df.deployment_id": dep_id,
                    "df.model_id": self._get_model_id_from_url(presigned_url),
                },
                env=await self._get_container_env(presigned_url, dep),
            )
        except DockerError as e:
            await self._handle_container_creation_error(task_id, dep_id, str(e))
            return {"error": "Failed to create container"}

        inference_url = f"/deployments/{dep_id}"

        health_ok = await self._wait_for_health(
            container, task_id, dep_id, int(health_check_timeout)
        )
        if not health_ok:
            return {"error": "Health check failed"}

        try:
            await self.platform.update_deployment(
                dep_id,
                DeploymentUpdate(
                    inference_url=inference_url,
                    status=DeploymentStatus.ACTIVE,
                ),
            )
            await self.platform.update_task_status(
                task_id,
                SatelliteTaskStatus.DONE,
                {"inference_url": inference_url},
            )
            return {"inference_url": inference_url}
        except Exception as e:
            logger.error(f"Failed to finalize deployment {dep_id}: {e}", exc_info=True)
            error_message = ErrorMessage(
                reason="failed to finalize deployment", error=str(e)
            )
            await self.platform.update_task_status(
                task_id, SatelliteTaskStatus.FAILED, error_message
            )
            await self.platform.update_deployment(
                dep_id,
                DeploymentUpdate(
                    status=DeploymentStatus.FAILED, error_message=error_message
                ),
            )
            raise

    async def _wait_for_health(
        self,
        container: DockerContainer,
        task_id: str,
        dep_id: str,
        timeout: int,
    ) -> bool:
        """Wait for container health check to pass.

        Args:
            container: The Docker container.
            task_id: Task ID for status updates.
            dep_id: Deployment ID.
            timeout: Maximum seconds to wait.

        Returns:
            True if health check passed, False otherwise.
        """
        import httpx

        for i in range(timeout):
            if i % 5 == 0:
                try:
                    await self.docker.check_container_running(dep_id)
                except (ContainerNotFoundError, ContainerNotRunningError) as e:
                    await self._handle_deploying_error(
                        container, task_id, dep_id, str(e)
                    )
                    return False

            with contextlib.suppress(Exception):
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"http://sat-{dep_id}:{self.model_server_port}/healthz",
                        timeout=5.0,
                    )
                    if response.status_code == 200:
                        return True

            await asyncio.sleep(1)

        await self._handle_healthcheck_timeout(container, task_id, dep_id)
        return False

    async def _handle_healthcheck_timeout(
        self, container: DockerContainer, task_id: str, dep_id: str
    ) -> None:
        """Handle health check timeout."""
        logs_str = ""
        try:
            logs_raw = await container.log(
                stdout=True, stderr=True, follow=False, tail=80
            )
            if isinstance(logs_raw, list):
                logs_str = "".join(logs_raw)
            elif isinstance(logs_raw, str):
                logs_str = logs_raw
            else:
                logs_str = str(logs_raw) if logs_raw is not None else ""
        except Exception:
            pass
        error_message = ErrorMessage(
            reason="healthcheck timeout", error=logs_str[-1000:]
        )
        await self.platform.update_task_status(
            task_id, SatelliteTaskStatus.FAILED, error_message
        )
        await self.platform.update_deployment(
            dep_id,
            DeploymentUpdate(
                status=DeploymentStatus.FAILED, error_message=error_message
            ),
        )

    async def _get_deployment_artifacts(
        self, dep_id: str, task_id: str
    ) -> tuple[Deployment, str]:
        """Fetch deployment details and presigned URL."""
        try:
            deployment = await self.platform.get_deployment(UUID(dep_id))
            if not deployment:
                raise ValueError("deployment not found")
            presigned_url = await self.platform.get_model_artifact_download_url(
                UUID(deployment.model_id)
            )
            return deployment, presigned_url
        except Exception as e:
            error_message = ErrorMessage(
                reason="failed to get model artifact details", error=str(e)
            )
            await self.platform.update_task_status(
                task_id, SatelliteTaskStatus.FAILED, error_message
            )
            await self.platform.update_deployment(
                dep_id,
                DeploymentUpdate(
                    status=DeploymentStatus.FAILED, error_message=error_message
                ),
            )
            raise

    async def _get_secrets_env(self, secrets_payload: dict[str, str]) -> dict[str, str]:
        """Retrieve secret environment variables."""
        secrets_env: dict[str, str] = {}
        if isinstance(secrets_payload, dict):
            for key, secret_id in secrets_payload.items():
                try:
                    secret = await self.platform.get_orbit_secret(UUID(secret_id))
                    secrets_env[str(key)] = str(secret.get("value", ""))
                except Exception:
                    continue
        return secrets_env

    async def _get_container_env(
        self, presigned_url: str, deployment: Deployment
    ) -> dict[str, str]:
        """Build container environment variables."""
        secrets_env = await self._get_secrets_env(
            deployment.env_variables_secrets or {}
        )

        env: dict[str, str] = {
            "MODEL_ARTIFACT_URL": str(presigned_url),
            "DEPLOYMENT_ID": str(deployment.id),
            "MODEL_NAME": deployment.model_artifact_name,
        }
        for key, value in secrets_env.items():
            env[key] = value

        for key, value in (deployment.env_variables or {}).items():
            env[key] = value

        return env

    @staticmethod
    def _get_model_id_from_url(url: str) -> str:
        """Extract model ID from presigned URL."""
        parsed_url = urlparse(url)
        url_path = parsed_url.path.split("?")[0]
        return hashlib.md5(url_path.encode()).hexdigest()

    async def _handle_container_creation_error(
        self, task_id: str, dep_id: str, error_str: str
    ) -> None:
        """Handle container creation errors."""
        if "No such image" in error_str or "not found" in error_str.lower():
            error_message = ErrorMessage(
                reason="Docker image not found",
                error=f"Image '{self.model_image}' not found. "
                "Please ensure the image is built or pulled on the satellite.",
            )
        else:
            error_message = ErrorMessage(
                reason="Failed to create container", error=error_str
            )

        logger.error(f"Failed to run container for deployment {dep_id}: {error_str}")
        await self.platform.update_task_status(
            task_id, SatelliteTaskStatus.FAILED, error_message
        )
        await self.platform.update_deployment(
            dep_id,
            DeploymentUpdate(
                status=DeploymentStatus.FAILED, error_message=error_message
            ),
        )

    async def _handle_deploying_error(
        self, container: DockerContainer, task_id: str, dep_id: str, error_str: str
    ) -> None:
        """Handle errors during deployment."""
        logs_str = ""
        try:
            logs_raw = await container.log(
                stdout=True, stderr=True, follow=False, tail=100
            )
            if isinstance(logs_raw, list):
                logs_str = "".join(logs_raw)
            elif isinstance(logs_raw, str):
                logs_str = logs_raw
            else:
                logs_str = str(logs_raw) if logs_raw is not None else ""
        except Exception:
            pass

        error_message = ErrorMessage(
            reason="Container stopped or not found",
            error=f"{error_str}\n\nLogs:\n{logs_str[-1000:]}",
        )
        logger.error(f"[deploy] Container {dep_id} check failed: {error_message}")
        await self.platform.update_task_status(
            task_id, SatelliteTaskStatus.FAILED, error_message
        )
        await self.platform.update_deployment(
            dep_id,
            DeploymentUpdate(
                status=DeploymentStatus.FAILED, error_message=error_message
            ),
        )
