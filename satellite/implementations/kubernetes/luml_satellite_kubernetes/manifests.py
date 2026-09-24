import hashlib
import json
from dataclasses import dataclass
from typing import Any, cast

from luml_satellite import (
    Deployment,
    StartContext,
    TokenDeriver,
    build_container_environment,
    kubernetes_labels,
)
from luml_satellite.container import (
    KUBERNETES_MANAGED_BY_LABEL,
    KUBERNETES_SATELLITE_LABEL,
    KUBERNETES_SHARED_LABEL,
)

from luml_satellite_kubernetes.configuration import KubernetesConfiguration
from luml_satellite_kubernetes.settings import KubernetesDeploymentSettings

MODEL_CACHE_PATH = "/app/models"


@dataclass(frozen=True)
class DeploymentManifests:
    secret: dict[str, Any]
    deployment: dict[str, Any]
    service: dict[str, Any]
    ingress: dict[str, Any]

    def objects(self) -> tuple[dict[str, Any], ...]:
        return (self.secret, self.deployment, self.service, self.ingress)


def deployment_object_name(deployment_id: str) -> str:
    return f"luml-dep-{deployment_id.lower()}"


def _suffixed_object_name(prefix: str, suffix: str) -> str:
    candidate = f"{prefix}-{suffix}"
    if len(candidate) <= 63:
        return candidate
    digest = hashlib.sha256(prefix.encode()).hexdigest()[:8]
    prefix_length = 63 - len(suffix) - len(digest) - 2
    return f"{prefix[:prefix_length].rstrip('-')}-{digest}-{suffix}"


