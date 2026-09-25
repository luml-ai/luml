import logging

import pytest

from luml_satellite.declaration import (
    DeploymentSettings,
    capability_diff,
    derive_capabilities,
    pair_satellite,
    setting_field,
    settings_fields,
)
from luml_satellite.testing import FakeMonitoringBundle, FakePlatform
from luml_satellite.wire import PlatformClient


class DockerSettings(DeploymentSettings):
    pass


class ConfigurableSettings(DeploymentSettings):
    replicas: int = setting_field(1, ge=1, le=8)


def docker_capabilities(
    monitoring_bundle: FakeMonitoringBundle | None = None,
) -> dict[str, dict[str, object]]:
    return derive_capabilities(
        supported_variants=["pyfunc", "pipeline"],
        supported_tags_combinations=None,
        settings_type=DockerSettings,
        monitoring_bundle=monitoring_bundle,
    )


def test_docker_declaration_matches_the_existing_wire_contract() -> None:
    assert docker_capabilities(FakeMonitoringBundle()) == {
        "deploy": {
            "version": 1,
            "api_versions": [1],
            "facets": ["satellite", "deployment"],
            "supported_variants": ["pyfunc", "pipeline"],
            "supported_tags_combinations": None,
            "extra_fields_form_spec": [],
        },
        "monitoring": {
            "version": 1,
            "api_versions": [1],
            "facets": ["deployment:monitoring"],
            "features": [
                "runtime",
                "traces",
                "alerts",
                "data_quality",
                "feature_drift",
                "output_drift",
                "multivariate_drift",
            ],
        },
    }


def test_features_and_fields_are_derived_from_runtime_inputs() -> None:
    bundle = FakeMonitoringBundle(
        [
            "runtime",
            "traces",
            "alerts",
            "data_quality",
            "feature_drift",
            "output_drift",
        ]
    )
    capabilities = derive_capabilities(
        supported_variants=["pyfunc"],
        supported_tags_combinations=None,
        settings_type=ConfigurableSettings,
        monitoring_bundle=bundle,
    )

    assert capabilities["monitoring"]["features"] == list(bundle.monitoring_features)
    assert capabilities["deploy"]["extra_fields_form_spec"] == settings_fields(ConfigurableSettings)


def test_monitoring_capability_can_be_absent() -> None:
    assert set(docker_capabilities()) == {"deploy"}


def test_a_satellite_that_does_not_serve_has_only_the_satellite_facet() -> None:
    capabilities = derive_capabilities(
        supported_variants=[],
        supported_tags_combinations=[],
        settings_type=DockerSettings,
        serves_deployments=False,
    )

    assert capabilities["deploy"]["facets"] == ["satellite"]


def test_capability_diff_reports_dotted_dropped_and_changed_fields() -> None:
    declared = {
        "deploy": {
            "version": 1,
            "future": {"nested": True},
            "facets": ["satellite", "deployment"],
        },
        "custom.vendor": {"version": 1},
    }
    kept = {
        "deploy": {
            "version": 2,
            "future": {},
            "facets": ["satellite"],
        }
    }

    assert capability_diff(declared, kept) == [
        "deploy.version: changed from 1 to 2",
        "deploy.future.nested: dropped",
        'deploy.facets: changed from ["satellite", "deployment"] to ["satellite"]',
        "custom.vendor: dropped",
    ]


def test_capability_diff_distinguishes_json_boolean_and_number_values() -> None:
    declared = {"deploy": {"future": [{"enabled": True}]}}
    kept = {"deploy": {"future": [{"enabled": 1}]}}

    assert capability_diff(declared, kept) == [
        'deploy.future: changed from [{"enabled": true}] to [{"enabled": 1}]'
    ]


@pytest.mark.asyncio
async def test_pairing_sends_kit_info_and_tolerates_a_missing_contract(
    caplog: pytest.LogCaptureFixture,
) -> None:
    platform = FakePlatform(contract_error=(404, "contract unavailable"))
    capabilities = docker_capabilities()

    with caplog.at_level(logging.WARNING):
        async with PlatformClient(
            "http://platform",
            "test-token",
            transport=platform.transport,
        ) as client:
            paired = await pair_satellite(
                client,
                kind="docker",
                capabilities=capabilities,
                slug="docker-2026.01-v2-debian12",
            )

    assert paired.paired is True
    pair_request = next(request for request in platform.requests if request.path.endswith("/pair"))
    assert isinstance(pair_request.body, dict)
    assert "base_url" not in pair_request.body
    assert pair_request.body["kit"] == {
        "name": "luml-satellite",
        "version": "0.1.0",
        "kind": "docker",
        "api_version": 1,
    }
    assert any(request.path.endswith("/contract") for request in platform.requests)
    assert "contract unavailable" in caplog.text


@pytest.mark.asyncio
async def test_pairing_keeps_unknown_fields_without_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    platform = FakePlatform()
    capabilities = docker_capabilities()
    capabilities["deploy"]["future"] = {"nested": True}

    with caplog.at_level(logging.WARNING):
        async with PlatformClient(
            "http://platform",
            "test-token",
            transport=platform.transport,
        ) as client:
            paired = await pair_satellite(
                client,
                kind="docker",
                capabilities=capabilities,
            )

    assert paired.capabilities["deploy"]["future"] == {"nested": True}
    assert not caplog.records


@pytest.mark.asyncio
async def test_pairing_logs_fields_dropped_by_an_older_platform(
    caplog: pytest.LogCaptureFixture,
) -> None:
    platform = FakePlatform(legacy=True)
    capabilities = docker_capabilities()
    capabilities["deploy"]["future"] = {"nested": True}

    with caplog.at_level(logging.WARNING):
        async with PlatformClient(
            "http://platform",
            "test-token",
            transport=platform.transport,
        ) as client:
            await pair_satellite(
                client,
                kind="docker",
                capabilities=capabilities,
                base_url="https://satellite.example/",
            )

    assert "deploy.future: dropped" in caplog.text
    pair_body = next(
        request.body for request in platform.requests if request.path.endswith("/pair")
    )
    assert isinstance(pair_body, dict)
    assert pair_body["base_url"] == "https://satellite.example"
