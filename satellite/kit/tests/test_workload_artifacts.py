from datetime import UTC, datetime

import pytest

from luml_satellite import Deployment, PlatformClient, TokenDeriver
from luml_satellite.testing import FakePlatform, InMemoryArtifactPusher
from luml_satellite.workload import (
    ArtifactDeliveryMode,
    ArtifactResolutionError,
    ArtifactResolver,
    ArtifactTokenError,
    presigned_expiry,
)
from tests.helpers import ARTIFACT_ID, DEPLOYMENT_ID, deployment_record


@pytest.mark.asyncio
async def test_artifact_resolver_supports_on_demand_and_verifies_tokens() -> None:
    platform = FakePlatform()
    platform.add_deployment(deployment_record())
    platform.add_artifact(ARTIFACT_ID, b"artifact")
    deployment = Deployment.model_validate(deployment_record())
    tokens = TokenDeriver("satellite-token")

    async with PlatformClient(
        "http://platform",
        platform.token,
        transport=platform.transport,
    ) as client:
        resolver = ArtifactResolver(
            client,
            tokens,
            satellite_address="http://satellite-internal/",
        )
        handle = await resolver.resolve(deployment, ArtifactDeliveryMode.ON_DEMAND)
        download = await resolver.resolve_download(DEPLOYMENT_ID, handle.token)

        assert handle.download_url is None
        assert handle.refresh_url == (
            f"http://satellite-internal/satellites/deployments/{DEPLOYMENT_ID}/artifact"
        )
        assert handle.artifact_id == ARTIFACT_ID
        assert download.artifact_id == ARTIFACT_ID
        assert download.url.endswith(f"/__fake__/artifacts/{ARTIFACT_ID}")
        assert resolver.verify_token(DEPLOYMENT_ID, handle.token)
        assert not resolver.verify_token("another-deployment", handle.token)

        request_count = len(platform.requests)
        with pytest.raises(ArtifactTokenError, match="invalid artifact token"):
            await resolver.resolve_download(DEPLOYMENT_ID, "wrong")
        assert len(platform.requests) == request_count


@pytest.mark.asyncio
async def test_on_demand_resolution_requires_an_address() -> None:
    platform = FakePlatform()
    deployment = Deployment.model_validate(deployment_record())

    async with PlatformClient(
        "http://platform",
        platform.token,
        transport=platform.transport,
    ) as client:
        resolver = ArtifactResolver(client, TokenDeriver("token"))
        with pytest.raises(ArtifactResolutionError, match="requires a satellite address"):
            await resolver.resolve(deployment, ArtifactDeliveryMode.ON_DEMAND)


@pytest.mark.asyncio
async def test_presigned_and_push_modes_use_the_platform_download() -> None:
    platform = FakePlatform()
    platform.add_artifact(ARTIFACT_ID, b"artifact")
    deployment = Deployment.model_validate(deployment_record())
    pusher = InMemoryArtifactPusher()

    async with PlatformClient(
        "http://platform",
        platform.token,
        transport=platform.transport,
    ) as client:
        resolver = ArtifactResolver(
            client,
            TokenDeriver("token"),
            satellite_address="http://satellite",
            pusher=pusher,
        )
        presigned = await resolver.resolve(deployment, ArtifactDeliveryMode.PRESIGNED_LINK)
        pushed = await resolver.resolve(deployment, ArtifactDeliveryMode.PUSH)

    assert presigned.download_url is not None
    assert presigned.download_url.endswith(f"/__fake__/artifacts/{ARTIFACT_ID}")
    assert presigned.token is not None
    assert pushed.provider_ref == f"memory://artifacts/{ARTIFACT_ID}"
    assert pusher.pushed[0].deployment_id == DEPLOYMENT_ID
    assert pusher.pushed[0].artifact.artifact_id == ARTIFACT_ID


@pytest.mark.asyncio
async def test_push_mode_requires_a_pusher() -> None:
    platform = FakePlatform()
    platform.add_artifact(ARTIFACT_ID, b"artifact")
    deployment = Deployment.model_validate(deployment_record())

    async with PlatformClient(
        "http://platform",
        platform.token,
        transport=platform.transport,
    ) as client:
        resolver = ArtifactResolver(client, TokenDeriver("token"))
        with pytest.raises(ArtifactResolutionError, match="requires an artifact pusher"):
            await resolver.resolve(deployment, ArtifactDeliveryMode.PUSH)


def test_presigned_expiry_reads_amazon_query_parameters() -> None:
    url = "https://store.example/model?X-Amz-Date=20260919T120000Z&X-Amz-Expires=90"

    assert presigned_expiry(url) == datetime(2026, 9, 19, 12, 1, 30, tzinfo=UTC)
    assert presigned_expiry("https://store.example/model") is None
    assert (
        presigned_expiry("https://store.example/model?X-Amz-Date=invalid&X-Amz-Expires=90") is None
    )