def render_deployment_manifests(
    configuration: KubernetesConfiguration,
    deployment: Deployment,
    context: StartContext,
    token_deriver: TokenDeriver,
) -> DeploymentManifests:
    settings = cast(KubernetesDeploymentSettings, context.settings)
    deployment_id = str(deployment.id)
    artifact_id = str(deployment.artifact_id)
    name = deployment_object_name(deployment_id)
    labels = kubernetes_labels(
        deployment_id=deployment_id,
        artifact_id=artifact_id,
        satellite_id=configuration.SATELLITE_NAME,
        launcher_protocol="1",
        derivation_key_fingerprint=token_deriver.fingerprint,
        spec_fingerprint=configuration.workload_spec_fingerprint,
    )
    model_environment = build_container_environment(
        deployment,
        context.secrets,
        telemetry_endpoint=context.telemetry_endpoint,
    )
    companion_token = token_deriver.companion_token(deployment_id)
    artifact_token = context.artifact.token or token_deriver.artifact_token(deployment_id)
    secret_data = {
        **{_model_secret_key(key): value for key, value in model_environment.items()},
        "artifact-url": context.artifact.download_url or "",
        "artifact-token": artifact_token,
        "companion-token": companion_token,
    }
    secret_hash = _stable_secret_hash(
        model_environment,
        artifact_token=artifact_token,
        companion_token=companion_token,
    )
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": _metadata(name, configuration.NAMESPACE, labels),
        "type": "Opaque",
        "stringData": secret_data,
    }

    cache_volume = _cache_volume(configuration, settings)
    init_container = {
        "name": "artifact-fetch",
        "image": configuration.SERVING_IMAGE,
        "imagePullPolicy": configuration.SERVING_IMAGE_PULL_POLICY,
        "command": ["luml-artifact-fetch"],
        "env": [
            _literal_env("MODEL_ARTIFACT_ID", artifact_id),
            _secret_env("MODEL_ARTIFACT_URL", name, "artifact-url"),
            _literal_env("SATELLITE_AGENT_URL", configuration.SATELLITE_INTERNAL_URL),
            _literal_env("DEPLOYMENT_ID", deployment_id),
            _secret_env("MODEL_ARTIFACT_TOKEN", name, "artifact-token"),
        ],
        "volumeMounts": [{"name": "model-cache", "mountPath": MODEL_CACHE_PATH}],
        "securityContext": configuration.container_security_context,
    }
    model_container = {
        "name": "model",
        "image": configuration.MODEL_IMAGE,
        "imagePullPolicy": configuration.MODEL_IMAGE_PULL_POLICY,
        "env": [
            _secret_env(key, name, _model_secret_key(key)) for key in sorted(model_environment)
        ],
        "ports": [{"name": "model", "containerPort": configuration.MODEL_SERVER_PORT}],
        "readinessProbe": {
            "httpGet": {"path": "/healthz", "port": "model"},
            "periodSeconds": 5,
            "timeoutSeconds": configuration.PROBE_TIMEOUT_SEC,
            "failureThreshold": configuration.PROBE_FAILURE_THRESHOLD,
        },
        "resources": {"limits": _model_limits(settings)},
        "volumeMounts": [{"name": "model-cache", "mountPath": MODEL_CACHE_PATH}],
        "securityContext": configuration.container_security_context,
    }
    sidecar = {
        "name": "sidecar",
        "image": configuration.SERVING_IMAGE,
        "imagePullPolicy": configuration.SERVING_IMAGE_PULL_POLICY,
        "env": [
            _literal_env("DEPLOYMENT_ID", deployment_id),
            _literal_env("SATELLITE_INTERNAL_URL", configuration.SATELLITE_INTERNAL_URL),
            _secret_env("COMPANION_TOKEN", name, "companion-token"),
            _literal_env(
                "UPSTREAM_MODEL_URL",
                f"http://127.0.0.1:{configuration.MODEL_SERVER_PORT}",
            ),
            _literal_env("SERVING_PORT", str(configuration.SERVING_PORT)),
            _literal_env("INTERNAL_PORT", str(configuration.INTERNAL_PORT)),
            _literal_env(
                "COMPANION_CACHE_TTL_SECONDS",
                str(configuration.SIDECAR_CACHE_TTL_SEC),
            ),
            _literal_env(
                "COMPANION_STALE_ALLOWANCE_SECONDS",
                str(configuration.SIDECAR_STALE_ALLOWANCE_SEC),
            ),
            _literal_env("LOG_LEVEL", settings.log_level),
            _literal_env("RECORDING_SAMPLE_RATE", str(context.recording_policy.sample_rate)),
            _literal_env(
                "RECORDING_BODY_MAX_BYTES",
                str(context.recording_policy.body_max_bytes),
            ),
            _literal_env(
                "RECORDING_KEEP_INPUTS",
                str(context.recording_policy.keep_inputs).lower(),
            ),
            _literal_env(
                "RECORDING_KEEP_OUTPUTS",
                str(context.recording_policy.keep_outputs).lower(),
            ),
            *(
                [_literal_env("OTEL_EXPORTER_OTLP_ENDPOINT", context.telemetry_endpoint)]
                if context.telemetry_endpoint is not None
                else []
            ),
        ],
        "ports": [
            {"name": "http", "containerPort": configuration.SERVING_PORT},
            {"name": "internal", "containerPort": configuration.INTERNAL_PORT},
        ],
        "readinessProbe": {
            "httpGet": {"path": "/livez", "port": "http"},
            "periodSeconds": 5,
            "timeoutSeconds": configuration.PROBE_TIMEOUT_SEC,
            "failureThreshold": configuration.PROBE_FAILURE_THRESHOLD,
        },
        "resources": configuration.SIDECAR_RESOURCES,
        "securityContext": configuration.container_security_context,
    }
    pod_spec: dict[str, Any] = {
        "securityContext": configuration.pod_security_context,
        "initContainers": [init_container],
        "containers": [model_container, sidecar],
        "volumes": [cache_volume],
        "imagePullSecrets": [{"name": item} for item in configuration.IMAGE_PULL_SECRETS],
    }
    if settings.use_gpu:
        if configuration.GPU_NODE_SELECTOR:
            pod_spec["nodeSelector"] = dict(configuration.GPU_NODE_SELECTOR)
        if configuration.GPU_TOLERATIONS:
            pod_spec["tolerations"] = [dict(item) for item in configuration.GPU_TOLERATIONS]
        if configuration.GPU_RUNTIME_CLASS is not None:
            pod_spec["runtimeClassName"] = configuration.GPU_RUNTIME_CLASS

    workload = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": _metadata(name, configuration.NAMESPACE, labels),
        "spec": {
            "replicas": settings.replicas,
            "strategy": {
                "type": "RollingUpdate",
                "rollingUpdate": {"maxUnavailable": 0, "maxSurge": 1},
            },
            "selector": {"matchLabels": _selector_labels(labels)},
            "template": {
                "metadata": {
                    "labels": labels,
                    "annotations": {"luml.ai/secret-hash": secret_hash},
                },
                "spec": pod_spec,
            },
        },
    }
    service = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": _metadata(name, configuration.NAMESPACE, labels),
        "spec": {
            "type": "ClusterIP",
            "selector": _selector_labels(labels),
            "ports": [
                {
                    "name": "http",
                    "port": configuration.SERVING_PORT,
                    "targetPort": "http",
                },
                {
                    "name": "internal",
                    "port": configuration.INTERNAL_PORT,
                    "targetPort": "internal",
                },
            ],
        },
    }
    ingress = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": _metadata(
            name,
            configuration.NAMESPACE,
            labels,
            annotations=configuration.INGRESS_ANNOTATIONS,
        ),
        "spec": _ingress_spec(configuration, deployment_id, name),
    }
    return DeploymentManifests(secret, workload, service, ingress)


