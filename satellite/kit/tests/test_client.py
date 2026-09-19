from typing import Any

import httpx
import pytest

from luml_satellite.testing import FakePlatform
from luml_satellite.wire import (
    AuthenticationFailure,
    DeploymentStatus,
    DeploymentUpdate,
    ErrorMessage,
    KitInfo,
    LegacyAddressRequired,
    PlatformClient,
    PlatformError,
    PlatformRefusal,
    SatelliteTaskStatus,
)
from tests.helpers import (
    ARTIFACT_ID,
    DEPLOYMENT_ID,
    SECRET_ID,
    TASK_ID,
    deployment_record,
    task_record,
)


def seeded_platform() -> FakePlatform:
    platform = FakePlatform()
    platform.add_deployment(deployment_record())
    platform.add_task(task_record())
    platform.add_secret(SECRET_ID, "DATABASE_URL", "postgresql://example")
    platform.add_artifact(ARTIFACT_ID, b"artifact bytes", {"name": "model.tar.gz"})
    platform.allowed_api_keys.add("allowed-key")
    platform.monitoring_tokens["monitoring-token"] = {
        "active": True,
        "claims": {
            "deployment_id": DEPLOYMENT_ID,
            "satellite_id": platform.satellite_id,
            "user_id": "60000000-0000-0000-0000-000000000001",
            "scope": "monitoring:read",
            "jti": "70000000-0000-0000-0000-000000000001",
            "exp": 2_000_000_000,
        },
    }
    return platform


@pytest.mark.asyncio
async def test_every_platform_client_call_and_update_body() -> None:
    platform = seeded_platform()
    async with PlatformClient(
        "http://platform", "test-token", transport=platform.transport
    ) as client:
        paired = await client.pair_satellite(
            None,
            {"deploy": {"version": 1, "custom_field": "kept"}},
            slug="docker",
            openapi={"openapi": "3.1.0", "paths": {}},
            kit=KitInfo(kind="docker"),
        )
        contract = await client.get_contract()
        tasks = await client.list_tasks(SatelliteTaskStatus.PENDING)
        updated_task = await client.update_task_status(
            TASK_ID,
            SatelliteTaskStatus.RUNNING,
            ErrorMessage(reason="starting", error=""),
        )
        secrets = await client.get_orbit_secrets()
        secret = await client.get_orbit_secret(SECRET_ID)
        deployments = await client.list_deployments()
        deployment = await client.get_deployment(DEPLOYMENT_ID)
        updated = await client.update_deployment(
            DEPLOYMENT_ID,
            DeploymentUpdate(
                inference_url="/deployments/fixture",
                monitoring_url="https://monitoring.example/fixture",
                provider_ref="provider-123",
                progress_note="Creating workload",
            ),
        )
        status_update = await client.update_deployment_status(
            DEPLOYMENT_ID, DeploymentStatus.ACTIVE
        )
        allowed = await client.authorize_inference_access("allowed-key")
        denied = await client.authorize_inference_access("denied-key")
        introspection = await client.introspect_monitoring_token("monitoring-token")
        download_url = await client.get_artifact_download_url(ARTIFACT_ID)
        artifact, artifact_url = await client.get_artifact(ARTIFACT_ID)

        async with httpx.AsyncClient(transport=platform.transport) as raw_client:
            artifact_response = await raw_client.get(download_url)

        await client.delete_deployment(DEPLOYMENT_ID)

    assert paired.base_url is None
    assert paired.kit_info is not None and paired.kit_info.kind == "docker"
    assert paired.capabilities["deploy"]["custom_field"] == "kept"
    assert contract.api_version == 1
    assert [task["id"] for task in tasks] == [TASK_ID]
    assert updated_task["result"] == {"reason": "starting", "error": ""}
    assert secrets == [secret]
    assert secret["value"] == "postgresql://example"
    assert deployments[0]["id"] == deployment.id
    assert updated.provider_ref == "provider-123"
    assert updated.progress_note == "Creating workload"
    assert status_update["status"] == "active"
    assert allowed is True
    assert denied is False
    assert introspection.active is True
    assert artifact["id"] == ARTIFACT_ID
    assert artifact_url == download_url
    assert artifact_response.content == b"artifact bytes"
    assert DEPLOYMENT_ID not in platform.deployments

    pair_body = next(
        request.body for request in platform.requests if request.path.endswith("/pair")
    )
    assert isinstance(pair_body, dict)
    assert "base_url" not in pair_body
    assert pair_body == {
        "capabilities": {"deploy": {"version": 1, "custom_field": "kept"}},
        "slug": "docker",
        "openapi": {"openapi": "3.1.0", "paths": {}},
        "kit": {
            "name": "luml-satellite",
            "version": "0.1.0",
            "kind": "docker",
            "api_version": 1,
        },
    }
    assert platform.deployment_updates == [
        (
            DEPLOYMENT_ID,
            {
                "inference_url": "/deployments/fixture",
                "monitoring_url": "https://monitoring.example/fixture",
                "provider_ref": "provider-123",
                "progress_note": "Creating workload",
            },
        ),
        (DEPLOYMENT_ID, {"status": "active"}),
    ]
    assert [transition.body for transition in platform.task_transitions] == [
        {"status": "running", "result": {"reason": "starting", "error": ""}}
    ]
    assert [transition.status for transition in platform.deployment_transitions] == ["active"]


