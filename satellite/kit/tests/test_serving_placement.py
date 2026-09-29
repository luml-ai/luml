from collections.abc import Mapping
from typing import Any

import httpx
import pytest
import respx

from luml_satellite import (
    AuthorizationVerdict,
    Deployment,
    ModelDescription,
    PlatformClient,
    SatelliteConfiguration,
    SatelliteRuntime,
    TokenDeriver,
)
from luml_satellite.serving import (
    InProcessServingPlacement,
    gate_reference_profile,
    usable_reference_profile,
)
from luml_satellite.testing import FakeDriver, FakePlatform
from luml_satellite.workload import ArtifactResolver, ProfileStatus
from tests.helpers import DEPLOYMENT_ID, deployment_record

AUTHORIZATION = {"Authorization": "Bearer key"}
READY_PROFILE: dict[str, Any] = {
    "task_type": "regression",
    "profile_status": "ready",
    "feature_summaries": {"numerical_features": {}, "categorical_features": {}},
}


class AllowAll:
    async def authorize(self, api_key: str) -> AuthorizationVerdict:
        return AuthorizationVerdict.ALLOWED


class NoSecrets:
    async def resolve(
        self,
        deployment_id: str,
        secrets: Mapping[str, str],
    ) -> Mapping[str, str]:
        return {}


@pytest.mark.asyncio
async def test_in_process_placement_reads_registers_and_updates_a_deployment() -> None:
    requests: list[str] = []

    async def upstream(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        responses = {
            "/healthz": httpx.Response(200, json={"status": "healthy"}),
            "/manifest": httpx.Response(
                200,
                json={"producer_tags": ["luml.ai::tabular_monitoring:v1"]},
            ),
            "/openapi.json": httpx.Response(
                200,
                json={
                    "openapi": "3.1.0",
                    "components": {
                        "schemas": {
                            "DynamicAttributesModel": {
                                "properties": {
                                    "feature": {"type": "number"},
                                    "api_key": {"type": "string"},
                                }
                            }
                        }
                    },
                },
            ),
            "/reference_profile": httpx.Response(200, json=READY_PROFILE),
        }
        return responses[request.url.path]

    placement = InProcessServingPlacement(
        AllowAll(),
        NoSecrets(),
        upstream_transport=httpx.MockTransport(upstream),
    )
    deployment = Deployment.model_validate(
        deployment_record(
            monitoring_mode="FULL",
            dynamic_attributes_secrets={"api_key": "secret-id"},
        )
    )
    try:
        description = await placement.describe(deployment, upstream_url="http://model")
        assert await placement.check_health(deployment, upstream_url="http://model") is True
        await placement.register(
            deployment,
            upstream_url="http://model",
            description=description,
        )

        local = placement.get_deployment(DEPLOYMENT_ID)
        assert local is not None
        assert local.reference_profile == READY_PROFILE
        assert local.profile_status is ProfileStatus.READY
        assert local.monitoring_enabled is True
        assert local.metadata.name == "classifier"
        assert local.openapi_schema is not None
        properties = local.openapi_schema["components"]["schemas"]["DynamicAttributesModel"][
            "properties"
        ]
        assert properties == {"feature": {"type": "number"}}
        assert placement.address(deployment, upstream_url="http://model") == (
            f"/deployments/{DEPLOYMENT_ID}"
        )
        assert placement.is_registered(DEPLOYMENT_ID)

        updated = deployment.model_copy(
            update={
                "name": "renamed",
                "status": "active",
                "monitoring_mode": "off",
                "dynamic_attributes_secrets": {},
            }
        )
        await placement.register(
            updated,
            upstream_url=None,
            description=ModelDescription(),
        )
        assert local.metadata.name == "renamed"
        assert local.metadata.status == "active"
        assert local.monitoring_enabled is False
        assert local.dynamic_attributes_secrets == {}
        assert local.upstream_url == "http://model"
        assert local.reference_profile == READY_PROFILE

        request_count = len(requests)
        placement.mark_reconciled()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=placement.application),
            base_url="http://satellite",
        ) as client:
            listing = await client.get("/deployments", headers=AUTHORIZATION)
        assert listing.status_code == 200
        assert len(requests) == request_count

        await placement.unregister(DEPLOYMENT_ID)
        assert not placement.is_registered(DEPLOYMENT_ID)
    finally:
        await placement.aclose()


