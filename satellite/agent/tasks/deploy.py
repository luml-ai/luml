from aiodocker.containers import DockerContainer

from agent.clients import ModelServerClient
from agent.handlers.handler_instances import ms_handler
from agent.schemas import SatelliteQueueTask, SatelliteTaskStatus
from agent.schemas.deployments import Deployment
from agent.settings import config
from agent.tasks.base import Task


class DeployTask(Task):
    async def _handle_healthcheck_timeout(self, container: DockerContainer, task_id: int) -> None:
        try:
            logs = await container.log(stdout=True, stderr=True, follow=False, tail=80)
            if isinstance(logs, list):
                logs = "".join(logs)
            elif not isinstance(logs, str):
                logs = str(logs) if logs is not None else ""
        except Exception:
            logs = ""
        await self.platform.update_task_status(
            task_id,
            SatelliteTaskStatus.FAILED,
            {"reason": "healthcheck timeout", "tail": str(logs)[-1000:]},
        )

    async def _get_deployment_artifacts(self, dep_id: int, task_id: int) -> tuple[Deployment, str]:
        try:
            deployment = await self.platform.get_deployment(dep_id)
            if not deployment:
                raise ValueError("deployment not found")
            presigned_url = await self.platform.get_model_artifact_download_url(deployment.model_id)
            return deployment, presigned_url
        except Exception as e:
            await self.platform.update_task_status(
                task_id,
                SatelliteTaskStatus.FAILED,
                {"reason": "failed to get model artifact details", "error": str(e)},
            )
            raise

    async def _get_secrets_env(self, secrets_payload: dict[str, int]) -> dict[str, str]:
        secrets_env: dict[str, str] = {}
        if isinstance(secrets_payload, dict):
            for key, secret_id in secrets_payload.items():
                try:
                    secret = await self.platform.get_orbit_secret(int(secret_id))
                    secrets_env[str(key)] = str(secret.get("value", ""))
                except Exception:
                    continue
        return secrets_env

    async def _get_container_env(
        self, presigned_url: str, deployment: Deployment
    ) -> dict[str, str]:
        secrets_env = await self._get_secrets_env(deployment.env_variables_secrets)

        env: dict[str, str] = {"MODEL_ARTIFACT_URL": str(presigned_url)}
        for key, value in secrets_env.items():
            env[key] = value

        for key, value in deployment.env_variables.items():
            env[key] = value

        return env

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

        env = await self._get_container_env(presigned_url, dep)
        container = await self.docker.run_model_container(
            image=config.MODEL_IMAGE,
            name=f"sat-{dep_id}",
            container_port=int(config.CONTAINER_PORT),
            labels={"df.deployment_id": str(dep_id)},
            env=env,
        )

        inference_url = f"{config.BASE_URL}:{int(config.AUTH_PORT)}/deployments/{int(dep_id)}/compute"
        async with ModelServerClient() as client:
            health_ok = await client.is_healthy(int(dep_id))

        if not health_ok:
            await self._handle_healthcheck_timeout(container, task.id)
            return
        await self.platform.update_deployment_inference_url(int(dep_id), inference_url)
        await self.platform.update_task_status(
            task.id,
            SatelliteTaskStatus.DONE,
            {"inference_url": inference_url},
        )

        await ms_handler.add_deployment(dep)
