import logging

import pytest

from luml_satellite import Deployment
from luml_satellite.container import (
    DEPLOYMENT_ID,
    DOCKER_ARTIFACT_LABEL,
    DOCKER_DEPLOYMENT_LABEL,
    DOCKER_LAUNCHER_PROTOCOL_LABEL,
    DOCKER_SATELLITE_LABEL,
    KUBERNETES_ARTIFACT_LABEL,
    KUBERNETES_DEPLOYMENT_LABEL,
    KUBERNETES_DERIVATION_FINGERPRINT_LABEL,
    KUBERNETES_LAUNCHER_PROTOCOL_LABEL,
    KUBERNETES_MANAGED_BY_LABEL,
    KUBERNETES_SATELLITE_LABEL,
    KUBERNETES_SHARED_LABEL,
    MODEL_ARTIFACT_ID,
    MODEL_ARTIFACT_TOKEN,
    MODEL_NAME,
    SATELLITE_ADDRESS,
    TELEMETRY_ENDPOINT,
    ContainerResources,
    build_container_environment,
    docker_labels,
    kubernetes_labels,
)
from tests.helpers import ARTIFACT_ID, deployment_record


def test_environment_precedence_and_reserved_names(caplog: pytest.LogCaptureFixture) -> None:
    deployment = Deployment.model_validate(
        deployment_record(
            env_variables_secrets={"FROM_SECRET": "secret-id"},
            env_variables={
                "FROM_SECRET": "plain-wins",
                "PLAIN": "value",
                MODEL_ARTIFACT_ID: "wrong-artifact",
                SATELLITE_ADDRESS: "wrong-address",
            },
        )
    )

    with caplog.at_level(logging.WARNING, logger="test.environment"):
        environment = build_container_environment(
            deployment,
            {"FROM_SECRET": "resolved-secret", "SECRET_ONLY": "secret-value"},
            telemetry_endpoint="http://collector:4317",
            artifact_token="artifact-token",
            satellite_address="http://satellite:8000",
            logger=logging.getLogger("test.environment"),
        )

    assert environment == {
        "FROM_SECRET": "plain-wins",
        "SECRET_ONLY": "secret-value",
        "PLAIN": "value",
        MODEL_ARTIFACT_ID: ARTIFACT_ID,
        DEPLOYMENT_ID: deployment.id,
        MODEL_NAME: deployment.artifact_name,
        TELEMETRY_ENDPOINT: "http://collector:4317",
        MODEL_ARTIFACT_TOKEN: "artifact-token",
        SATELLITE_ADDRESS: "http://satellite:8000",
    }
    assert "MODEL_ARTIFACT_ID" in caplog.text
    assert "SATELLITE_AGENT_URL" in caplog.text


def test_environment_omits_optional_reserved_values() -> None:
    deployment = Deployment.model_validate(deployment_record())

    environment = build_container_environment(deployment, {})

    assert SATELLITE_ADDRESS not in environment
    assert MODEL_ARTIFACT_TOKEN not in environment
    assert TELEMETRY_ENDPOINT not in environment


def test_docker_and_kubernetes_label_sets_carry_ownership() -> None:
    docker = docker_labels(
        deployment_id="deployment",
        artifact_id="artifact",
        satellite_id="satellite",
        launcher_protocol="3",
    )
    kubernetes = kubernetes_labels(
        deployment_id="deployment",
        artifact_id="artifact",
        satellite_id="release",
        launcher_protocol="1",
        derivation_key_fingerprint="abcdef",
        shared=True,
    )

    assert docker == {
        DOCKER_DEPLOYMENT_LABEL: "deployment",
        DOCKER_ARTIFACT_LABEL: "artifact",
        DOCKER_SATELLITE_LABEL: "satellite",
        DOCKER_LAUNCHER_PROTOCOL_LABEL: "3",
    }
    assert kubernetes == {
        KUBERNETES_MANAGED_BY_LABEL: "luml-satellite",
        KUBERNETES_DEPLOYMENT_LABEL: "deployment",
        KUBERNETES_ARTIFACT_LABEL: "artifact",
        KUBERNETES_SATELLITE_LABEL: "release",
        KUBERNETES_LAUNCHER_PROTOCOL_LABEL: "1",
        KUBERNETES_DERIVATION_FINGERPRINT_LABEL: "abcdef",
        KUBERNETES_SHARED_LABEL: "true",
    }


def test_container_resources_reject_invalid_values() -> None:
    assert ContainerResources(cpu_millicores=1000, memory="2Gi", gpu_count=1)
    with pytest.raises(ValueError, match="cpu_millicores"):
        ContainerResources(cpu_millicores=0)
    with pytest.raises(ValueError, match="gpu_count"):
        ContainerResources(gpu_count=-1)
