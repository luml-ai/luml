import httpx
import pytest

from luml_satellite.testing import FakePlatform
from luml_satellite.wire import (
    AuthenticationFailure,
    KitInfo,
    PlatformClient,
    PlatformRefusal,
)
from tests.helpers import ARTIFACT_ID, DEPLOYMENT_ID, deployment_record, task_record


@pytest.mark.asyncio
async def test_legacy_mode_requires_an_address_and_drops_unknown_capability_fields() -> None:
    platform = FakePlatform(legacy=True)
    async with PlatformClient(
        "http://platform", "test-token", transport=platform.transport
    ) as client:
        paired = await client.pair_satellite(
            "http://satellite",
            {
                "deploy": {"version": 1, "future_field": "dropped"},
                "custom.vendor": {"version": 1, "facets": ["satellite:custom.vendor"]},
            },
            kit=KitInfo(kind="docker"),
        )
        with pytest.raises(PlatformRefusal) as caught:
            await client.get_contract()

    assert paired.kit_info is None
    assert paired.capabilities == {"deploy": {"version": 1}}
    assert caught.value.status_code == 404


@pytest.mark.asyncio
async def test_fake_platform_authentication_not_found_and_transition_refusal() -> None:
    platform = FakePlatform()
    platform.add_deployment(deployment_record(status="pending"))
    platform.refused_deployment_transitions.add(("pending", "active"))

    async with PlatformClient(
        "http://platform", "wrong-token", transport=platform.transport
    ) as wrong_client:
        with pytest.raises(AuthenticationFailure) as unauthorized:
            await wrong_client.list_tasks()
    assert unauthorized.value.status_code == 401

    async with PlatformClient(
        "http://platform", "test-token", transport=platform.transport
    ) as client:
        with pytest.raises(PlatformRefusal) as missing:
            await client.get_deployment("missing")
        with pytest.raises(PlatformRefusal) as refused:
            await client.update_deployment_status(DEPLOYMENT_ID, "active")

    assert missing.value.status_code == 404
    assert refused.value.status_code == 409
    assert platform.deployment_transitions == []


@pytest.mark.asyncio
async def test_deprecated_artifact_routes_and_artifact_bytes() -> None:
    platform = FakePlatform()
    platform.add_artifact(ARTIFACT_ID, b"fixture", {"name": "fixture.tar.gz"})
    headers = {"Authorization": "Bearer test-token"}

    async with httpx.AsyncClient(
        base_url="http://platform", transport=platform.transport, headers=headers
    ) as client:
        metadata = await client.get(f"/satellites/v1/model_artifacts/{ARTIFACT_ID}")
        url_response = await client.get(
            f"/satellites/v1/model_artifacts/{ARTIFACT_ID}/download-url"
        )
        content = await client.get(url_response.json()["url"])

    assert metadata.status_code == 200
    assert metadata.json()["artifact"]["id"] == ARTIFACT_ID
    assert metadata.json()["model"]["id"] == ARTIFACT_ID
    assert url_response.status_code == 200
    assert content.status_code == 200
    assert content.content == b"fixture"


@pytest.mark.asyncio
async def test_fake_platform_control_state_can_inspect_and_seed_runtime_records() -> None:
    platform = FakePlatform()
    headers = {"Authorization": "Bearer test-token"}
    deployment = deployment_record()
    task = task_record()

    async with httpx.AsyncClient(
        base_url="http://platform",
        transport=platform.transport,
        headers=headers,
    ) as client:
        seeded = await client.post(
            "/__fake__/state",
            json={
                "deployments": [deployment],
                "tasks": [task],
                "allowed_api_keys": ["valid-key"],
                "monitoring_tokens": {
                    "launch-token": {"active": False, "claims": None},
                },
            },
        )
        state = await client.get("/__fake__/state")

    assert seeded.status_code == 204
    assert state.status_code == 200
    assert state.json()["deployments"] == [deployment]
    assert state.json()["tasks"] == [task]
    assert state.json()["allowed_api_keys"] == ["valid-key"]
    assert state.json()["monitoring_tokens"] == {"launch-token": {"active": False, "claims": None}}
    assert state.json()["requests"][-1]["path"] == "/__fake__/state"


@pytest.mark.asyncio
async def test_fake_platform_control_state_requires_authentication_and_valid_records() -> None:
    platform = FakePlatform()

    async with httpx.AsyncClient(
        base_url="http://platform",
        transport=platform.transport,
    ) as client:
        unauthorized = await client.get("/__fake__/state")
        invalid = await client.post(
            "/__fake__/state",
            headers={"Authorization": "Bearer test-token"},
            json={"deployments": [{"name": "missing id"}]},
        )

    assert unauthorized.status_code == 401
    assert invalid.status_code == 422
    assert platform.deployments == {}
