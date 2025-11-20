import logging
from collections.abc import Callable
from contextlib import suppress
from typing import Any
from uuid import UUID

from agent.clients import ModelServerClient, PlatformClient
from agent.schemas import Deployment, DeploymentStatus, LocalDeployment, Secret
from agent.settings import config

logger = logging.getLogger(__name__)


class ModelServerHandler:
    def __init__(self) -> None:
        self.deployments: dict[str, LocalDeployment] = {}
        self._openapi_cache_invalidation_callbacks = []

    async def add_single_deployment(
        self, deployment_id: str, dynamic_attributes_secrets: dict[str, str] | None
    ) -> None:
        manifest = None
        openapi_schema = None
        with suppress(Exception):
            async with ModelServerClient() as client:
                manifest = await client.get_manifest(deployment_id)
                openapi_schema = await client.get_openapi_schema(deployment_id)

        self.deployments[deployment_id] = LocalDeployment(
            deployment_id=deployment_id,
            dynamic_attributes_secrets=dynamic_attributes_secrets,
            manifest=manifest,
            openapi_schema=openapi_schema,
        )

    async def add_deployment(self, deployment: Deployment) -> None:
        await self.add_single_deployment(deployment.id, deployment.dynamic_attributes_secrets)
        self._invalidate_openapi_cache()

    async def remove_deployment(self, deployment_id: UUID) -> None:
        self.deployments.pop(str(deployment_id), None)
        self._invalidate_openapi_cache()

    async def get_deployment(self, deployment_id: str) -> LocalDeployment | None:
        return self.deployments.get(deployment_id)

    async def list_active_deployments(self) -> list[LocalDeployment]:
        active_deployments = {}

        for dep_id, info in self.deployments.items():
            async with ModelServerClient() as client:
                with suppress(Exception):
                    health_ok = await client.is_healthy(dep_id)
                    if health_ok:
                        active_deployments[dep_id] = info

        self.deployments = active_deployments
        return list(active_deployments.values())

    async def sync_deployments(self) -> None:
        logger.info("[ModelServerHandler] sync_deployments...")
        async with PlatformClient(
            str(config.PLATFORM_URL), config.SATELLITE_TOKEN
        ) as platform_client:
            deployments_db = await platform_client.list_deployments()
            active_deployments_db = [
                dep for dep in deployments_db if dep.get("status", "") == "active"
            ]

            logger.info(
                f"[active_deployments_db] {[d.get('id', '') for d in active_deployments_db]}"
            )
            for dep in active_deployments_db:
                async with ModelServerClient() as client:
                    health_ok = await client.is_healthy(dep["id"])
                if health_ok:
                    await self.add_single_deployment(
                        dep["id"], dep.get("dynamic_attributes_secrets")
                    )
                else:
                    await platform_client.update_deployment_status(
                        dep["id"], DeploymentStatus.NOT_RESPONDING
                    )

            logger.info(f"Synced deployments: {list(self.deployments.keys())}")

        self._invalidate_openapi_cache()

    @staticmethod
    async def get_compute_missing_secrets(
        deployment: LocalDeployment, compute_dynamic_atr: dict
    ) -> dict:
        missing_secrets: dict[str, str] = {}
        deployment_secrets = deployment.dynamic_attributes_secrets or {}

        secrets_to_fetch: list[tuple[str, UUID]] = []
        for attr_name, secret_id in deployment_secrets.items():
            if attr_name in compute_dynamic_atr:
                continue
            secrets_to_fetch.append((attr_name, secret_id))

        if not secrets_to_fetch:
            return compute_dynamic_atr

        try:
            async with PlatformClient(
                str(config.PLATFORM_URL), config.SATELLITE_TOKEN
            ) as platform_client:
                for attr_name, secret_id in secrets_to_fetch:
                    try:
                        secret_data = await platform_client.get_orbit_secret(secret_id)
                    except Exception:
                        secret_data = None

                    if secret_data:
                        secret = Secret.model_validate(secret_data)
                        missing_secrets[attr_name] = secret.value
        except Exception as error:
            logger.error("Failed to fetch secrets for compute: %s", error)

        return compute_dynamic_atr | missing_secrets

    async def model_compute(self, deployment_id: str, body: dict) -> dict:
        deployment = await self.get_deployment(deployment_id)
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

    async def get_deployment_schemas(self, deployment_id) -> dict[str, Any] | None:  # noqa ANN101
        logger.info(f"[get_deployment_schemas] Starting for deployment_id='{deployment_id}'...")

        local_dep = await self.get_deployment(deployment_id)
        schema = local_dep.openapi_schema

        if local_dep and local_dep.dynamic_attributes_secrets:
            dyna_props = (
                schema.get("components", {})
                .get("schemas", {})
                .get("DynamicAttributesModel", {})
                .get("properties", None)
            )
            if dyna_props:
                props_to_remove = [
                    prop for prop in dyna_props if prop in local_dep.dynamic_attributes_secrets
                ]
                for prop in props_to_remove:
                    dyna_props.pop(prop)

        return schema

    def register_openapi_cache_invalidation_callback(self, callback: Callable) -> None:
        self._openapi_cache_invalidation_callbacks.append(callback)

    def _invalidate_openapi_cache(self) -> None:
        for callback in self._openapi_cache_invalidation_callbacks:
            with suppress(Exception):
                callback()
