from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from luml.handlers.orbits import OrbitHandler
from luml.handlers.permissions import PermissionsHandler
from luml.infra.db import engine as shared_engine
from luml.infra.exceptions import OrbitError
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.bucket_secrets import BucketSecretRepository
from luml.repositories.orbits import OrbitRepository
from luml.schemas.artifacts import ArtifactCreate, ArtifactStatus
from luml.schemas.bucket_secrets import S3BucketSecretCreate
from luml.schemas.orbit import OrbitUpdate

from tests.support.seeds import CollectionFixtureData, OrbitFixtureData


@pytest.fixture
async def handler(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[OrbitHandler]:
    monkeypatch.setattr(PermissionsHandler, "check_permissions", AsyncMock())
    await shared_engine.dispose()
    yield OrbitHandler()
    await shared_engine.dispose()


class TestOrbitHandler:
    @pytest.mark.parametrize("status", list(ArtifactStatus))
    async def test_bucket_change_with_artifacts_preserves_original_orbit(
        self,
        handler: OrbitHandler,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
        status: ArtifactStatus,
    ) -> None:
        data = seeded_collection
        await ArtifactRepository(data.engine).create_artifact(
            new_artifact.model_copy(
                update={"collection_id": data.collection.id, "status": status}
            )
        )
        new_secret = await BucketSecretRepository(data.engine).create_bucket_secret(
            S3BucketSecretCreate(
                organization_id=data.organization.id,
                endpoint="s3",
                bucket_name="other-bucket",
                region="us-east-1",
            )
        )

        with pytest.raises(
            OrbitError,
            match="Cannot change bucket secret while orbit contains artifacts",
        ) as error:
            await handler.update_orbit(
                data.user.id,
                data.organization.id,
                data.orbit.id,
                OrbitUpdate(name="renamed", bucket_secret_id=new_secret.id),
            )

        assert error.value.status_code == 409
        unchanged = await OrbitRepository(data.engine).get_orbit_simple(
            data.orbit.id, data.organization.id
        )
        assert unchanged is not None
        assert unchanged.name == data.orbit.name
        assert unchanged.bucket_secret_id == data.bucket_secret.id
        assert unchanged.total_artifacts == 1

    @pytest.mark.parametrize("include_bucket_secret", [False, True])
    async def test_rename_with_artifacts_preserves_bucket_secret(
        self,
        handler: OrbitHandler,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
        include_bucket_secret: bool,
    ) -> None:
        data = seeded_collection
        await ArtifactRepository(data.engine).create_artifact(
            new_artifact.model_copy(update={"collection_id": data.collection.id})
        )
        update = OrbitUpdate(name="renamed")
        if include_bucket_secret:
            update.bucket_secret_id = data.bucket_secret.id

        await handler.update_orbit(
            data.user.id, data.organization.id, data.orbit.id, update
        )

        updated = await OrbitRepository(data.engine).get_orbit_simple(
            data.orbit.id, data.organization.id
        )
        assert updated is not None
        assert updated.name == "renamed"
        assert updated.bucket_secret_id == data.bucket_secret.id
        assert updated.total_artifacts == 1

    async def test_empty_orbit_can_change_bucket_secret(
        self, handler: OrbitHandler, seeded_orbit: OrbitFixtureData
    ) -> None:
        data = seeded_orbit
        new_secret = await BucketSecretRepository(data.engine).create_bucket_secret(
            S3BucketSecretCreate(
                organization_id=data.organization.id,
                endpoint="s3",
                bucket_name="other-bucket",
                region="us-east-1",
            )
        )

        await handler.update_orbit(
            data.user.id,
            data.organization.id,
            data.orbit.id,
            OrbitUpdate(bucket_secret_id=new_secret.id),
        )

        updated = await OrbitRepository(data.engine).get_orbit_simple(
            data.orbit.id, data.organization.id
        )
        assert updated is not None
        assert updated.bucket_secret_id == new_secret.id
        assert updated.total_artifacts == 0
