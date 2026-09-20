import re
from typing import Any, Literal, Self

from luml_satellite import SatelliteConfiguration
from pydantic import Field, model_validator

DEFAULT_MEMORY_VALUES = (
    "512Mi",
    "1Gi",
    "2Gi",
    "4Gi",
    "8Gi",
    "16Gi",
    "32Gi",
    "64Gi",
)
PLATFORM_INTEGER_MAX = 2_147_483_647

_KUBERNETES_QUANTITY = re.compile(
    r"^(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)(?:[EPTGMK]i?|[eE][+-]?[0-9]+|[numk])?$"
)


class KubernetesConfiguration(SatelliteConfiguration):
    BASE_URL: str = "http://localhost"
    SATELLITE_SLUG: str = Field(default="kubernetes-2026.01-v1", min_length=1)
    NAMESPACE: str = Field(default="default", min_length=1)
    SATELLITE_NAME: str = Field(default="luml", min_length=1)
    SATELLITE_INTERNAL_URL: str = "http://luml-satellite:8001"
    INTERNAL_PORT: int = Field(default=8001, ge=1, le=65535)

    MODEL_IMAGE: str = Field(default="luml-model-server:latest", min_length=1)
    MODEL_IMAGE_PULL_POLICY: Literal["Always", "IfNotPresent", "Never"] = "IfNotPresent"
    SERVING_IMAGE: str = Field(default="ghcr.io/luml-ai/luml-satellite-serving:dev", min_length=1)
    SERVING_IMAGE_PULL_POLICY: Literal["Always", "IfNotPresent", "Never"] = "IfNotPresent"
    MODEL_SERVER_PORT: int = Field(default=8080, ge=1, le=65535)
    SERVING_PORT: int = Field(default=8000, ge=1, le=65535)
    INGRESS_HOST: str = Field(default="localhost", min_length=1)
    INGRESS_CLASS: str | None = None
    INGRESS_ANNOTATIONS: dict[str, str] = Field(default_factory=dict)
    INGRESS_TLS_SECRET: str | None = None
    MONITORING_PATHS_ROUTED: bool = True
    MONITORING_DASHBOARD_SERVICE: str | None = None

    DEPLOYMENT_REPLICAS_MAX: int = 64
    DEPLOYMENT_REPLICAS_DEFAULT: int = 1
    DEPLOYMENT_CPU_MIN_MILLICORES: int = 100
    DEPLOYMENT_CPU_MAX_MILLICORES: int = 64_000
    DEPLOYMENT_CPU_DEFAULT_MILLICORES: int = 1_000
    DEPLOYMENT_MEMORY_VALUES: list[str] = Field(default_factory=lambda: list(DEFAULT_MEMORY_VALUES))
    DEPLOYMENT_MEMORY_DEFAULT: str = "2Gi"
    DEPLOYMENT_HEALTH_TIMEOUT_MIN: int = 60
    DEPLOYMENT_HEALTH_TIMEOUT_MAX: int = 7_200
    DEPLOYMENT_HEALTH_TIMEOUT_DEFAULT: int = 1_800

    GPU_OFFERED: bool = False
    GPU_COUNT_MAX: int = 8
    GPU_RESOURCE_NAMES: list[str] = Field(default_factory=lambda: ["nvidia.com/gpu", "amd.com/gpu"])
    GPU_NODE_SELECTOR: dict[str, str] = Field(default_factory=dict)
    GPU_TOLERATIONS: list[dict[str, Any]] = Field(default_factory=list)
    GPU_RUNTIME_CLASS: str | None = None
    SHARED_CACHE_CLAIM_NAME: str | None = None

    SECURITY_PRESET: Literal["vanilla", "openshift"] = "vanilla"
    POD_SECURITY_CONTEXT: dict[str, Any] | None = None
    CONTAINER_SECURITY_CONTEXT: dict[str, Any] | None = None
    IMAGE_PULL_SECRETS: list[str] = Field(default_factory=list)
    SIDECAR_RESOURCES: dict[str, Any] = Field(default_factory=dict)
    SIDECAR_CACHE_TTL_SEC: float = Field(default=60.0, gt=15.0)
    SIDECAR_STALE_ALLOWANCE_SEC: float = Field(default=600.0, ge=0.0)

    KUBERNETES_FIELD_MANAGER: str = "luml-satellite"
    REMOVAL_TIMEOUT_SEC: float = Field(default=60.0, ge=0)
    REMOVAL_POLL_INTERVAL_SEC: float = Field(default=1.0, gt=0)

    @model_validator(mode="after")
    def validate_deployment_limits(self) -> Self:
        self._validate_range(
            "DEPLOYMENT_REPLICAS",
            1,
            self.DEPLOYMENT_REPLICAS_MAX,
            self.DEPLOYMENT_REPLICAS_DEFAULT,
        )
        self._validate_range(
            "DEPLOYMENT_CPU_MILLICORES",
            self.DEPLOYMENT_CPU_MIN_MILLICORES,
            self.DEPLOYMENT_CPU_MAX_MILLICORES,
            self.DEPLOYMENT_CPU_DEFAULT_MILLICORES,
        )
        self._validate_range(
            "DEPLOYMENT_HEALTH_TIMEOUT",
            self.DEPLOYMENT_HEALTH_TIMEOUT_MIN,
            self.DEPLOYMENT_HEALTH_TIMEOUT_MAX,
            self.DEPLOYMENT_HEALTH_TIMEOUT_DEFAULT,
        )
        if not self.DEPLOYMENT_MEMORY_VALUES:
            raise ValueError("DEPLOYMENT_MEMORY_VALUES must not be empty")
        if len(set(self.DEPLOYMENT_MEMORY_VALUES)) != len(self.DEPLOYMENT_MEMORY_VALUES):
            raise ValueError("DEPLOYMENT_MEMORY_VALUES contains duplicate values")
        for value in self.DEPLOYMENT_MEMORY_VALUES:
            if not _is_kubernetes_quantity(value):
                raise ValueError(f"DEPLOYMENT_MEMORY_VALUES contains invalid quantity {value!r}")
        if self.DEPLOYMENT_MEMORY_DEFAULT not in self.DEPLOYMENT_MEMORY_VALUES:
            raise ValueError(
                "DEPLOYMENT_MEMORY_DEFAULT="
                f"{self.DEPLOYMENT_MEMORY_DEFAULT!r} is not in DEPLOYMENT_MEMORY_VALUES"
            )
        if self.GPU_COUNT_MAX < 1:
            raise ValueError(f"GPU_COUNT_MAX={self.GPU_COUNT_MAX} must be at least 1")
        _validate_platform_integer("GPU_COUNT_MAX", self.GPU_COUNT_MAX)
        if self.GPU_OFFERED and not self.GPU_RESOURCE_NAMES:
            raise ValueError("GPU_RESOURCE_NAMES must not be empty when GPU_OFFERED is true")
        if any(not name for name in self.GPU_RESOURCE_NAMES):
            raise ValueError("GPU_RESOURCE_NAMES must not contain an empty value")
        if len(set(self.GPU_RESOURCE_NAMES)) != len(self.GPU_RESOURCE_NAMES):
            raise ValueError("GPU_RESOURCE_NAMES contains duplicate values")
        if self.SERVING_PORT == self.INTERNAL_PORT:
            raise ValueError("SERVING_PORT and INTERNAL_PORT must differ")
        return self

    @property
    def pod_security_context(self) -> dict[str, Any]:
        if self.POD_SECURITY_CONTEXT is not None:
            return dict(self.POD_SECURITY_CONTEXT)
        context: dict[str, Any] = {
            "runAsNonRoot": True,
            "seccompProfile": {"type": "RuntimeDefault"},
        }
        if self.SECURITY_PRESET == "vanilla":
            context.update({"runAsUser": 10001, "runAsGroup": 0, "fsGroup": 10001})
        return context

    @property
    def container_security_context(self) -> dict[str, Any]:
        if self.CONTAINER_SECURITY_CONTEXT is not None:
            return dict(self.CONTAINER_SECURITY_CONTEXT)
        return {
            "runAsNonRoot": True,
            "allowPrivilegeEscalation": False,
            "capabilities": {"drop": ["ALL"]},
        }

    @property
    def monitoring_dashboard_service(self) -> str:
        return self.MONITORING_DASHBOARD_SERVICE or f"{self.SATELLITE_NAME}-dashboard"

    @staticmethod
    def _validate_range(name: str, minimum: int, maximum: int, default: int) -> None:
        _validate_platform_integer(f"{name}_MAX", maximum)
        if minimum < 1:
            raise ValueError(f"{name}_MIN={minimum} must be at least 1")
        if minimum > maximum:
            raise ValueError(f"{name}_MIN={minimum} exceeds {name}_MAX={maximum}")
        if not minimum <= default <= maximum:
            raise ValueError(f"{name}_DEFAULT={default} is outside the range {minimum}..{maximum}")


def _validate_platform_integer(name: str, value: int) -> None:
    if value > PLATFORM_INTEGER_MAX:
        raise ValueError(f"{name}={value} exceeds the platform integer range")


def _is_kubernetes_quantity(value: str) -> bool:
    return bool(_KUBERNETES_QUANTITY.fullmatch(value))
