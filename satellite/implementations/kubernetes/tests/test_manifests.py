from typing import Any, cast

from luml_satellite import TokenDeriver
from luml_satellite.container import (
    DEPLOYMENT_ID as DEPLOYMENT_ID_ENV,
    KUBERNETES_DERIVATION_FINGERPRINT_LABEL,
    MODEL_ARTIFACT_ID,
    MODEL_ARTIFACT_TOKEN,
    MODEL_NAME,
    SATELLITE_ADDRESS,
    TELEMETRY_ENDPOINT,
)

from luml_satellite_kubernetes.manifests import render_deployment_manifests
from tests.support import (
    DEPLOYMENT_ID,
    DERIVATION_KEY,
    configuration,
    container_by_name,
    deployment,
    env_by_name,
    init_container,
    start_context,
)


def test_default_manifests_match_the_no_gpu_ephemeral_golden_projection() -> None:
    config = configuration(MONITORING_PATHS_ROUTED=False)
    manifests = render_deployment_manifests(
        config,
        deployment(),
        start_context(config),
        TokenDeriver(config.SATELLITE_TOKEN, config.DERIVATION_KEY),
    )
    workload = manifests.deployment
    pod_spec = workload["spec"]["template"]["spec"]
    model = container_by_name(workload, "model")

    assert [item["kind"] for item in manifests.objects()] == [
        "Secret",
        "Deployment",
        "Service",
        "Ingress",
    ]
    assert {item["metadata"]["name"] for item in manifests.objects()} == {
        f"luml-dep-{DEPLOYMENT_ID}"
    }
    assert workload["spec"]["replicas"] == 1
    assert model["resources"] == {"limits": {"cpu": "1000m", "memory": "2Gi"}}
    assert pod_spec["volumes"] == [{"name": "model-cache", "emptyDir": {}}]
    assert pod_spec["securityContext"] == {
        "runAsNonRoot": True,
        "seccompProfile": {"type": "RuntimeDefault"},
        "runAsUser": 10001,
        "runAsGroup": 0,
        "fsGroup": 10001,
    }
    assert "nodeSelector" not in pod_spec
    assert "tolerations" not in pod_spec
    assert "runtimeClassName" not in pod_spec
    assert [path["path"] for path in _ingress_paths(manifests.ingress)] == [
        f"/deployments/{DEPLOYMENT_ID}"
    ]
    assert [port["name"] for port in manifests.service["spec"]["ports"]] == [
        "http",
        "internal",
    ]


def test_gpu_shared_cache_and_replica_manifests_match_the_golden_projection() -> None:
    config = configuration(
        GPU_OFFERED=True,
        SHARED_CACHE_CLAIM_NAME="release-one-model-cache",
        MODEL_IMAGE_PULL_POLICY="Always",
        SERVING_IMAGE_PULL_POLICY="Never",
        IMAGE_PULL_SECRETS=["private-registry"],
        SIDECAR_CACHE_TTL_SEC=90,
        SIDECAR_STALE_ALLOWANCE_SEC=900,
        GPU_NODE_SELECTOR={"accelerator": "amd"},
        GPU_TOLERATIONS=[{"key": "gpu", "operator": "Exists", "effect": "NoSchedule"}],
        GPU_RUNTIME_CLASS="gpu-runtime",
    )
    record = deployment(
        env_variables={"PLAIN": "value", MODEL_NAME: "ignored"},
    )
    context = start_context(
        config,
        parameters={
            "replicas": 3,
            "cpu_millicores": 1_500,
            "memory": "4Gi",
            "use_gpu": True,
            "gpu_count": 2,
            "gpu_resource_name": "amd.com/gpu",
            "artifact_cache": "shared",
            "log_level": "debug",
        },
        secrets={"SECRET": "resolved"},
    )
    manifests = render_deployment_manifests(
        config,
        record,
        context,
        TokenDeriver(config.SATELLITE_TOKEN, config.DERIVATION_KEY),
    )
    workload = manifests.deployment
    pod_spec = workload["spec"]["template"]["spec"]
    model = container_by_name(workload, "model")
    sidecar = container_by_name(workload, "sidecar")
    fetch = init_container(workload)

    assert workload["spec"]["replicas"] == 3
    assert model["resources"] == {"limits": {"cpu": "1500m", "memory": "4Gi", "amd.com/gpu": 2}}
    assert pod_spec["volumes"] == [
        {
            "name": "model-cache",
            "persistentVolumeClaim": {"claimName": "release-one-model-cache"},
        }
    ]
    assert pod_spec["nodeSelector"] == {"accelerator": "amd"}
    assert pod_spec["tolerations"] == [{"key": "gpu", "operator": "Exists", "effect": "NoSchedule"}]
    assert pod_spec["runtimeClassName"] == "gpu-runtime"
    assert pod_spec["imagePullSecrets"] == [{"name": "private-registry"}]
    assert model["imagePullPolicy"] == "Always"
    assert fetch["imagePullPolicy"] == "Never"
    assert sidecar["imagePullPolicy"] == "Never"
    assert [path["path"] for path in _ingress_paths(manifests.ingress)] == [
        f"/deployments/{DEPLOYMENT_ID}/monitoring",
        f"/deployments/{DEPLOYMENT_ID}",
    ]

    model_env = env_by_name(model)
    init_env = env_by_name(fetch)
    sidecar_env = env_by_name(sidecar)
    assert {
        MODEL_NAME,
        DEPLOYMENT_ID_ENV,
        MODEL_ARTIFACT_ID,
        TELEMETRY_ENDPOINT,
    } <= model_env.keys()
    assert {SATELLITE_ADDRESS, MODEL_ARTIFACT_TOKEN, "MODEL_ARTIFACT_URL"}.isdisjoint(model_env)
    assert "COMPANION_TOKEN" not in model_env
    assert "MODEL_ARTIFACT_URL" in init_env
    assert MODEL_ARTIFACT_TOKEN in init_env
    assert "COMPANION_TOKEN" in sidecar_env
    assert "MODEL_ARTIFACT_URL" not in sidecar_env
    assert "SATELLITE_TOKEN" not in sidecar_env
    assert "DERIVATION_KEY" not in sidecar_env
    assert sidecar_env["LOG_LEVEL"]["value"] == "debug"
    assert sidecar_env["COMPANION_CACHE_TTL_SECONDS"]["value"] == "90.0"
    assert sidecar_env["COMPANION_STALE_ALLOWANCE_SECONDS"]["value"] == "900.0"
    for container in [fetch, model, sidecar]:
        assert container["securityContext"]["capabilities"] == {"drop": ["ALL"]}
        assert container["securityContext"]["allowPrivilegeEscalation"] is False


