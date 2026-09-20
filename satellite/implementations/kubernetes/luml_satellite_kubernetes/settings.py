from typing import Any, Literal

from luml_satellite import (
    DeploymentSettings,
    DropdownValue,
    FieldCondition,
    SettingsValidator,
    setting_field,
)
from pydantic import create_model

from luml_satellite_kubernetes.configuration import KubernetesConfiguration


class KubernetesDeploymentSettings(DeploymentSettings):
    replicas: int = setting_field(1, ge=1, le=64)
    cpu_millicores: int = setting_field(1_000, ge=100, le=64_000)
    memory: str = setting_field(
        "2Gi",
        values=[
            DropdownValue("512 MiB", "512Mi"),
            DropdownValue("1 GiB", "1Gi"),
            DropdownValue("2 GiB", "2Gi"),
            DropdownValue("4 GiB", "4Gi"),
            DropdownValue("8 GiB", "8Gi"),
            DropdownValue("16 GiB", "16Gi"),
            DropdownValue("32 GiB", "32Gi"),
            DropdownValue("64 GiB", "64Gi"),
        ],
    )
    use_gpu: bool = setting_field(False)
    gpu_count: int = setting_field(
        1,
        ge=1,
        le=8,
        conditions=[FieldCondition("use_gpu", "equal", True)],
    )
    gpu_resource_name: str = setting_field(
        "nvidia.com/gpu",
        values=[
            DropdownValue("NVIDIA", "nvidia.com/gpu"),
            DropdownValue("AMD", "amd.com/gpu"),
        ],
        conditions=[FieldCondition("use_gpu", "equal", True)],
    )
    artifact_cache: Literal["ephemeral", "shared"] = setting_field("ephemeral")
    health_check_timeout: int = setting_field(1_800, ge=60, le=7_200)
    log_level: str = setting_field(
        "info",
        values=[
            DropdownValue("Debug", "debug"),
            DropdownValue("Info", "info"),
            DropdownValue("Warning", "warning"),
            DropdownValue("Error", "error"),
        ],
    )


def build_settings_model(
    configuration: KubernetesConfiguration,
) -> type[KubernetesDeploymentSettings]:
    gpu_condition = [FieldCondition("use_gpu", "equal", True)]
    default_gpu_resource = (
        configuration.GPU_RESOURCE_NAMES[0]
        if configuration.GPU_RESOURCE_NAMES
        else "nvidia.com/gpu"
    )
    fields: dict[str, Any] = {
        "replicas": (
            int,
            setting_field(
                configuration.DEPLOYMENT_REPLICAS_DEFAULT,
                ge=1,
                le=configuration.DEPLOYMENT_REPLICAS_MAX,
            ),
        ),
        "cpu_millicores": (
            int,
            setting_field(
                configuration.DEPLOYMENT_CPU_DEFAULT_MILLICORES,
                ge=configuration.DEPLOYMENT_CPU_MIN_MILLICORES,
                le=configuration.DEPLOYMENT_CPU_MAX_MILLICORES,
            ),
        ),
        "memory": (
            str,
            setting_field(
                configuration.DEPLOYMENT_MEMORY_DEFAULT,
                exposed=len(configuration.DEPLOYMENT_MEMORY_VALUES) > 1,
                values=[_memory_option(value) for value in configuration.DEPLOYMENT_MEMORY_VALUES],
            ),
        ),
        "health_check_timeout": (
            int,
            setting_field(
                configuration.DEPLOYMENT_HEALTH_TIMEOUT_DEFAULT,
                ge=configuration.DEPLOYMENT_HEALTH_TIMEOUT_MIN,
                le=configuration.DEPLOYMENT_HEALTH_TIMEOUT_MAX,
            ),
        ),
        "log_level": (
            str,
            setting_field(
                "info",
                values=[
                    DropdownValue("Debug", "debug"),
                    DropdownValue("Info", "info"),
                    DropdownValue("Warning", "warning"),
                    DropdownValue("Error", "error"),
                ],
            ),
        ),
    }
    if configuration.GPU_OFFERED:
        fields.update(
            {
                "use_gpu": (bool, setting_field(False)),
                "gpu_count": (
                    int,
                    setting_field(
                        1,
                        ge=1,
                        le=configuration.GPU_COUNT_MAX,
                        conditions=gpu_condition,
                    ),
                ),
                "gpu_resource_name": (
                    str,
                    setting_field(
                        default_gpu_resource,
                        exposed=len(configuration.GPU_RESOURCE_NAMES) > 1,
                        values=[_gpu_option(value) for value in configuration.GPU_RESOURCE_NAMES],
                        conditions=gpu_condition,
                    ),
                ),
            }
        )
    else:
        fields.update(
            {
                "use_gpu": (
                    bool,
                    setting_field(
                        False,
                        exposed=False,
                        validators=[SettingsValidator("equal", False)],
                    ),
                ),
                "gpu_count": (
                    int,
                    setting_field(
                        1,
                        exposed=False,
                        validators=[SettingsValidator("equal", 1)],
                    ),
                ),
                "gpu_resource_name": (
                    str,
                    setting_field(
                        default_gpu_resource,
                        exposed=False,
                        values=[_gpu_option(default_gpu_resource)],
                    ),
                ),
            }
        )
    if configuration.SHARED_CACHE_CLAIM_NAME is None:
        fields["artifact_cache"] = (
            str,
            setting_field(
                "ephemeral",
                exposed=False,
                values=[DropdownValue("Ephemeral", "ephemeral")],
            ),
        )
    else:
        fields["artifact_cache"] = (
            str,
            setting_field(
                "ephemeral",
                values=[
                    DropdownValue("Ephemeral", "ephemeral"),
                    DropdownValue("Shared", "shared"),
                ],
            ),
        )

    model = create_model(
        "ConfiguredKubernetesDeploymentSettings",
        __base__=KubernetesDeploymentSettings,
        __module__=__name__,
        **fields,
    )
    return model


def _memory_option(value: str) -> DropdownValue:
    labels = {
        "512Mi": "512 MiB",
        "1Gi": "1 GiB",
        "2Gi": "2 GiB",
        "4Gi": "4 GiB",
        "8Gi": "8 GiB",
        "16Gi": "16 GiB",
        "32Gi": "32 GiB",
        "64Gi": "64 GiB",
    }
    return DropdownValue(labels.get(value, value), value)


def _gpu_option(value: str) -> DropdownValue:
    labels = {"nvidia.com/gpu": "NVIDIA", "amd.com/gpu": "AMD"}
    return DropdownValue(labels.get(value, value), value)