def render_cache_sweep_job(
    configuration: KubernetesConfiguration,
    artifact_ids: set[str],
) -> dict[str, Any]:
    if configuration.SHARED_CACHE_CLAIM_NAME is None:
        raise ValueError("a shared cache claim is required for a cache sweep")
    name = _suffixed_object_name(configuration.SATELLITE_NAME, "cache-sweep")
    labels = {
        KUBERNETES_MANAGED_BY_LABEL: "luml-satellite",
        KUBERNETES_SATELLITE_LABEL: configuration.SATELLITE_NAME,
        KUBERNETES_SHARED_LABEL: "true",
    }
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": _metadata(name, configuration.NAMESPACE, labels),
        "spec": {
            "ttlSecondsAfterFinished": 300,
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "restartPolicy": "Never",
                    "securityContext": configuration.pod_security_context,
                    "imagePullSecrets": [
                        {"name": item} for item in configuration.IMAGE_PULL_SECRETS
                    ],
                    "containers": [
                        {
                            "name": "cache-sweep",
                            "image": configuration.SERVING_IMAGE,
                            "imagePullPolicy": configuration.SERVING_IMAGE_PULL_POLICY,
                            "command": ["luml-artifact-fetch", "--sweep"],
                            "env": [
                                _literal_env(
                                    "MODEL_ARTIFACT_KEEP",
                                    ",".join(sorted(artifact_ids)),
                                )
                            ],
                            "volumeMounts": [
                                {"name": "model-cache", "mountPath": MODEL_CACHE_PATH}
                            ],
                            "securityContext": configuration.container_security_context,
                        }
                    ],
                    "volumes": [
                        {
                            "name": "model-cache",
                            "persistentVolumeClaim": {
                                "claimName": configuration.SHARED_CACHE_CLAIM_NAME
                            },
                        }
                    ],
                },
            },
        },
    }


def _metadata(
    name: str,
    namespace: str,
    labels: dict[str, str],
    *,
    annotations: dict[str, str] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "name": name,
        "namespace": namespace,
        "labels": dict(labels),
    }
    if annotations:
        metadata["annotations"] = dict(annotations)
    return metadata


def _selector_labels(labels: dict[str, str]) -> dict[str, str]:
    return {
        KUBERNETES_MANAGED_BY_LABEL: labels[KUBERNETES_MANAGED_BY_LABEL],
        "luml.ai/deployment-id": labels["luml.ai/deployment-id"],
        KUBERNETES_SATELLITE_LABEL: labels[KUBERNETES_SATELLITE_LABEL],
    }


def _model_secret_key(environment_name: str) -> str:
    return f"model.{environment_name}"


def _literal_env(name: str, value: str) -> dict[str, Any]:
    return {"name": name, "value": value}


def _secret_env(name: str, secret_name: str, key: str) -> dict[str, Any]:
    return {
        "name": name,
        "valueFrom": {"secretKeyRef": {"name": secret_name, "key": key}},
    }


def _stable_secret_hash(
    model_environment: dict[str, str],
    *,
    artifact_token: str,
    companion_token: str,
) -> str:
    stable = {
        "model_environment": model_environment,
        "artifact_token": artifact_token,
        "companion_token": companion_token,
    }
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _model_limits(settings: KubernetesDeploymentSettings) -> dict[str, object]:
    limits: dict[str, object] = {
        "cpu": f"{settings.cpu_millicores}m",
        "memory": settings.memory,
    }
    if settings.use_gpu:
        limits[settings.gpu_resource_name] = settings.gpu_count
    return limits


def _cache_volume(
    configuration: KubernetesConfiguration,
    settings: KubernetesDeploymentSettings,
) -> dict[str, Any]:
    if settings.artifact_cache == "shared" and configuration.SHARED_CACHE_CLAIM_NAME is not None:
        return {
            "name": "model-cache",
            "persistentVolumeClaim": {"claimName": configuration.SHARED_CACHE_CLAIM_NAME},
        }
    return {"name": "model-cache", "emptyDir": {}}


def _ingress_spec(
    configuration: KubernetesConfiguration,
    deployment_id: str,
    service_name: str,
) -> dict[str, Any]:
    paths: list[dict[str, Any]] = []
    if configuration.MONITORING_PATHS_ROUTED:
        paths.append(
            _ingress_path(
                f"/deployments/{deployment_id}/monitoring",
                configuration.monitoring_dashboard_service,
                configuration.SERVING_PORT,
            )
        )
    paths.append(
        _ingress_path(
            f"/deployments/{deployment_id}",
            service_name,
            configuration.SERVING_PORT,
        )
    )
    spec: dict[str, Any] = {
        "rules": [
            {
                "host": configuration.INGRESS_HOST,
                "http": {"paths": paths},
            }
        ]
    }
    if configuration.INGRESS_CLASS is not None:
        spec["ingressClassName"] = configuration.INGRESS_CLASS
    if configuration.INGRESS_TLS_SECRET is not None:
        spec["tls"] = [
            {
                "hosts": [configuration.INGRESS_HOST],
                "secretName": configuration.INGRESS_TLS_SECRET,
            }
        ]
    return spec


def _ingress_path(path: str, service_name: str, port: int) -> dict[str, Any]:
    return {
        "path": path,
        "pathType": "Prefix",
        "backend": {
            "service": {
                "name": service_name,
                "port": {"number": port},
            }
        },
    }
