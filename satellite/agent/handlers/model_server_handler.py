import json
from pathlib import Path

from agent.clients import PlatformClient
from agent.handlers.http_client import HttpClient
from agent.settings import config




class ModelServerHandler:
    def __init__(self, state_file: str = "deployments.json") -> None:
        self.state_file = Path(state_file)
        self._client = HttpClient()

    @staticmethod
    def _to_local_deployment(deployment_id: int, model_url: str) -> dict:
        return {
            "deployment_id": deployment_id,
            "model_url": model_url,
        }

    async def _read_deployments(self) -> dict[str, dict]:
        if not self.state_file.exists():
            return {}

        try:
            with open(self.state_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    async def _write_deployments(self, deployments: dict[str, dict]) -> None:
        data = {str(k): v for k, v in deployments.items()}

        temp_file = self.state_file.with_suffix(".tmp")
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=2, default=str)
        temp_file.rename(self.state_file)

    async def add_deployment(
        self,
        deployment_id: int,
        model_url: str,
    ) -> None:
        deployments = await self._read_deployments()

        deployments[str(deployment_id)] = self._to_local_deployment(deployment_id, model_url)
        await self._write_deployments(deployments)

    async def get_deployment(self, deployment_id: str) -> dict | None:
        deployments = await self._read_deployments()
        return deployments.get(deployment_id)

    async def list_active_deployments(self) -> list[dict]:
        deployments = await self._read_deployments()
        active_deployments = {}
        updated = False

        for deployment_id, info in deployments.items():
            try:
                health_ok = await self._client.get(f"{info['model_url']}/healthz")
                if health_ok:
                    active_deployments[deployment_id] = info
                else:
                    updated = True
            except Exception:
                updated = True

        if updated:
            await self._write_deployments(active_deployments)

        return list(active_deployments.values())

    async def sync_deployments(self) -> None:
        async with PlatformClient(
            str(config.PLATFORM_URL), config.SATELLITE_TOKEN
        ) as platform_client:
            deployments_db = await platform_client.list_deployments()
        deployments_db = [dep for dep in deployments_db if dep.get("status", "") == "active"]
        deployments = await self._read_deployments()

        for dep in deployments_db:
            try:
                health_ok = await self._client.get(f"{dep["inference_url"]}/healthz")
            except Exception:
                health_ok = False
            if health_ok:
                deployments[str(dep["id"])] = self._to_local_deployment(
                    dep["id"], dep["inference_url"]
                )

        await self._write_deployments(deployments)

    async def model_compute(self, deployment_id: int, body: dict) -> dict:
        deployment = await self.get_deployment(str(deployment_id))
        if not deployment:
            raise ValueError(f"Deployment {deployment_id} not found")


        try:
            return await self._client.post(f"{deployment['model_url']}/compute", body)
        except Exception as e:
            raise ValueError(f"Model server request failed: {str(e)}") from e

    async def model_manifest(self, deployment_id: int) -> dict:
        deployment = await self.get_deployment(str(deployment_id))
        if not deployment:
            raise ValueError(f"Deployment {deployment_id} not found")

        try:
            return await self._client.get(f"{deployment['model_url']}/manifest")
        except Exception as e:
            raise ValueError(f"Model server request failed: {str(e)}") from e
