from datetime import UTC, datetime
from typing import Any, Protocol, cast

import httpx
from luml_satellite import (
    ArtifactDeliveryMode,
    ArtifactHandle,
    Deployment,
    RecordingPolicy,
    SatelliteRuntime,
    StartContext,
    TokenDeriver,
)

from luml_satellite_kubernetes import KubernetesConfiguration
from luml_satellite_kubernetes.settings import build_settings_model

SATELLITE_ID = "00000000-0000-0000-0000-000000000001"
OTHER_SATELLITE_ID = "00000000-0000-0000-0000-000000000002"
DEPLOYMENT_ID = "10000000-0000-0000-0000-000000000001"
OTHER_DEPLOYMENT_ID = "10000000-0000-0000-0000-000000000002"
ARTIFACT_ID = "20000000-0000-0000-0000-000000000001"
DERIVATION_KEY = "stable-derivation-key"


def configuration(**overrides: object) -> KubernetesConfiguration:
    values: dict[str, object] = {
        "SATELLITE_TOKEN": "test-token",
        "DERIVATION_KEY": DERIVATION_KEY,
        "PLATFORM_URL": "http://platform",
        "BASE_URL": "http://satellite.example",
        "NAMESPACE": "models",
        "SATELLITE_NAME": "release-one",
        "SATELLITE_INTERNAL_URL": "http://release-one-satellite:8001",
        "INGRESS_HOST": "models.example.test",
        "MONITORING_ENABLED": False,
        "OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector:4317",
        "REMOVAL_TIMEOUT_SEC": 0,
    }
    values.update(overrides)
    return KubernetesConfiguration.model_validate(values)


def deployment(**overrides: object) -> Deployment:
    values: dict[str, object] = {
        "id": DEPLOYMENT_ID,
        "orbit_id": "30000000-0000-0000-0000-000000000001",
        "satellite_id": SATELLITE_ID,
        "satellite_name": "Kubernetes satellite",
        "orbit_name": "Production",
        "name": "classifier",
        "artifact_id": ARTIFACT_ID,
        "artifact_name": "classifier.tar.gz",
        "collection_id": "40000000-0000-0000-0000-000000000001",
        "status": "pending",
        "monitoring_mode": "full",
        "satellite_parameters": {},
        "dynamic_attributes_secrets": {},
        "env_variables_secrets": {},
        "env_variables": {},
        "created_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
    }
    values.update(overrides)
    return Deployment.model_validate(values)


def deployment_record(**overrides: object) -> dict[str, Any]:
    return deployment(**overrides).model_dump(mode="json")


def start_context(
    config: KubernetesConfiguration | None = None,
    *,
    deployment_id: str = DEPLOYMENT_ID,
    artifact_id: str = ARTIFACT_ID,
    parameters: dict[str, object] | None = None,
    secrets: dict[str, str] | None = None,
    download_url: str = "https://artifacts.example/model.tar.gz?X-Amz-Date=20300101T000000Z&X-Amz-Expires=900",
    satellite_token: str | None = None,
    derivation_key: str | None = None,
) -> StartContext:
    active = config or configuration()
    settings_type = build_settings_model(active)
    settings = settings_type.model_validate(parameters or {})
    tokens = TokenDeriver(
        satellite_token or active.SATELLITE_TOKEN,
        derivation_key if derivation_key is not None else active.DERIVATION_KEY,
    )
    return StartContext(
        settings=settings,
        secrets=secrets or {},
        artifact=ArtifactHandle(
            artifact_id=artifact_id,
            mode=ArtifactDeliveryMode.PRESIGNED_LINK,
            download_url=download_url,
            refresh_url=(
                f"{active.SATELLITE_INTERNAL_URL}/satellites/deployments/{deployment_id}/artifact"
            ),
            token=tokens.artifact_token(deployment_id),
        ),
        telemetry_endpoint=active.OTEL_EXPORTER_OTLP_ENDPOINT,
        health_check_timeout=settings.health_check_timeout,
        recording_policy=RecordingPolicy(),
    )


def upstream_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/healthz":
            return httpx.Response(200, json={"status": "healthy"})
        if request.url.path == "/manifest":
            return httpx.Response(200, json={"variant": "pyfunc"})
        if request.url.path == "/openapi.json":
            return httpx.Response(200, json={"openapi": "3.1.0", "paths": {}})
        if request.url.path == "/reference_profile":
            return httpx.Response(404)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def env_by_name(container: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {entry["name"]: entry for entry in container.get("env", [])}


def container_by_name(manifest: dict[str, Any], name: str) -> dict[str, Any]:
    containers = manifest["spec"]["template"]["spec"]["containers"]
    return next(item for item in containers if item["name"] == name)


def init_container(manifest: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], manifest["spec"]["template"]["spec"]["initContainers"][0])


class AsyncCloseable(Protocol):
    async def aclose(self) -> None: ...


async def close_runtime(runtime: SatelliteRuntime) -> None:
    await cast(AsyncCloseable, runtime.serving).aclose()
    if runtime.monitoring is not None:
        await cast(AsyncCloseable, runtime.monitoring).aclose()
