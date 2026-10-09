import logging
from collections.abc import Mapping
from dataclasses import dataclass

from luml_satellite.wire import Deployment

DOCKER_DEPLOYMENT_LABEL = "df.deployment_id"
DOCKER_ARTIFACT_LABEL = "df.model_id"
DOCKER_SATELLITE_LABEL = "df.satellite_id"
DOCKER_LAUNCHER_PROTOCOL_LABEL = "df.launcher_protocol"

KUBERNETES_MANAGED_BY_LABEL = "app.kubernetes.io/managed-by"
KUBERNETES_DEPLOYMENT_LABEL = "luml.ai/deployment-id"
KUBERNETES_ARTIFACT_LABEL = "luml.ai/artifact-id"
KUBERNETES_SATELLITE_LABEL = "luml.ai/satellite-id"
KUBERNETES_LAUNCHER_PROTOCOL_LABEL = "luml.ai/launcher-protocol"
KUBERNETES_DERIVATION_FINGERPRINT_LABEL = "luml.ai/derivation-key-fingerprint"
KUBERNETES_SPEC_FINGERPRINT_LABEL = "luml.ai/workload-spec-fingerprint"
KUBERNETES_SHARED_LABEL = "luml.ai/shared"

MODEL_ARTIFACT_ID = "MODEL_ARTIFACT_ID"
DEPLOYMENT_ID = "DEPLOYMENT_ID"
MODEL_NAME = "MODEL_NAME"
TELEMETRY_ENDPOINT = "OTEL_EXPORTER_OTLP_ENDPOINT"
MODEL_ARTIFACT_TOKEN = "MODEL_ARTIFACT_TOKEN"
SATELLITE_ADDRESS = "SATELLITE_AGENT_URL"


@dataclass(frozen=True)
class ContainerResources:
    cpu_millicores: int | None = None
    memory: str | None = None
    gpu_count: int = 0
    gpu_resource_name: str | None = None

    def __post_init__(self) -> None:
        if self.cpu_millicores is not None and self.cpu_millicores <= 0:
            raise ValueError("cpu_millicores must be greater than zero")
        if self.memory is not None and not self.memory:
            raise ValueError("memory must not be empty")
        if self.gpu_count < 0:
            raise ValueError("gpu_count must not be negative")
        if self.gpu_resource_name == "":
            raise ValueError("gpu_resource_name must not be empty")


def docker_labels(
    *,
    deployment_id: str,
    artifact_id: str,
    satellite_id: str,
    launcher_protocol: str,
) -> dict[str, str]:
    return {
        DOCKER_DEPLOYMENT_LABEL: deployment_id,
        DOCKER_ARTIFACT_LABEL: artifact_id,
        DOCKER_SATELLITE_LABEL: satellite_id,
        DOCKER_LAUNCHER_PROTOCOL_LABEL: launcher_protocol,
    }


def kubernetes_labels(
    *,
    deployment_id: str,
    artifact_id: str,
    satellite_id: str,
    launcher_protocol: str,
    derivation_key_fingerprint: str,
    spec_fingerprint: str,
    shared: bool = False,
) -> dict[str, str]:
    return {
        KUBERNETES_MANAGED_BY_LABEL: "luml-satellite",
        KUBERNETES_DEPLOYMENT_LABEL: deployment_id,
        KUBERNETES_ARTIFACT_LABEL: artifact_id,
        KUBERNETES_SATELLITE_LABEL: satellite_id,
        KUBERNETES_LAUNCHER_PROTOCOL_LABEL: launcher_protocol,
        KUBERNETES_DERIVATION_FINGERPRINT_LABEL: derivation_key_fingerprint,
        KUBERNETES_SPEC_FINGERPRINT_LABEL: spec_fingerprint,
        KUBERNETES_SHARED_LABEL: str(shared).lower(),
    }


def build_container_environment(
    deployment: Deployment,
    resolved_secrets: Mapping[str, str],
    *,
    telemetry_endpoint: str | None = None,
    artifact_token: str | None = None,
    satellite_address: str | None = None,
    logger: logging.Logger | None = None,
) -> dict[str, str]:
    environment = {str(name): str(value) for name, value in resolved_secrets.items()}
    environment.update(
        {str(name): str(value) for name, value in (deployment.env_variables or {}).items()}
    )

    reserved = {
        MODEL_ARTIFACT_ID: str(deployment.artifact_id),
        DEPLOYMENT_ID: str(deployment.id),
        MODEL_NAME: deployment.artifact_name,
    }
    if telemetry_endpoint is not None:
        reserved[TELEMETRY_ENDPOINT] = telemetry_endpoint
    if artifact_token is not None:
        reserved[MODEL_ARTIFACT_TOKEN] = artifact_token
    if satellite_address is not None:
        reserved[SATELLITE_ADDRESS] = satellite_address

    overridden = sorted(environment.keys() & reserved.keys())
    if overridden:
        active_logger = logger or logging.getLogger("luml_satellite")
        active_logger.warning(
            "deployment '%s' supplied reserved environment variables; ignoring them: %s",
            deployment.id,
            overridden,
        )
    environment.update(reserved)
    return environment


build_environment = build_container_environment