@pytest.mark.asyncio
async def test_description_parts_are_independently_optional_and_health_errors_are_false() -> None:
    async def upstream(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/manifest":
            return httpx.Response(500)
        if request.url.path == "/openapi.json":
            return httpx.Response(200, content=b"not-json")
        if request.url.path == "/reference_profile":
            return httpx.Response(404)
        raise httpx.ConnectError("unreachable", request=request)

    placement = InProcessServingPlacement(
        AllowAll(),
        NoSecrets(),
        upstream_transport=httpx.MockTransport(upstream),
    )
    deployment = Deployment.model_validate(deployment_record())
    try:
        description = await placement.describe(deployment, upstream_url="http://model")
        healthy = await placement.check_health(deployment, upstream_url="http://model")
    finally:
        await placement.aclose()

    assert description == ModelDescription()
    assert healthy is False


@pytest.mark.asyncio
async def test_in_process_compute_uses_the_shared_model_server_fixture(
    mock_model_server: respx.MockRouter,
) -> None:
    upstream_client = httpx.AsyncClient()
    placement = InProcessServingPlacement(
        AllowAll(),
        NoSecrets(),
        upstream_client=upstream_client,
    )
    deployment = Deployment.model_validate(deployment_record(status="active"))
    await placement.register(
        deployment,
        upstream_url=f"http://sat-{DEPLOYMENT_ID}:8000",
        description=ModelDescription(schema={"openapi": "3.1.0"}),
    )
    placement.mark_reconciled()
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=placement.application),
            base_url="http://satellite",
        ) as client:
            response = await client.post(
                f"/deployments/{DEPLOYMENT_ID}/compute",
                headers=AUTHORIZATION,
                json={"inputs": {"x": 1}},
            )
    finally:
        await upstream_client.aclose()

    assert response.status_code == 200
    assert response.json() == {"prediction": 42}
    assert mock_model_server.routes[-1].called


@pytest.mark.parametrize(
    ("manifest", "profile", "expected_profile", "expected_status"),
    [
        ({"producer_tags": []}, READY_PROFILE, None, ProfileStatus.ABSENT),
        (
            {"producer_tags": ["luml.ai::tabular_monitoring:v9"]},
            READY_PROFILE,
            None,
            ProfileStatus.UNSUPPORTED,
        ),
        (
            {"producer_tags": ["luml.ai::tabular_monitoring:v1"]},
            None,
            None,
            ProfileStatus.ABSENT,
        ),
        (
            {"producer_tags": ["luml.ai::tabular_monitoring:v1"]},
            {"profile_status": "placeholder"},
            None,
            ProfileStatus.PLACEHOLDER,
        ),
        (
            {"producer_tags": ["luml.ai::tabular_monitoring:v1"]},
            {"task_type": "regression"},
            None,
            ProfileStatus.PLACEHOLDER,
        ),
        (
            {"producer_tags": ["luml.ai::tabular_monitoring:v1"]},
            {"feature_summaries": {"numerical_features": {"age": {"mean": 1}}}},
            {"feature_summaries": {"numerical_features": {"age": {"mean": 1}}}},
            ProfileStatus.READY,
        ),
    ],
)
def test_reference_profile_gating(
    manifest: dict[str, Any],
    profile: dict[str, Any] | None,
    expected_profile: dict[str, Any] | None,
    expected_status: ProfileStatus,
) -> None:
    assert gate_reference_profile(manifest, profile) == (expected_profile, expected_status)


def test_usable_reference_profile_accepts_ready_or_real_summaries_only() -> None:
    summaries = {"feature_summaries": {"categorical_features": {"city": {"count": 2}}}}

    assert usable_reference_profile(READY_PROFILE) == READY_PROFILE
    assert usable_reference_profile(summaries) == summaries
    assert usable_reference_profile({"profile_status": "placeholder"}) is None
    assert usable_reference_profile({"task_type": "regression"}) is None
    assert usable_reference_profile(None) is None


@pytest.mark.asyncio
async def test_runtime_opens_the_starting_gate_after_reconciliation() -> None:
    platform = FakePlatform()
    configuration = SatelliteConfiguration.model_validate(
        {
            "SATELLITE_TOKEN": platform.token,
            "PLATFORM_URL": "http://platform",
            "BASE_URL": "http://satellite",
            "MONITORING_ENABLED": False,
        }
    )
    async with PlatformClient(
        "http://platform",
        platform.token,
        transport=platform.transport,
    ) as platform_client:
        placement = InProcessServingPlacement(
            AllowAll(),
            NoSecrets(),
            artifact_resolver=ArtifactResolver(
                platform_client,
                TokenDeriver(platform.token),
            ),
            upstream_transport=httpx.MockTransport(lambda request: httpx.Response(200)),
        )
        runtime = SatelliteRuntime(
            configuration,
            platform_client,
            FakeDriver(),
            serving=placement,
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=placement.application),
            base_url="http://satellite",
        ) as client:
            before = await client.get("/deployments", headers=AUTHORIZATION)
            await runtime.reconcile()
            after = await client.get("/deployments", headers=AUTHORIZATION)
        assert runtime.internal_application is placement.internal_application
        await placement.aclose()

    assert before.status_code == 503
    assert after.status_code == 200
