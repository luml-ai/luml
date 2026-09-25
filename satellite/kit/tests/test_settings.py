from enum import StrEnum
from typing import Literal

import pytest

from luml_satellite.declaration import (
    ConditionGroup,
    DeploymentSettings,
    DropdownValue,
    FieldCondition,
    ModelCondition,
    SettingsDeclarationError,
    SettingsValidationError,
    SettingsValidator,
    parse_settings,
    setting_field,
    settings_fields,
)


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"


class FieldShapeSettings(DeploymentSettings):
    enabled: bool = setting_field(False)
    replicas: int = setting_field(1, ge=1, le=8)
    endpoint: str = setting_field(pattern=r"^https://")
    memory: str = setting_field(
        "2Gi",
        values=[DropdownValue("2 GiB", "2Gi"), DropdownValue("4 GiB", "4Gi")],
    )
    priority: Literal[1, 2] = 1
    log_level: LogLevel = LogLevel.INFO
    optional_name: str | None = None
    internal_name: str = setting_field("hidden", exposed=False)


def field_map(settings_type: type[DeploymentSettings]) -> dict[str, dict[str, object]]:
    return {str(field["name"]): field for field in settings_fields(settings_type)}


def test_each_field_type_uses_the_existing_wire_shape() -> None:
    fields = field_map(FieldShapeSettings)

    assert fields["enabled"] == {
        "name": "enabled",
        "type": "boolean",
        "values": None,
        "required": False,
        "validators": [],
        "conditions": [],
        "default": False,
    }
    assert fields["replicas"] == {
        "name": "replicas",
        "type": "number",
        "values": None,
        "required": False,
        "validators": [
            {"type": "min", "value": 1},
            {"type": "max", "value": 8},
        ],
        "conditions": [],
        "default": 1,
    }
    assert fields["endpoint"] == {
        "name": "endpoint",
        "type": "text",
        "values": None,
        "required": True,
        "validators": [{"type": "regex", "value": r"^https://"}],
        "conditions": [],
    }
    assert fields["memory"]["type"] == "dropdown"
    assert fields["memory"]["values"] == [
        {"label": "2 GiB", "value": "2Gi"},
        {"label": "4 GiB", "value": "4Gi"},
    ]
    assert fields["priority"]["values"] == [
        {"label": "1", "value": 1},
        {"label": "2", "value": 2},
    ]
    assert fields["log_level"]["values"] == [
        {"label": "Debug", "value": "DEBUG"},
        {"label": "Info", "value": "INFO"},
    ]
    assert fields["optional_name"]["default"] is None


def test_unexposed_fields_are_parsed_but_not_declared() -> None:
    fields = field_map(FieldShapeSettings)
    parsed = parse_settings(
        FieldShapeSettings,
        {
            "endpoint": "https://example.test",
            "internal_name": "stored",
        },
    )

    assert "health_check_timeout" not in fields
    assert "internal_name" not in fields
    assert parsed.internal_name == "stored"
    assert parsed.health_check_timeout == 1800


FIELD_CONDITIONS = [
    FieldCondition("source", "equal", 2),
    FieldCondition("source", "notEqual", 3),
    FieldCondition("source", "gt", 1),
    FieldCondition("source", "gte", 2),
    FieldCondition("source", "lt", 3),
    FieldCondition("source", "lte", 2),
    FieldCondition("source", "includes"),
    FieldCondition("source", "notIncludes"),
]
MODEL_CONDITIONS = [
    ModelCondition("tags", "includes", [["tabular", "classification"]]),
    ModelCondition("tags", "notIncludes", [["vision"]]),
    ModelCondition("version", "eq", "1.0"),
    ModelCondition("version", "neq", "2.0"),
    ModelCondition("variant", "eq", "pyfunc"),
    ModelCondition("variant", "neq", "pipeline"),
    ModelCondition("variant", "includes", "pyfunc,pipeline"),
    ModelCondition("variant", "notIncludes", "onnx"),
]


class ConditionalSettings(DeploymentSettings):
    source: int | None = None
    target: str = setting_field(
        "value",
        conditions=[
            *FIELD_CONDITIONS,
            *MODEL_CONDITIONS,
            ConditionGroup(
                FieldCondition("source", "equal", 2),
                ModelCondition("variant", "eq", "pyfunc"),
            ),
        ],
    )


