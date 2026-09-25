import json
from pathlib import Path
from typing import cast

import pytest
from luml_satellite import SettingsValidationError, parse_settings, settings_fields
from pydantic import ValidationError

from luml_satellite_kubernetes import KubernetesConfiguration, build_settings_model
from luml_satellite_kubernetes.configuration import PLATFORM_INTEGER_MAX
from tests.support import configuration

SNAPSHOT = Path(__file__).parent / "snapshots" / "settings_fields.json"


def test_default_limits_build_the_declared_settings() -> None:
    model = build_settings_model(configuration(GPU_OFFERED=True))
    fields = {field["name"]: field for field in settings_fields(model)}

    assert fields["replicas"]["default"] == 1
    assert fields["replicas"]["validators"] == [
        {"type": "min", "value": 1},
        {"type": "max", "value": 64},
    ]
    assert fields["cpu_millicores"]["default"] == 1_000
    assert fields["memory"]["default"] == "2Gi"
    assert len(cast(list[object], fields["memory"]["values"])) == 8
    assert fields["use_gpu"]["default"] is False
    assert fields["gpu_count"]["conditions"] == [
        {
            "type": "field",
            "body": {"field": "use_gpu", "operator": "equal", "value": True},
        }
    ]
    assert fields["health_check_timeout"]["default"] == 1_800
    assert fields["log_level"]["values"] == [
        {"label": "Debug", "value": "debug"},
        {"label": "Info", "value": "info"},
        {"label": "Warning", "value": "warning"},
        {"label": "Error", "value": "error"},
    ]
    assert "artifact_cache" not in fields


def test_small_cluster_offers_only_values_it_can_run() -> None:
    config = configuration(
        DEPLOYMENT_REPLICAS_MAX=2,
        DEPLOYMENT_CPU_MAX_MILLICORES=4_000,
        DEPLOYMENT_CPU_DEFAULT_MILLICORES=500,
        DEPLOYMENT_MEMORY_VALUES=["512Mi", "1Gi", "2Gi"],
        DEPLOYMENT_MEMORY_DEFAULT="1Gi",
        GPU_OFFERED=False,
        SHARED_CACHE_CLAIM_NAME=None,
    )
    model = build_settings_model(config)
    fields = {field["name"]: field for field in settings_fields(model)}

    replica_validators = cast(list[dict[str, object]], fields["replicas"]["validators"])
    cpu_validators = cast(
        list[dict[str, object]],
        fields["cpu_millicores"]["validators"],
    )
    assert replica_validators[-1] == {"type": "max", "value": 2}
    assert fields["cpu_millicores"]["default"] == 500
    assert cpu_validators[-1] == {
        "type": "max",
        "value": 4_000,
    }
    assert fields["memory"]["values"] == [
        {"label": "512 MiB", "value": "512Mi"},
        {"label": "1 GiB", "value": "1Gi"},
        {"label": "2 GiB", "value": "2Gi"},
    ]
    assert fields["memory"]["default"] == "1Gi"
    assert not {"use_gpu", "gpu_count", "gpu_resource_name", "artifact_cache"} & fields.keys()

    with pytest.raises(SettingsValidationError) as cpu_error:
        parse_settings(model, {"cpu_millicores": 8_000})
    with pytest.raises(SettingsValidationError) as gpu_error:
        parse_settings(model, {"use_gpu": True})

    assert cpu_error.value.field == "cpu_millicores"
    assert gpu_error.value.field == "use_gpu"
    assert parse_settings(model, {"cpu_millicores": 2_000}).cpu_millicores == 2_000


def test_gpu_resource_names_may_be_empty_when_gpus_are_not_offered() -> None:
    model = build_settings_model(
        configuration(GPU_OFFERED=False, GPU_RESOURCE_NAMES=[]),
    )

    assert "gpu_resource_name" not in {field["name"] for field in settings_fields(model)}
    assert parse_settings(model, {}).use_gpu is False


