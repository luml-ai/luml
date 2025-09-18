import json
import re

from agent.handlers.model_server_handler import ModelServerHandler
from agent.schemas import SatelliteQueueTask, SatelliteTaskStatus
from agent.settings import config
from agent.tasks.base import Task

model_server_handler = ModelServerHandler()


class DeployTask(Task):
    @staticmethod
    def fix_env_name(name: str) -> str:
        fixed = re.sub(r'[^A-Za-z0-9_]', '_', name)
        return re.sub(r'_+', '_', fixed).strip('_').upper()

    @staticmethod
    async def _get_ip(container):
        info = await container.show()
        return info.get("NetworkSettings", {}).get("Networks", {}).get("bridge", {}).get("IPAddress") or info.get("NetworkSettings", {}).get("IPAddress") or "127.0.0.1"

    async def _healthy(self, container, container_port):
        ip = await self._get_ip(container)
        return await self.docker.wait_http_ok(
            f"http://{ip}:{container_port}/healthz", timeout_s=45
        )

    async def _handle_healthcheck_timeout(self, container, task):
        try:
            logs = await container.log(stdout=True, stderr=True, follow=False, tail=80)
            if isinstance(logs, list):
                logs = "".join(logs)
            elif not isinstance(logs, str):
                logs = str(logs) if logs is not None else ""
        except Exception:
            logs = ""
        await self.platform.update_task_status(
            task.id,
            SatelliteTaskStatus.FAILED,
            {"reason": "healthcheck timeout", "tail": str(logs)[-1000:]},
        )

    async def _get_deployment_artifacts(self, dep_id, task_id):
        try:
            deployment = await self.platform.get_deployment(dep_id)
            if not deployment:
                raise ValueError("deployment not found")
            model, presigned_url = await self.platform.get_model_artifact(int(deployment.get("model_id")))
            return deployment, model, presigned_url
        except Exception as e:
            await self.platform.update_task_status(
                task_id,
                SatelliteTaskStatus.FAILED,
                {"reason": "failed to get model artifact details", "error": str(e)},
            )
            raise

    async def _get_secrets_env(self, secrets_payload):
        secrets_env: dict[str, str] = {}
        if isinstance(secrets_payload, dict):
            for key, secret_id in secrets_payload.items():
                try:
                    secret = await self.platform.get_orbit_secret(int(secret_id))
                    secrets_env[str(key)] = str(secret.get("value", ""))
                except Exception:
                    continue
        return secrets_env

    async def _get_container_env(self, presigned_url, secrets_payload, env_vars_payload):
        secrets_env = await self._get_secrets_env(secrets_payload)

        env: dict[str, str] = {"MODEL_ARTIFACT_URL": str(presigned_url)}
        for key, value in secrets_env.items():
            env[self.fix_env_name(key)] = value

        if secrets_env:
            env["MODEL_SECRETS"] = json.dumps(secrets_env)

        for key, value in secrets_env.items():
            env[self.fix_env_name(key)] = value

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
            dep, model, presigned_url = await self._get_deployment_artifacts(dep_id, task.id)
        except Exception:
            return

        container_port = int(config.CONTAINER_PORT)
        # TODO validate frontend passed all env variables / secrets that model need during deployment creation
        env = await self._get_container_env(presigned_url, dep.get("secrets") or {}, dep.get("env_vars") or {})

        container, host_port = await self.docker.run_model_container(
            image=config.MODEL_IMAGE,
            name=f"sat-{dep_id}",
            container_port=container_port,
            labels={"df.deployment_id": str(dep_id)},
            env=env,
        )

        if not await self._healthy(container, host_port):
            await self._handle_healthcheck_timeout(container, task)
            return

        inference_url = f"{config.BASE_URL}:{host_port}"
        await self.platform.update_deployment_inference_url(int(dep_id), inference_url)
        await self.platform.update_task_status(
            task.id,
            SatelliteTaskStatus.DONE,
            {"inference_url": inference_url},
        )
        await model_server_handler.add_deployment(dep_id, inference_url)
