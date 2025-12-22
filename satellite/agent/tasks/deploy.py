import hashlib
import logging
from urllib.parse import urlparse
from uuid import UUID

from aiodocker.containers import DockerContainer

from agent.clients import ModelServerClient
from agent.handlers.handler_instances import ms_handler
from agent.schemas import (
    Deployment,
    DeploymentStatus,
    DeploymentUpdate,
    SatelliteQueueTask,
    SatelliteTaskStatus,
)
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
        error_message = {"reason": "healthcheck timeout", "error": str(logs)[-1000:]}
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
            error_message = {"reason": "failed to get model artifact details", "error": str(e)}
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

    async def run(self, task: SatelliteQueueTask) -> None:
        await self.platform.update_task_status(task.id, SatelliteTaskStatus.RUNNING)

        dep_id = (task.payload or {}).get("deployment_id")
        if dep_id is None:
            await self.platform.update_task_status(
                task.id, SatelliteTaskStatus.FAILED, {"reason": "missing deployment_id"}
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

        inference_url = f"/deployments/{dep_id}"
        async with ModelServerClient() as client:
            health_ok = await client.is_healthy(dep_id, timeout=int(health_check_timeout))

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
            error_message = {"reason": "failed to finalize deployment", "error": str(e)}
            await self.platform.update_task_status(
                task.id, SatelliteTaskStatus.FAILED, error_message
            )
            await self.platform.update_deployment(
                dep_id,
                DeploymentUpdate(status=DeploymentStatus.FAILED, error_message=error_message),
            )