def test_single_value_dropdowns_are_not_offered_but_reject_other_values() -> None:
    config = configuration(
        DEPLOYMENT_MEMORY_VALUES=["1Gi"],
        DEPLOYMENT_MEMORY_DEFAULT="1Gi",
        GPU_OFFERED=True,
        GPU_RESOURCE_NAMES=["nvidia.com/gpu"],
    )
    model = build_settings_model(config)
    field_names = {field["name"] for field in settings_fields(model)}

    assert "memory" not in field_names
    assert "gpu_resource_name" not in field_names
    assert parse_settings(model, {}).memory == "1Gi"
    assert parse_settings(model, {}).gpu_resource_name == "nvidia.com/gpu"

    with pytest.raises(SettingsValidationError) as memory_error:
        parse_settings(model, {"memory": "2Gi"})
    with pytest.raises(SettingsValidationError) as gpu_error:
        parse_settings(model, {"gpu_resource_name": "amd.com/gpu"})

    assert memory_error.value.field == "memory"
    assert gpu_error.value.field == "gpu_resource_name"


def test_shared_cache_is_offered_only_when_a_claim_exists() -> None:
    without_claim = build_settings_model(configuration(SHARED_CACHE_CLAIM_NAME=None))
    with_claim = build_settings_model(
        configuration(SHARED_CACHE_CLAIM_NAME="release-one-model-cache")
    )

    assert "artifact_cache" not in {field["name"] for field in settings_fields(without_claim)}
    cache = next(
        field for field in settings_fields(with_claim) if field["name"] == "artifact_cache"
    )
    assert cache["values"] == [
        {"label": "Ephemeral", "value": "ephemeral"},
        {"label": "Shared", "value": "shared"},
    ]
    assert cache["default"] == "ephemeral"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"DEPLOYMENT_CPU_MIN_MILLICORES": 5_000, "DEPLOYMENT_CPU_MAX_MILLICORES": 4_000},
            "DEPLOYMENT_CPU_MILLICORES_MIN=5000",
        ),
        (
            {"DEPLOYMENT_REPLICAS_MAX": 2, "DEPLOYMENT_REPLICAS_DEFAULT": 3},
            "DEPLOYMENT_REPLICAS_DEFAULT=3",
        ),
        (
            {"DEPLOYMENT_MEMORY_VALUES": ["512Mi"], "DEPLOYMENT_MEMORY_DEFAULT": "1Gi"},
            "DEPLOYMENT_MEMORY_DEFAULT='1Gi'",
        ),
        ({"DEPLOYMENT_MEMORY_VALUES": []}, "DEPLOYMENT_MEMORY_VALUES"),
        ({"DEPLOYMENT_MEMORY_VALUES": ["a-lot"]}, "a-lot"),
        ({"GPU_OFFERED": True, "GPU_RESOURCE_NAMES": []}, "GPU_RESOURCE_NAMES"),
        ({"GPU_COUNT_MAX": PLATFORM_INTEGER_MAX + 1}, "GPU_COUNT_MAX"),
        (
            {"DEPLOYMENT_REPLICAS_MAX": PLATFORM_INTEGER_MAX + 1},
            "DEPLOYMENT_REPLICAS_MAX",
        ),
        ({"SIDECAR_CACHE_TTL_SEC": 15}, "SIDECAR_CACHE_TTL_SEC"),
    ],
)
def test_contradictory_limits_stop_configuration(
    overrides: dict[str, object],
    message: str,
) -> None:
    values: dict[str, object] = {"SATELLITE_TOKEN": "token", **overrides}

    with pytest.raises(ValidationError, match=message):
        KubernetesConfiguration.model_validate(values)


def test_default_gpu_field_declaration_matches_the_shared_snapshot() -> None:
    model = build_settings_model(configuration(GPU_OFFERED=True))

    assert settings_fields(model) == json.loads(SNAPSHOT.read_text())
