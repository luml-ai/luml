import httpx
import pytest

from luml_satellite import PlatformClient, TokenDeriver
from luml_satellite.serving import create_internal_application
from luml_satellite.testing import FakePlatform
from luml_satellite.workload import ArtifactResolver
from tests.helpers import ARTIFACT_ID, DEPLOYMENT_ID, deployment_record


@pytest.mark.asyncio
async def test_artifact_route_validates_its_token_and_maps_platform_outcomes() -> None:
    platform = FakePlatform()
    platform.add_deployment(deployment_record())
    platform.add_artifact(ARTIFACT_ID, b"artifact")
    tokens = TokenDeriver("derivation-key")
    token = tokens.artifact_token(DEPLOYMENT_ID)

    async with PlatformClient(
        "http://platform",
        platform.token,
        transport=platform.transport,
    ) as platform_client:
        application = create_internal_application(ArtifactResolver(platform_client, tokens))
        assert application.openapi()["paths"] == {}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application),
            base_url="http://satellite",
        ) as client:
            success = await client.get(
                f"/satellites/deployments/{DEPLOYMENT_ID}/artifact",
                headers={"X-Artifact-Token": token},
            )
            missing_token = await client.get(f"/satellites/deployments/{DEPLOYMENT_ID}/artifact")
            wrong_token = await client.get(
                f"/satellites/deployments/{DEPLOYMENT_ID}/artifact",
                headers={"X-Artifact-Token": tokens.artifact_token("another")},
            )
            unknown_id = "10000000-0000-0000-0000-000000000099"
            unknown = await client.get(
                f"/satellites/deployments/{unknown_id}/artifact",
                headers={"X-Artifact-Token": tokens.artifact_token(unknown_id)},
            )
            platform.script_responses(
                "GET",
                f"/satellites/v1/deployments/{DEPLOYMENT_ID}",
                (500, {"detail": "down"}),
            )
            failed = await client.get(
                f"/satellites/deployments/{DEPLOYMENT_ID}/artifact",
                headers={"X-Artifact-Token": token},
            )

    assert success.status_code == 200
    assert success.json()["artifact_id"] == ARTIFACT_ID
    assert success.json()["url"].endswith(f"/__fake__/artifacts/{ARTIFACT_ID}")
    assert missing_token.status_code == 403
    assert wrong_token.status_code == 403
    assert unknown.status_code == 404
    assert failed.status_code == 502