@pytest.mark.asyncio
async def test_update_deployment_can_explicitly_clear_new_fields() -> None:
    platform = seeded_platform()
    platform.deployments[DEPLOYMENT_ID]["provider_ref"] = "provider-123"
    platform.deployments[DEPLOYMENT_ID]["progress_note"] = "working"

    async with PlatformClient(
        "http://platform", "test-token", transport=platform.transport
    ) as client:
        await client.update_deployment(
            DEPLOYMENT_ID,
            DeploymentUpdate(provider_ref=None, progress_note=None),
        )

    assert platform.deployment_updates == [
        (DEPLOYMENT_ID, {"provider_ref": None, "progress_note": None})
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [400, 404, 409, 410, 422])
async def test_refusal_statuses_map_to_one_family(status_code: int) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"detail": "refused"})

    transport = httpx.MockTransport(handler)
    async with PlatformClient("http://platform", "token", transport=transport) as client:
        with pytest.raises(PlatformRefusal) as caught:
            await client.list_deployments()

    assert caught.value.status_code == status_code
    assert caught.value.detail == "refused"


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403])
async def test_authentication_statuses_map_to_one_family(status_code: int) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"detail": "bad token"})

    async with PlatformClient(
        "http://platform", "token", transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(AuthenticationFailure) as caught:
            await client.list_deployments()

    assert caught.value.status_code == status_code


@pytest.mark.asyncio
async def test_other_http_and_transport_errors_map_to_platform_error() -> None:
    async def server_error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="down")

    async with PlatformClient(
        "http://platform", "token", transport=httpx.MockTransport(server_error)
    ) as client:
        with pytest.raises(PlatformError) as caught:
            await client.list_deployments()
    assert type(caught.value) is PlatformError
    assert caught.value.status_code == 500

    async def connection_error(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable", request=request)

    async with PlatformClient(
        "http://platform", "token", transport=httpx.MockTransport(connection_error)
    ) as client:
        with pytest.raises(PlatformError, match="unreachable"):
            await client.list_deployments()


@pytest.mark.asyncio
async def test_legacy_pairing_error_names_base_url(
    caplog: pytest.LogCaptureFixture,
) -> None:
    platform = FakePlatform(legacy=True)
    async with PlatformClient(
        "http://platform", "test-token", transport=platform.transport
    ) as client:
        with pytest.raises(LegacyAddressRequired, match="requires BASE_URL"):
            await client.pair_satellite(None, {"deploy": {"version": 1}})

    assert "this platform requires BASE_URL; set BASE_URL or upgrade the platform" in caplog.text


@pytest.mark.asyncio
async def test_other_pairing_422_logs_platform_detail(
    caplog: pytest.LogCaptureFixture,
) -> None:
    platform = FakePlatform(pairing_error=(422, "capability rejected"))
    async with PlatformClient(
        "http://platform", "test-token", transport=platform.transport
    ) as client:
        with pytest.raises(PlatformRefusal):
            await client.pair_satellite(None, {"deploy": {"version": 1}})

    assert "capability rejected" in caplog.text
    assert "requires BASE_URL" not in caplog.text


@pytest.mark.asyncio
async def test_clients_do_not_share_authorization_state() -> None:
    first = FakePlatform(token="first-token", allowed_api_keys={"same-key"})
    second = FakePlatform(token="second-token")

    async with (
        PlatformClient("http://first", "first-token", transport=first.transport) as first_client,
        PlatformClient(
            "http://second", "second-token", transport=second.transport
        ) as second_client,
    ):
        assert await first_client.authorize_inference_access("same-key") is True
        assert await second_client.authorize_inference_access("same-key") is False


@pytest.mark.asyncio
async def test_client_requires_a_context_manager() -> None:
    client = PlatformClient("http://platform", "token")
    with pytest.raises(RuntimeError, match="async context manager"):
        await client.list_tasks()


def request_bodies(platform: FakePlatform, path: str) -> list[dict[str, Any]]:
    return [
        request.body
        for request in platform.requests
        if request.path == path and isinstance(request.body, dict)
    ]
