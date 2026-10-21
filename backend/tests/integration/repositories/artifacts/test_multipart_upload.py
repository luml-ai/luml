from uuid import uuid4

import pytest
from luml.repositories.artifacts import ArtifactRepository
from luml.schemas.artifacts import ArtifactCreate, ArtifactStatus

from tests.support.seeds import CollectionFixtureData


@pytest.mark.parametrize("status", list(ArtifactStatus))
async def test_multipart_location_requires_pending_upload_artifact(
    repository: ArtifactRepository,
    seeded_collection: CollectionFixtureData,
    new_artifact: ArtifactCreate,
    status: ArtifactStatus,
) -> None:
    data = new_artifact.model_copy(
        update={"collection_id": seeded_collection.collection.id, "status": status}
    )
    artifact = await repository.create_artifact(data)

    orbit_id = await repository.get_pending_upload_orbit(
        seeded_collection.bucket_secret.id,
        seeded_collection.organization.id,
        artifact.bucket_location,
    )

    assert orbit_id == (
        seeded_collection.orbit.id if status == ArtifactStatus.PENDING_UPLOAD else None
    )


@pytest.mark.parametrize("mismatch", ["bucket", "organization", "location"])
async def test_multipart_location_must_match_bucket_and_organization(
    repository: ArtifactRepository,
    seeded_collection: CollectionFixtureData,
    new_artifact: ArtifactCreate,
    mismatch: str,
) -> None:
    data = new_artifact.model_copy(
        update={"collection_id": seeded_collection.collection.id}
    )
    artifact = await repository.create_artifact(data)

    result = await repository.get_pending_upload_orbit(
        uuid4() if mismatch == "bucket" else seeded_collection.bucket_secret.id,
        uuid4() if mismatch == "organization" else seeded_collection.organization.id,
        artifact.bucket_location + "/other"
        if mismatch == "location"
        else artifact.bucket_location,
    )

    assert result is None
