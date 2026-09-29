import json
from collections.abc import Mapping, Sequence
from typing import Protocol

from luml_satellite.declaration.settings import DeploymentSettings, settings_fields

type CapabilityDeclaration = dict[str, dict[str, object]]


class MonitoringBundleCapabilities(Protocol):
    @property
    def monitoring_features(self) -> Sequence[str]: ...


def derive_capabilities(
    *,
    supported_variants: Sequence[str],
    supported_tags_combinations: Sequence[Sequence[str]] | None,
    settings_type: type[DeploymentSettings],
    monitoring_bundle: MonitoringBundleCapabilities | None = None,
    serves_deployments: bool = True,
) -> CapabilityDeclaration:
    monitoring_features = (
        list(monitoring_bundle.monitoring_features) if monitoring_bundle is not None else None
    )
    return build_capabilities(
        supported_variants=supported_variants,
        supported_tags_combinations=supported_tags_combinations,
        field_spec=settings_fields(settings_type),
        monitoring_features=monitoring_features,
        serves_deployments=serves_deployments,
    )


def build_capabilities(
    *,
    supported_variants: Sequence[str],
    supported_tags_combinations: Sequence[Sequence[str]] | None,
    field_spec: Sequence[Mapping[str, object]],
    monitoring_features: Sequence[str] | None,
    serves_deployments: bool = True,
) -> CapabilityDeclaration:
    deploy_facets = ["satellite", "deployment"] if serves_deployments else ["satellite"]
    capabilities: CapabilityDeclaration = {
        "deploy": {
            "version": 1,
            "api_versions": [1],
            "facets": deploy_facets,
            "supported_variants": list(supported_variants),
            "supported_tags_combinations": (
                [list(combination) for combination in supported_tags_combinations]
                if supported_tags_combinations is not None
                else None
            ),
            "extra_fields_form_spec": [dict(field) for field in field_spec],
        }
    }
    if monitoring_features is not None:
        capabilities["monitoring"] = {
            "version": 1,
            "api_versions": [1],
            "facets": ["deployment:monitoring"],
            "features": list(monitoring_features),
        }
    return capabilities


def capability_diff(
    declared: Mapping[str, object],
    kept: Mapping[str, object],
) -> list[str]:
    differences: list[str] = []
    _diff_mapping("", declared, kept, differences)
    return differences


def _diff_mapping(
    prefix: str,
    declared: Mapping[str, object],
    kept: Mapping[str, object],
    differences: list[str],
) -> None:
    for key, expected in declared.items():
        path = f"{prefix}.{key}" if prefix else key
        if key not in kept:
            differences.append(f"{path}: dropped")
            continue
        actual = kept[key]
        if isinstance(expected, Mapping) and isinstance(actual, Mapping):
            _diff_mapping(path, expected, actual, differences)
        elif not _json_values_equal(expected, actual):
            differences.append(f"{path}: changed from {_display(expected)} to {_display(actual)}")


def _json_values_equal(expected: object, actual: object) -> bool:
    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        return expected.keys() == actual.keys() and all(
            _json_values_equal(expected[key], actual[key]) for key in expected
        )
    if isinstance(expected, list) and isinstance(actual, list):
        return len(expected) == len(actual) and all(
            _json_values_equal(expected_item, actual_item)
            for expected_item, actual_item in zip(expected, actual, strict=True)
        )
    return type(expected) is type(actual) and expected == actual


def _display(value: object) -> str:
    return json.dumps(value, sort_keys=True, default=str)