def test_secret_hash_ignores_fresh_links_and_reissued_satellite_tokens() -> None:
    first_config = configuration(SATELLITE_TOKEN="first-token")
    second_config = configuration(SATELLITE_TOKEN="second-token")
    first = render_deployment_manifests(
        first_config,
        deployment(),
        start_context(
            first_config,
            download_url="https://artifacts.example/first",
            satellite_token="first-token",
        ),
        TokenDeriver("first-token", DERIVATION_KEY),
    )
    second = render_deployment_manifests(
        second_config,
        deployment(),
        start_context(
            second_config,
            download_url="https://artifacts.example/second",
            satellite_token="second-token",
        ),
        TokenDeriver("second-token", DERIVATION_KEY),
    )

    assert _secret_hash(first.deployment) == _secret_hash(second.deployment)
    assert (
        first.secret["stringData"]["artifact-token"]
        == second.secret["stringData"]["artifact-token"]
    )
    assert (
        first.secret["stringData"]["companion-token"]
        == second.secret["stringData"]["companion-token"]
    )
    assert first.secret["stringData"]["artifact-url"] != second.secret["stringData"]["artifact-url"]


def test_rotating_the_derivation_key_changes_tokens_fingerprint_and_secret_hash() -> None:
    config = configuration()
    first = render_deployment_manifests(
        config,
        deployment(),
        start_context(config, derivation_key="first-key"),
        TokenDeriver(config.SATELLITE_TOKEN, "first-key"),
    )
    second = render_deployment_manifests(
        config,
        deployment(),
        start_context(config, derivation_key="second-key"),
        TokenDeriver(config.SATELLITE_TOKEN, "second-key"),
    )

    assert _secret_hash(first.deployment) != _secret_hash(second.deployment)
    assert (
        first.secret["stringData"]["artifact-token"]
        != second.secret["stringData"]["artifact-token"]
    )
    assert (
        first.secret["stringData"]["companion-token"]
        != second.secret["stringData"]["companion-token"]
    )
    first_label = first.deployment["metadata"]["labels"][KUBERNETES_DERIVATION_FINGERPRINT_LABEL]
    second_label = second.deployment["metadata"]["labels"][KUBERNETES_DERIVATION_FINGERPRINT_LABEL]
    assert first_label != second_label


def test_openshift_preset_pins_no_user_or_group() -> None:
    config = configuration(SECURITY_PRESET="openshift")
    manifests = render_deployment_manifests(
        config,
        deployment(),
        start_context(config),
        TokenDeriver(config.SATELLITE_TOKEN, config.DERIVATION_KEY),
    )
    pod_context = manifests.deployment["spec"]["template"]["spec"]["securityContext"]

    assert pod_context == {
        "runAsNonRoot": True,
        "seccompProfile": {"type": "RuntimeDefault"},
    }
    assert not {"runAsUser", "runAsGroup", "fsGroup"} & pod_context.keys()


def _ingress_paths(ingress: dict[str, Any]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], ingress["spec"]["rules"][0]["http"]["paths"])


def _secret_hash(workload: dict[str, Any]) -> str:
    return cast(
        str,
        workload["spec"]["template"]["metadata"]["annotations"]["luml.ai/secret-hash"],
    )


def test_model_and_sidecar_probes_carry_the_configured_timeout() -> None:
    config = configuration(PROBE_TIMEOUT_SEC=12)
    manifests = render_deployment_manifests(
        config,
        deployment(),
        start_context(config),
        TokenDeriver(config.SATELLITE_TOKEN, config.DERIVATION_KEY),
    )
    workload = manifests.deployment

    assert container_by_name(workload, "model")["readinessProbe"]["timeoutSeconds"] == 12
    assert container_by_name(workload, "sidecar")["readinessProbe"]["timeoutSeconds"] == 12
