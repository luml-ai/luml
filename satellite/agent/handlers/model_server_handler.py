import logging

from agent.clients import ModelServerClient, PlatformClient
from agent.schemas import Deployment, LocalDeployment
from agent.settings import config

logger = logging.getLogger(__name__)


class ModelServerHandler:
    def __init__(self) -> None:
        self.deployments: dict[str, LocalDeployment] = {}
        self._openapi_cache_invalidation_callbacks = []

    async def add_deployment(self, deployment: Deployment) -> None:
        manifest = None
        openapi_schema = None
        try:
            async with ModelServerClient() as client:
                manifest = await client.get_manifest(deployment.id)
                openapi_schema = await client.get_openapi_schema(deployment.id)
        except Exception:
            pass
        
        self.deployments[str(deployment.id)] = LocalDeployment(
            deployment_id=deployment.id,
            dynamic_attributes_secrets=deployment.dynamic_attributes_secrets,
            manifest=manifest,
            openapi_schema=openapi_schema,
        )
        self._invalidate_openapi_cache()

    async def get_deployment(self, deployment_id: str) -> LocalDeployment | None:
        return self.deployments.get(deployment_id)

    async def list_active_deployments(self) -> list[LocalDeployment]:
        active_deployments = {}

        for dep_id, info in self.deployments.items():
            async with ModelServerClient() as client:
                try:
                    health_ok = await client.is_healthy(int(dep_id))
                    if health_ok:
                        active_deployments[dep_id] = info
                except Exception:
                    pass

        self.deployments = active_deployments
        return list(active_deployments.values())

    async def sync_deployments(self) -> None:
        logger.info('sync_deployments')
        async with PlatformClient(
            str(config.PLATFORM_URL), config.SATELLITE_TOKEN
        ) as platform_client:
            deployments_db = await platform_client.list_deployments()
            deployments_db = [dep for dep in deployments_db if dep.get("status", "") == "active"]

            logger.info(f'[deployments_db] {deployments_db}')
            for dep in deployments_db:
                try:
                    async with ModelServerClient() as client:
                        health_ok = await client.is_healthy(dep["id"])
                except Exception:
                    health_ok = False
                logger.info(f'[dep] {dep["id"]} health_ok - {health_ok}')
                if health_ok:
                    manifest = None
                    openapi_schema = None
                    try:
                        async with ModelServerClient() as client:
                            manifest = await client.get_manifest(dep["id"])
                            openapi_schema = await client.get_openapi_schema(dep["id"])
                            logger.info(f"[manifest] {manifest}")
                            logger.info(f"[openapi_schema] {openapi_schema}")

                    except Exception:
                        pass
                    
                    self.deployments[str(dep["id"])] = LocalDeployment(
                        deployment_id=dep["id"],
                        dynamic_attributes_secrets=dep.get("dynamic_attributes_secrets"),
                        manifest=manifest,
                        openapi_schema=openapi_schema,
                    )

            logger.info(f"Synced deployments: {list(self.deployments.keys())}")
        
        self._invalidate_openapi_cache()

    @staticmethod
    async def get_compute_missing_secrets(
        deployment: LocalDeployment, compute_dynamic_atr: dict
    ) -> dict:
        from agent.handlers.handler_instances import secrets_handler

        missing_secrets = {}
        deployment_secrets = deployment.dynamic_attributes_secrets

        if deployment_secrets:
            for attr_name, secret_id in deployment_secrets.items():
                if attr_name not in compute_dynamic_atr:
                    secret = await secrets_handler.get_secret(secret_id)
                    if secret:
                        missing_secrets[attr_name] = secret.value

        return compute_dynamic_atr | missing_secrets

    async def model_compute(self, deployment_id: int, body: dict) -> dict:
        deployment = await self.get_deployment(str(deployment_id))
        if not deployment:
            raise ValueError(f"Deployment {deployment_id} not found")

        body["dynamic_attributes"] = await self.get_compute_missing_secrets(
            deployment, body.get("dynamic_attributes") or {}
        )

        try:
            async with ModelServerClient() as client:
                return await client.compute(deployment_id, body)
        except Exception as e:
            raise RuntimeError(f"Model server request failed: {str(e)}") from e

    def register_openapi_cache_invalidation_callback(self, callback):
        self._openapi_cache_invalidation_callbacks.append(callback)

    def _invalidate_openapi_cache(self):
        for callback in self._openapi_cache_invalidation_callbacks:
            try:
                callback()
            except Exception:
                pass
