import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

import pytest
from fastapi import status
from luml.handlers.deployments import (
    satellite_field_conditions_hold,
    validate_satellite_parameters,
)
from luml.infra.exceptions import ApplicationError
from luml.schemas.artifacts import Artifact
from luml.schemas.satellite import DeployCapabilityV1

CONDITION_CASES_PATH = (
    Path(__file__).resolve().parents[2] / "satellite_field_condition_cases.json"
)
CONDITION_CASES = cast(
    list[dict[str, Any]], json.loads(CONDITION_CASES_PATH.read_text())
)

PARAMETER_FIELDS: list[dict[str, Any]] = [
    {
        "name": "use_gpu",
        "type": "boolean",
        "values": None,
        "required": True,
        "validators": [],
        "conditions": [],
    },
    {
        "name": "gpu_count",
        "type": "number",
        "values": None,
        "required": False,
        "validators": [{"type": "min", "value": 1}],
        "conditions": [
            {
                "type": "field",
                "body": {"field": "use_gpu", "operator": "equal", "value": True},
            }
        ],
    },
    {
        "name": "optimized_runtime",
        "type": "text",
        "values": None,
        "required": False,
        "validators": [],
        "conditions": [
            {
                "type": "model",
                "body": {
                    "field": "tags",
                    "operator": "includes",
                    "value": [["optimized"]],
                },
            }
        ],
    },
    {
        "name": "required_name",
        "type": "text",
        "values": None,
        "required": True,
        "validators": [],
        "conditions": [],
    },
    {
        "name": "replicas",
        "type": "number",
        "values": None,
        "required": True,
        "validators": [
            {"type": "min", "value": 1},
            {"type": "max", "value": 4},
        ],
        "conditions": [],
    },
    {
        "name": "memory",
        "type": "dropdown",
        "values": [
            {"label": "2 GiB", "value": "2Gi"},
            {"label": "4 GiB", "value": "4Gi"},
        ],
        "required": True,
        "validators": [],
        "conditions": [],
    },
    {
        "name": "future_setting",
        "type": "text",
        "values": None,
        "required": False,
        "validators": [],
        "conditions": [{"type": "future", "body": {"operator": "new"}}],
    },
]

VALID_PARAMETERS: dict[str, bool | int | str] = {
    "use_gpu": False,
    "required_name": "worker",
    "replicas": 2,
    "memory": "2Gi",
}


def _artifact(
    *,
    producer_tags: list[str] | None = None,
    version: str | None = "1.0",
    variant: str = "pyfunc",
) -> Artifact:
    return cast(
        Artifact,
        Mock(
            manifest=Mock(
                producer_tags=producer_tags or [],
                version=version,
                variant=variant,
            )
        ),
    )


def _capability(
    fields: list[dict[str, Any]] | None = None,
) -> DeployCapabilityV1:
    return DeployCapabilityV1(
        version=1,
        supported_variants=["pyfunc"],
        extra_fields_form_spec=fields if fields is not None else PARAMETER_FIELDS,
    )


@pytest.mark.parametrize(
    "case",
    CONDITION_CASES,
    ids=[str(case["name"]) for case in CONDITION_CASES],
)
def test_shared_condition_cases(case: dict[str, Any]) -> None:
    manifest = case["manifest"]

    result = satellite_field_conditions_hold(
        case["conditions"],
        case["current_values"],
        producer_tags=manifest["producer_tags"],
        version=manifest["version"],
        variant=manifest["variant"],
    )

    assert result is case["expected"]


@pytest.mark.parametrize(
    ("parameters", "failed_field", "failed_rule"),
    [
        (
            {**VALID_PARAMETERS, "gpu_count": 1},
            "gpu_count",
            "condition",
        ),
        (
            {**VALID_PARAMETERS, "optimized_runtime": "enabled"},
            "optimized_runtime",
            "condition",
        ),
        (
            {
                key: value
                for key, value in VALID_PARAMETERS.items()
                if key != "required_name"
            },
            "required_name",
            "required",
        ),
        (
            {**VALID_PARAMETERS, "replicas": 5},
            "replicas",
            "max",
        ),
        (
            {**VALID_PARAMETERS, "memory": "8Gi"},
            "memory",
            "dropdown",
        ),
        (
            {**VALID_PARAMETERS, "replicas": "2"},
            "replicas",
            "number",
        ),
    ],
)
def test_parameter_verification_names_the_failed_rule(
    parameters: dict[str, bool | int | str],
    failed_field: str,
    failed_rule: str,
) -> None:
    with pytest.raises(ApplicationError, match=failed_field) as caught:
        validate_satellite_parameters(_capability(), parameters, _artifact())

    assert caught.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert failed_rule in caught.value.message


def test_valid_and_undeclared_parameters_are_left_untouched() -> None:
    parameters = {
        **VALID_PARAMETERS,
        "health_check_timeout": 60,
        "undeclared": "kept",
    }
    original = parameters.copy()

    validate_satellite_parameters(_capability(), parameters, _artifact())

    assert parameters == original


def test_unknown_condition_and_validator_types_are_skipped() -> None:
    fields = [
        PARAMETER_FIELDS[-1],
        {
            "name": "new_validation",
            "type": "text",
            "values": None,
            "required": True,
            "conditions": [],
            "validators": [{"type": "future", "value": "rule"}],
        },
    ]

    validate_satellite_parameters(
        _capability(fields),
        {"future_setting": "on", "new_validation": "value"},
        _artifact(),
    )


def test_empty_field_list_accepts_parameters_as_before() -> None:
    validate_satellite_parameters(
        _capability([]),
        {"health_check_timeout": 60, "unknown": True},
        _artifact(),
    )


def test_required_field_hidden_by_a_condition_may_be_absent() -> None:
    field = {
        "name": "gpu_count",
        "type": "number",
        "values": None,
        "required": True,
        "validators": [],
        "conditions": [
            {
                "type": "field",
                "body": {"field": "use_gpu", "operator": "equal", "value": True},
            }
        ],
    }

    validate_satellite_parameters(_capability([field]), {"use_gpu": False}, _artifact())


@pytest.mark.parametrize(
    ("field_type", "validator", "accepted", "refused"),
    [
        ("number", {"type": "min", "value": 2}, 2, 1),
        ("number", {"type": "max", "value": 2}, 2, 3),
        ("text", {"type": "regex", "value": "^ok"}, "okay", "no"),
        ("text", {"type": "equal", "value": "exact"}, "exact", "other"),
        ("text", {"type": "in", "value": ["a", "b"]}, "a", "c"),
        ("text", {"type": "notEqual", "value": "blocked"}, "open", "blocked"),
    ],
)
def test_every_validator_type(
    field_type: str,
    validator: dict[str, object],
    accepted: int | str,
    refused: int | str,
) -> None:
    field = {
        "name": "value",
        "type": field_type,
        "values": None,
        "required": True,
        "validators": [validator],
        "conditions": [],
    }
    capability = _capability([field])

    validate_satellite_parameters(capability, {"value": accepted}, _artifact())
    with pytest.raises(ApplicationError, match=str(validator["type"])):
        validate_satellite_parameters(capability, {"value": refused}, _artifact())