def test_every_condition_operator_and_nested_groups_are_preserved() -> None:
    conditions = field_map(ConditionalSettings)["target"]["conditions"]

    assert isinstance(conditions, list)
    assert [condition["type"] for condition in conditions[:8]] == ["field"] * 8
    assert [condition["body"]["operator"] for condition in conditions[:8]] == [
        "equal",
        "notEqual",
        "gt",
        "gte",
        "lt",
        "lte",
        "includes",
        "notIncludes",
    ]
    assert [condition["type"] for condition in conditions[8:16]] == ["model"] * 8
    assert [condition["body"]["operator"] for condition in conditions[8:16]] == [
        "includes",
        "notIncludes",
        "eq",
        "neq",
        "eq",
        "neq",
        "includes",
        "notIncludes",
    ]
    assert conditions[-1] == {
        "type": "field",
        "body": [
            {
                "type": "field",
                "body": {"field": "source", "operator": "equal", "value": 2},
            },
            {
                "type": "model",
                "body": {"field": "variant", "operator": "eq", "value": "pyfunc"},
            },
        ],
    }


def test_every_validator_type_and_optional_message_are_preserved() -> None:
    validators = [
        SettingsValidator("min", 1, "At least one"),
        SettingsValidator("max", 8, "At most eight"),
        SettingsValidator("regex", r"^x", "Starts with x"),
        SettingsValidator("equal", "exact", "Must match"),
        SettingsValidator("in", ["x", "y"], "Choose a known value"),
        SettingsValidator("notEqual", "blocked"),
    ]

    class ValidatorSettings(DeploymentSettings):
        value: str = setting_field(validators=validators)

    assert field_map(ValidatorSettings)["value"]["validators"] == [
        {"type": "min", "value": 1, "message": "At least one"},
        {"type": "max", "value": 8, "message": "At most eight"},
        {"type": "regex", "value": r"^x", "message": "Starts with x"},
        {"type": "equal", "value": "exact", "message": "Must match"},
        {"type": "in", "value": ["x", "y"], "message": "Choose a known value"},
        {"type": "notEqual", "value": "blocked"},
    ]


def test_condition_naming_an_undeclared_setting_fails_at_class_creation() -> None:
    with pytest.raises(SettingsDeclarationError, match="target.*missing"):

        class InvalidConditionSettings(DeploymentSettings):
            target: int = setting_field(
                1,
                conditions=[FieldCondition("missing", "equal", True)],
            )


@pytest.mark.parametrize("annotation", [list[str], float])
def test_non_scalar_and_float_fields_fail_at_class_creation(annotation: object) -> None:
    with pytest.raises(SettingsDeclarationError, match="bad.*unsupported"):
        type(
            "InvalidSettings",
            (DeploymentSettings,),
            {"__annotations__": {"bad": annotation}},
        )


def test_parsing_ignores_conditions_and_unknown_keys() -> None:
    class GpuSettings(DeploymentSettings):
        use_gpu: bool = False
        gpu_count: int = setting_field(
            1,
            ge=1,
            conditions=[FieldCondition("use_gpu", "equal", True)],
        )

    parsed = parse_settings(
        GpuSettings,
        {"use_gpu": False, "gpu_count": 3, "future_setting": "ignored"},
    )

    assert parsed.use_gpu is False
    assert parsed.gpu_count == 3
    assert not hasattr(parsed, "future_setting")


def test_known_invalid_value_names_its_field() -> None:
    class ReplicaSettings(DeploymentSettings):
        replicas: int = setting_field(1, ge=1)

    with pytest.raises(SettingsValidationError, match="replicas") as caught:
        parse_settings(ReplicaSettings, {"replicas": 0})

    assert caught.value.field == "replicas"


def test_settings_override_uses_its_own_health_timeout_default() -> None:
    class ExposedTimeoutSettings(DeploymentSettings):
        health_check_timeout: int = setting_field(30, exposed=True, ge=1, le=60)

    parsed = parse_settings(
        ExposedTimeoutSettings,
        {},
        default_health_check_timeout=45,
    )

    assert parsed.health_check_timeout == 30
    assert field_map(ExposedTimeoutSettings)["health_check_timeout"]["default"] == 30
