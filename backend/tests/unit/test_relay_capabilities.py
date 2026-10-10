from typing import Any

import pytest
from luml.schemas.relay import (
    get_present_relay_capabilities,
    normalize_relay_capabilities,
)
from luml.schemas.satellite import CapabilityValidationError


def test_known_sessions_declaration_gets_defaults() -> None:
    assert normalize_relay_capabilities({"sessions": {"version": 1}}) == {
        "sessions": {"version": 1, "api_versions": [1]}
    }


def test_unknown_version_and_custom_capabilities_are_kept_as_declared() -> None:
    declared = {
        "sessions": {"version": 2, "api_versions": [2], "paths": ["/x"]},
        "custom.replay": {"version": 1, "mode": "fast"},
    }

    assert normalize_relay_capabilities(declared) == declared


@pytest.mark.parametrize(
    ("declared", "message"),
    [
        ({"replay": {"version": 1}}, "Invalid capability 'replay'"),
        ({"custom.Replay": {"version": 1}}, "Invalid capability 'custom.Replay'"),
        ({"sessions": {}}, "Invalid capability 'sessions' field 'version'"),
        ({"sessions": {"version": 0}}, "Invalid capability 'sessions' field 'version'"),
        (
            {"sessions": {"version": 1, "api_versions": "1"}},
            "Invalid capability 'sessions' field 'api_versions'",
        ),
    ],
)
def test_invalid_declarations_are_refused(
    declared: dict[str, dict[str, Any]], message: str
) -> None:
    with pytest.raises(CapabilityValidationError, match=message):
        normalize_relay_capabilities(declared)


@pytest.mark.parametrize(
    ("declared", "present"),
    [
        ({"sessions": {"version": 1, "api_versions": [1]}}, ["sessions"]),
        ({"sessions": {"version": 1, "api_versions": [1, 2]}}, ["sessions"]),
        ({"sessions": {"version": 1, "api_versions": [2]}}, []),
        ({"sessions": {"version": 2, "api_versions": [1]}}, []),
        ({"custom.replay": {"version": 7}}, ["custom.replay"]),
        ({}, []),
    ],
)
def test_present_capabilities_are_those_this_luml_supports(
    declared: dict[str, dict[str, Any]], present: list[str]
) -> None:
    assert get_present_relay_capabilities(declared) == present
