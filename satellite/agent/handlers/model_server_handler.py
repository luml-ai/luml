import logging
from collections.abc import Callable
from contextlib import suppress
from typing import Any
from uuid import UUID

from agent._exceptions import ContainerNotFoundError, ContainerNotRunningError
from agent.clients import ModelServerClient, ModelServerError, PlatformClient
from agent.clients.docker_client import DockerService
from agent.monitoring.instrumentation import InferenceInstrumentation
from agent.monitoring.telemetry import TelemetrySetup
from agent.schemas import (
    Deployment,
    DeploymentStatus,
    DeploymentUpdate,
    LocalDeployment,
    Secret,
    usable_reference_profile,
)
from agent.settings import config

logger = logging.getLogger(__name__)


class ModelServerHandler:
    def __init__(self, telemetry: TelemetrySetup | None = None) -> None:
        self.deployments: dict[str, LocalDeployment] = {}
        self._openapi_cache_invalidation_callbacks: list[Callable] = []
        self._telemetry = telemetry
        self._instrumentation: InferenceInstrumentation | None = None
        if telemetry and telemetry.active:
            self._instrumentation = InferenceInstrumentation(telemetry)

    async def add_single_deployment(
        self,
        deployment_id: str,
        dynamic_attributes_secrets: dict[str, str] | None,
        *,
        monitoring_enabled: bool = False,
    ) -> None:
        manifest = None
        openapi_schema = None
        reference_profile = None
        try:
            async with ModelServerClient() as client:
                manifest = await client.get_manifest(deployment_id)
                openapi_schema = await client.get_openapi_schema(deployment_id)
                reference_profile = await client.get_reference_profile(deployment_id)
        except Exception as e:
            logger.warning(
                f"[add_single_deployment] Could not fetch manifest/schema for {deployment_id}: {e}"
            )

        self.deployments[deployment_id] = LocalDeployment(
            deployment_id=deployment_id,
            dynamic_attributes_secrets=dynamic_attributes_secrets,
            manifest=manifest,
            openapi_schema=openapi_schema,
            monitoring_enabled=monitoring_enabled,
            reference_profile=usable_reference_profile(reference_profile),
        )

    @staticmethod
    def _read_monitoring_enabled(monitoring_mode: str | None) -> bool:
        return (monitoring_mode or "off").strip().lower() == "full"

    async def add_deployment(self, deployment: Deployment) -> None:
        monitoring_enabled = self._read_monitoring_enabled(deployment.monitoring_mode)
        await self.add_single_deployment(
            deployment.id,
            deployment.dynamic_attributes_secrets,
            monitoring_enabled=monitoring_enabled,
        )
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
        async with (
            PlatformClient(str(config.PLATFORM_URL), config.SATELLITE_TOKEN) as platform_client,
            DockerService() as docker,
        ):
            deployments_db = await platform_client.list_deployments()
            active_deployments_db = [
                dep for dep in deployments_db if dep.get("status", "") == "active"
            ]

            logger.info(
                f"[active_deployments_db] {[d.get('id', '') for d in active_deployments_db]}"
            )

            for dep in active_deployments_db:
                dep_id = dep["id"]
                try:
                    await docker.check_container_running(dep_id)
                except ContainerNotFoundError:
                    await platform_client.update_deployment(
                        dep_id,
                        DeploymentUpdate(
                            status=DeploymentStatus.NOT_RESPONDING,
                            error_message={
                                "reason": "Not Found",
                                "error": f"Container with deployment id '{dep_id}' not found",
                            },
                        ),
                    )
                    continue
                except ContainerNotRunningError as e:
                    await platform_client.update_deployment(
                        dep_id,
                        DeploymentUpdate(
                            status=DeploymentStatus.NOT_RESPONDING,
                            error_message={"reason": "Container not running", "error": str(e)},
                        ),
                    )
                    continue

                async with ModelServerClient() as client:
                    health_ok = await client.is_healthy(dep_id)

                if health_ok:
                    monitoring_enabled = self._read_monitoring_enabled(dep.get("monitoring_mode"))
                    await self.add_single_deployment(
                        dep_id,
                        dep.get("dynamic_attributes_secrets"),
                        monitoring_enabled=monitoring_enabled,
                    )
                else:
                    logs = ""
                    with suppress(Exception):
                        container = await docker.client.containers.get(f"sat-{dep_id}")
                        logs_list = await container.log(
                            stdout=True, stderr=True, follow=False, tail=100
                        )
                        logs = "".join(logs_list) if isinstance(logs_list, list) else str(logs_list)
                    await platform_client.update_deployment(
                        dep_id,
                        DeploymentUpdate(
                            status=DeploymentStatus.NOT_RESPONDING,
                            error_message={
                                "reason": "Health check failed",
                                "error": (
                                    f"Health check failed for deployment '{dep_id}'."
                                    + (f"\n\nContainer logs:\n{str(logs)[-3000:]}" if logs else "")
                                ),
                            },
                        ),
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
                    except Exception as e:
                        logger.warning(
                            f"Failed to fetch secret '{attr_name}' (id={secret_id}): {e}"
                        )
                        secret_data = None

                    if secret_data:
                        secret = Secret.model_validate(secret_data)
                        missing_secrets[attr_name] = secret.value
        except Exception as error:
            logger.error("Failed to fetch secrets for compute: %s", error)

        return compute_dynamic_atr | missing_secrets

    async def model_compute(self, deployment_id: str, body: dict) -> tuple[dict, str | None]:
        deployment = await self.get_deployment(deployment_id)
        if not deployment:
            raise ValueError(f"Deployment {deployment_id} not found")

        safe_inputs: dict[str, Any] | None = None
        should_instrument = deployment.monitoring_enabled and self._instrumentation is not None

        if should_instrument:
            safe_inputs = _extract_safe_inputs(body, deployment)

        body["dynamic_attributes"] = await self.get_compute_missing_secrets(
            deployment, body.get("dynamic_attributes") or {}
        )

        if should_instrument:
            assert self._instrumentation is not None

            async def _forward(*, extra_headers: dict[str, str] | None = None) -> dict:
                try:
                    async with ModelServerClient() as client:
                        return await client.compute(
                            deployment_id, body, extra_headers=extra_headers
                        )
                except ModelServerError:
                    raise
                except Exception as e:
                    raise RuntimeError(f"Model server request failed: {str(e)}") from e

            result, event_id = await self._instrumentation.instrumented_compute(
                deployment_id=deployment_id,
                safe_inputs=safe_inputs,
                forward_fn=_forward,
            )
            return result, event_id

        try:
            async with ModelServerClient() as client:
                result = await client.compute(deployment_id, body)
        except ModelServerError:
            raise
        except Exception as e:
            raise RuntimeError(f"Model server request failed: {str(e)}") from e
        return result, None

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


def _extract_safe_inputs(body: dict, deployment: LocalDeployment) -> dict[str, Any] | None:
    """Capture the model input payload for monitoring, excluding secret-backed attributes.

    The model input payload (``body["inputs"]``) is required for data quality and feature
    drift, so it is recorded verbatim. Dynamic attributes are recorded too, but keys backed
    by secrets are dropped so secret values never reach local telemetry.
    """
    safe: dict[str, Any] = {}

    model_inputs = body.get("inputs")
    if model_inputs is not None:
        safe["inputs"] = model_inputs

    dynamic_attrs = body.get("dynamic_attributes")
    if dynamic_attrs is not None:
        secret_keys = set(deployment.dynamic_attributes_secrets or {})
        safe["dynamic_attributes"] = {
            k: v for k, v in dynamic_attrs.items() if k not in secret_keys
        }

    return safe or None
