import asyncio
import contextlib
import hashlib
import logging
from urllib.parse import urlparse
from uuid import UUID

from aiodocker.containers import DockerContainer
from aiodocker.exceptions import DockerError

from agent._exceptions import ContainerNotFoundError, ContainerNotRunningError
from agent.clients import ModelServerClient
from agent.handlers.handler_instances import ms_handler
from agent.schemas import (
    Deployment,
    DeploymentStatus,
    DeploymentUpdate,
    SatelliteQueueTask,
    SatelliteTaskStatus,
)
from agent.schemas.deployments import ErrorMessage
from agent.settings import config
from agent.tasks.base import Task

logger = logging.getLogger(__name__)


class DeployTask(Task):
    default_health_check_timeout = 1800

    async def _handle_healthcheck_timeout(
        self, container: DockerContainer, task_id: str, dep_id: str
    ) -> None:
        try:
            logs = await container.log(stdout=True, stderr=True, follow=False, tail=80)
            if isinstance(logs, list):
                logs = "".join(logs)
            elif not isinstance(logs, str):
                logs = str(logs) if logs is not None else ""
        except Exception:
            logs = ""
        error_message = ErrorMessage(reason="healthcheck timeout", error=str(logs)[-1000:])
        await self.platform.update_task_status(task_id, SatelliteTaskStatus.FAILED, error_message)
        await self.platform.update_deployment(
            dep_id, DeploymentUpdate(status=DeploymentStatus.FAILED, error_message=error_message)
        )

    async def _get_deployment_artifacts(self, dep_id: str, task_id: str) -> tuple[Deployment, str]:
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
                DeploymentUpdate(status=DeploymentStatus.FAILED, error_message=error_message),
            )
            raise

    async def _get_secrets_env(self, secrets_payload: dict[str, str]) -> dict[str, str]:
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
        secrets_env = await self._get_secrets_env(deployment.env_variables_secrets)

        env: dict[str, str] = {
            "MODEL_ARTIFACT_URL": str(presigned_url),
            "DEPLOYMENT_ID": str(deployment.id),
            "MODEL_NAME": deployment.model_artifact_name,
        }
        for key, value in secrets_env.items():
            env[key] = value

        for key, value in deployment.env_variables.items():
            env[key] = value

        return env

    @staticmethod
    def _get_model_id_from_url(url: str) -> str:
        parsed_url = urlparse(url)
        url_path = parsed_url.path.split("?")[0]
        return hashlib.md5(url_path.encode()).hexdigest()

    async def _handle_container_creation_error(
        self, task_id: str, dep_id: str, error_str: str
    ) -> None:
        if "No such image" in error_str or "not found" in error_str.lower():
            error_message = ErrorMessage(
                reason="Docker image not found",
                error=f"Image '{config.MODEL_IMAGE}' not found. "
                f"Please ensure the image is built or pulled on the satellite.",
            )
        else:
            error_message = ErrorMessage(reason="Failed to create container", error=error_str)

        logger.error(f"Failed to run container for deployment {dep_id}: {error_str}")
        await self.platform.update_task_status(task_id, SatelliteTaskStatus.FAILED, error_message)
        await self.platform.update_deployment(
            dep_id,
            DeploymentUpdate(status=DeploymentStatus.FAILED, error_message=error_message),
        )

    async def _handle_deploying_error(
        self, container: DockerContainer, task_id: str, dep_id: str, error_str: str
    ) -> None:
        try:
            logs = await container.log(stdout=True, stderr=True, follow=False, tail=100)
            if isinstance(logs, list):
                logs = "".join(logs)
            elif not isinstance(logs, str):
                logs = str(logs) if logs is not None else ""
        except Exception:
            logs = ""

        error_message = ErrorMessage(
            reason="Container stopped or not found",
            error=f"{error_str}\n\nLogs:\n{str(logs)[-1000:]}",
        )
        logger.error(f"[deploy] Container {dep_id} check failed: {error_message}")
        await self.platform.update_task_status(task_id, SatelliteTaskStatus.FAILED, error_message)
        await self.platform.update_deployment(
            dep_id,
            DeploymentUpdate(status=DeploymentStatus.FAILED, error_message=error_message),
        )

    async def run(self, task: SatelliteQueueTask) -> None:
        await self.platform.update_task_status(task.id, SatelliteTaskStatus.RUNNING)

        dep_id = (task.payload or {}).get("deployment_id")
        if dep_id is None:
            await self.platform.update_task_status(
                task.id,
                SatelliteTaskStatus.FAILED,
                ErrorMessage(
                    reason="Failed to deploy model", error="Missing deployment_id in task."
                ),
            )
            return
        try:
            dep, presigned_url = await self._get_deployment_artifacts(dep_id, task.id)
        except Exception:
            return

        satellite_params = dep.satellite_parameters or {}
        health_check_timeout = satellite_params.get(
            "health_check_timeout", self.default_health_check_timeout
        )

        try:
            container = await self.docker.run_model_container(
                image=config.MODEL_IMAGE,
                name=f"sat-{dep_id}",
                container_port=config.MODEL_SERVER_PORT,
                labels={
                    "df.deployment_id": dep_id,
                    "df.model_id": self._get_model_id_from_url(presigned_url),
                },
                env=await self._get_container_env(presigned_url, dep),
            )
        except DockerError as e:
            await self._handle_container_creation_error(task.id, dep_id, str(e))
            return

        inference_url = f"/deployments/{dep_id}"

        health_ok = False
        async with ModelServerClient() as client:
            for i in range(int(health_check_timeout)):
                if i % 5 == 0:
                    try:
                        await self.docker.check_container_running(dep_id)
                    except (ContainerNotFoundError, ContainerNotRunningError) as e:
                        await self._handle_deploying_error(container, task.id, dep_id, str(e))
                        return

                with contextlib.suppress(Exception):
                    response = await client._session.get(
                        f"http://sat-{dep_id}:{config.MODEL_SERVER_PORT}/healthz", timeout=5.0
                    )
                    if response.status_code == 200:
                        health_ok = True
                        break

                await asyncio.sleep(1)

        if not health_ok:
            await self._handle_healthcheck_timeout(container, task.id, dep_id)
            return

        try:
            await ms_handler.add_deployment(dep)
            schemas = await ms_handler.get_deployment_schemas(dep_id)

            await self.platform.update_deployment(
                dep_id,
                DeploymentUpdate(
                    inference_url=inference_url, schemas=schemas, status=DeploymentStatus.ACTIVE
                ),
            )
            await self.platform.update_task_status(
                task.id,
                SatelliteTaskStatus.DONE,
                {"inference_url": inference_url},
            )
        except Exception as e:
            logger.error(f"Failed to finalize deployment {dep_id}: {e}", exc_info=True)
            error_message = ErrorMessage(reason="failed to finalize deployment", error=str(e))
            await self.platform.update_task_status(
                task.id, SatelliteTaskStatus.FAILED, error_message
            )
            await self.platform.update_deployment(
                dep_id,
                DeploymentUpdate(status=DeploymentStatus.FAILED, error_message=error_message),
            )
