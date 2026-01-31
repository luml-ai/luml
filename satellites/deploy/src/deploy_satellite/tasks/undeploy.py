"""Undeploy task implementation for the deploy satellite."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from luml_satellite_sdk import (
    BaseTask,
    DeploymentStatus,
    DeploymentUpdate,
    ErrorMessage,
    PlatformClient,
    SatelliteTaskStatus,
)

if TYPE_CHECKING:
    from deploy_satellite.docker import DockerService

logger = logging.getLogger(__name__)


class UndeployTask(BaseTask):
    """Task for undeploying a model container."""

    def __init__(
        self,
        *,
        platform: PlatformClient,
        docker: DockerService,
    ) -> None:
        """Initialize the undeploy task.

        Args:
            platform: Platform client for API calls.
            docker: Docker service for container management.
        """
        self.platform = platform
        self.docker = docker

    @classmethod
    def get_task_type(cls) -> str:
        """Return the task type identifier."""
        return "undeploy"

    async def execute(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Execute the undeploy task.

        Args:
            task_data: Dictionary containing task data with keys:
                - id: Task ID
                - payload: Dict with deployment_id

        Returns:
            Dictionary with container_removed status on success.

        Raises:
            Exception: If undeployment fails.
        """
        task_id = task_data["id"]
        await self.platform.update_task_status(task_id, SatelliteTaskStatus.RUNNING)

        payload = task_data.get("payload") or {}
        deployment_id_str: str = payload.get("deployment_id", "")
        deployment_id = UUID(deployment_id_str)

        try:
            container_removed, model_id = await self.docker.remove_model_container(
                deployment_id=deployment_id
            )
        except Exception as error:
            error_message = ErrorMessage(
                reason="Failed to remove container.",
                error=str(error),
            )
            await self.platform.update_task_status(
                task_id, SatelliteTaskStatus.FAILED, error_message
            )
            await self.platform.update_deployment(
                deployment_id_str,
                DeploymentUpdate(
                    error_message=error_message, status=DeploymentStatus.DELETION_FAILED
                ),
            )
            return {"error": "Failed to remove container"}

        try:
            await self.platform.delete_deployment(deployment_id)
        except Exception as error:
            error_message = ErrorMessage(
                reason="Failed to delete deployment.", error=str(error)
            )
            await self.platform.update_task_status(
                task_id, SatelliteTaskStatus.FAILED, error_message
            )
            await self.platform.update_deployment(
                deployment_id_str,
                DeploymentUpdate(
                    error_message=error_message, status=DeploymentStatus.DELETION_FAILED
                ),
            )
            return {"error": "Failed to delete deployment"}

        await self.platform.update_task_status(
            task_id,
            SatelliteTaskStatus.DONE,
            {"container_removed": container_removed},
        )

        return {"container_removed": container_removed}
