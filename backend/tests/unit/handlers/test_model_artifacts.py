import random
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from dataforce_studio.handlers.model_artifacts import ModelArtifactHandler
from dataforce_studio.infra.exceptions import (
    ApplicationError,
    ModelArtifactNotFoundError,
)
from dataforce_studio.schemas.bucket_secrets import BucketSecret
from dataforce_studio.schemas.model_artifacts import (
    Manifest,
    ModelArtifact,
    ModelArtifactIn,
    ModelArtifactStatus,
    ModelArtifactUpdate,
    ModelArtifactUpdateIn,
)
from dataforce_studio.schemas.orbit import OrbitRole
from dataforce_studio.schemas.organization import OrgRole

handler = ModelArtifactHandler()


@pytest.fixture
def manifest_example() -> Manifest:
    return Manifest(
        **{
            "variant": "pipeline",
            "description": "",
            "producer_name": "falcon.beastbyte.ai",
            "producer_version": "0.8.0",
            "producer_tags": [
                "falcon.beastbyte.ai::tabular_classification:v1",
                "dataforce.studio::tabular_classification:v1",
            ],
            "inputs": [
                {
                    "name": "sepal.length",
                    "content_type": "NDJSON",
                    "dtype": "Array[float32]",
                    "shape": ["batch", 1],
                    "tags": ["falcon.beastbyte.ai::numeric:v1"],
                },
            ],
            "outputs": [
                {
                    "name": "y_pred",
                    "content_type": "NDJSON",
                    "dtype": "Array[string]",
                    "shape": ["batch"],
                }
            ],
            "dynamic_attributes": [],
            "env_vars": [],
        }
    )


@pytest.fixture
def test_bucket() -> BucketSecret:
    return BucketSecret(
        id=1,
        organization_id=1,
        endpoint="url",
        bucket_name="name",
        access_key="access_key",
        secret_key="secret_key",
        session_token="session_token",
        secure=True,
        region="region",
        cert_check=True,
        created_at=datetime.now(),
    )


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactRepository.create_model_artifact",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactHandler._get_secret_or_raise",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.S3Service.get_upload_url",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_model_artifact_with_tags(
    mock_get_upload_url: AsyncMock,
    mock_get_secret_or_raise: AsyncMock,
    mock_create_model_artifact: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
    test_bucket: BucketSecret,
    manifest_example: Manifest,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

    model_artifact = ModelArtifact(
        id=1,
        collection_id=collection_id,
        file_name="model",
        model_name=None,
        metrics={},
        manifest=manifest_example,
        file_hash="hash",
        file_index={},
        bucket_location="loc",
        size=1,
        unique_identifier="uid",
        tags=["tag"],
        status=ModelArtifactStatus.PENDING_UPLOAD,
        created_at=datetime.now(),
        updated_at=None,
    )

    mock_secret = test_bucket

    mock_create_model_artifact.return_value = model_artifact
    mock_get_orbit_simple.return_value = type(
        "obj",
        (),
        {"bucket_secret_id": 1, "organization_id": organization_id},
    )
    mock_get_collection.return_value = type("obj", (), {"orbit_id": orbit_id})
    mock_get_secret_or_raise.return_value = mock_secret
    mock_get_upload_url.return_value = "url"
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER
    model_artifact_in = ModelArtifactIn(
        metrics={},
        manifest=manifest_example,
        file_hash="hash",
        file_index={},
        size=1,
        file_name="file.txt",
        model_name=None,
        tags=["tag"],
    )
    result_model_artifact, url = await handler.create_model_artifact(
        user_id,
        organization_id,
        orbit_id,
        collection_id,
        model_artifact_in,
    )

    assert result_model_artifact == model_artifact
    assert url == "url"
    mock_create_model_artifact.assert_awaited_once()
    mock_get_secret_or_raise.assert_awaited_once_with(1)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactRepository.get_model_artifact",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactHandler._get_secret_or_raise",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.S3Service.get_download_url",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_model_artifact(
    mock_get_download_url: AsyncMock,
    mock_get_secret_or_raise: AsyncMock,
    mock_get_model_artifact: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
    test_bucket: BucketSecret,
    manifest_example: Manifest,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    model_artifact_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

    model_artifact = ModelArtifact(
        id=model_artifact_id,
        collection_id=1,
        file_name="model",
        model_name=None,
        metrics={},
        manifest=manifest_example,
        file_hash="hash",
        file_index={},
        bucket_location="loc",
        size=1,
        unique_identifier="uid",
        status=ModelArtifactStatus.UPLOADED,
        created_at=datetime.now(),
        updated_at=None,
    )

    mock_secret = test_bucket

    mock_get_model_artifact.return_value = model_artifact
    mock_get_orbit_simple.return_value = type("obj", (), {"bucket_secret_id": 1})
    mock_get_orbit_simple.return_value = type(
        "obj",
        (),
        {"bucket_secret_id": 1, "organization_id": organization_id},
    )
    mock_get_collection.return_value = type("obj", (), {"orbit_id": orbit_id})
    mock_get_secret_or_raise.return_value = mock_secret
    mock_get_download_url.return_value = "url"
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

    result_model_artifact, url = await handler.get_model_artifact(
        user_id, organization_id, orbit_id, collection_id, model_artifact_id
    )

    assert result_model_artifact == model_artifact
    assert url == "url"
    mock_get_model_artifact.assert_awaited_once_with(model_artifact_id, collection_id)
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_secret_or_raise.assert_awaited_once_with(1)
    mock_get_download_url.assert_awaited_once_with(model_artifact.bucket_location)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactRepository.get_model_artifact",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.S3Service.get_download_url",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_model_artifact_not_found(
    mock_get_download_url: AsyncMock,
    mock_get_model_artifact: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    model_artifact_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

    mock_get_model_artifact.return_value = None
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER
    mock_get_orbit_simple.return_value = type(
        "obj",
        (),
        {"bucket_secret_id": 1, "organization_id": organization_id},
    )
    mock_get_collection.return_value = type("obj", (), {"orbit_id": orbit_id})

    with pytest.raises(ModelArtifactNotFoundError) as error:
        await handler.get_model_artifact(
            user_id, organization_id, orbit_id, collection_id, model_artifact_id
        )

    assert error.value.status_code == 404
    mock_get_model_artifact.assert_awaited_once_with(model_artifact_id, collection_id)
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_download_url.assert_not_called()


@patch(
    "dataforce_studio.handlers.model_artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactRepository.get_model_artifact",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactHandler._get_secret_or_raise",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.S3Service.get_download_url",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_request_download_url(
    mock_get_download_url: AsyncMock,
    mock_get_secret_or_raise: AsyncMock,
    mock_get_model_artifact: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
    mock_get_collection: AsyncMock,
    test_bucket: BucketSecret,
    manifest_example: Manifest,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    model_artifact_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

    model_artifact = ModelArtifact(
        id=model_artifact_id,
        collection_id=1,
        file_name="model",
        model_name=None,
        metrics={},
        manifest=manifest_example,
        file_hash="hash",
        file_index={},
        bucket_location="loc",
        size=1,
        unique_identifier="uid",
        status=ModelArtifactStatus.UPLOADED,
        created_at=datetime.now(),
        updated_at=None,
    )

    mock_secret = test_bucket

    mock_get_model_artifact.return_value = model_artifact
    mock_get_orbit_simple.return_value = type(
        "obj",
        (),
        {"bucket_secret_id": 1, "organization_id": organization_id},
    )
    mock_get_collection.return_value = type(
        "obj",
        (),
        {"id": collection_id, "orbit_id": orbit_id},
    )
    mock_get_secret_or_raise.return_value = mock_secret
    mock_get_download_url.return_value = "url"
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

    url = await handler.request_download_url(
        user_id, organization_id, orbit_id, collection_id, model_artifact_id
    )

    assert url == "url"
    mock_get_secret_or_raise.assert_awaited_once_with(1)
    mock_get_download_url.assert_awaited_once_with(model_artifact.bucket_location)


@patch(
    "dataforce_studio.handlers.model_artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactRepository.get_model_artifact",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactRepository.update_status",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactHandler._get_secret_or_raise",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.S3Service.get_delete_url",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_request_delete_url(
    mock_get_delete_url: AsyncMock,
    mock_get_secret_or_raise: AsyncMock,
    mock_update_status: AsyncMock,
    mock_get_model_artifact: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
    mock_get_collection: AsyncMock,
    test_bucket: BucketSecret,
    manifest_example: Manifest,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    model_artifact_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

    model_artifact = ModelArtifact(
        id=model_artifact_id,
        collection_id=1,
        file_name="model",
        model_name=None,
        metrics={},
        manifest=manifest_example,
        file_hash="hash",
        file_index={},
        bucket_location="loc",
        size=1,
        unique_identifier="uid",
        status=ModelArtifactStatus.UPLOADED,
        created_at=datetime.now(),
        updated_at=None,
    )

    mock_secret = test_bucket

    mock_get_model_artifact.return_value = model_artifact
    mock_get_orbit_simple.return_value = type(
        "obj",
        (),
        {"bucket_secret_id": 1, "organization_id": organization_id},
    )
    mock_get_collection.return_value = type(
        "obj",
        (),
        {"id": collection_id, "orbit_id": orbit_id},
    )
    mock_get_secret_or_raise.return_value = mock_secret
    mock_get_delete_url.return_value = "url"
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

    url = await handler.request_delete_url(
        user_id, organization_id, orbit_id, collection_id, model_artifact_id
    )

    assert url == "url"
    mock_update_status.assert_awaited_once_with(
        model_artifact_id, ModelArtifactStatus.PENDING_DELETION
    )
    mock_get_secret_or_raise.assert_awaited_once_with(1)
    mock_get_delete_url.assert_awaited_once_with(model_artifact.bucket_location)


@patch(
    "dataforce_studio.handlers.model_artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactRepository.get_model_artifact",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactRepository.delete_model_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_confirm_deletion_pending(
    mock_delete_model_artifact: AsyncMock,
    mock_get_model_artifact: AsyncMock,
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    manifest_example: Manifest,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    model_artifact_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

    model_artifact = ModelArtifact(
        id=model_artifact_id,
        collection_id=1,
        file_name="model",
        model_name=None,
        metrics={},
        manifest=manifest_example,
        file_hash="hash",
        file_index={},
        bucket_location="loc",
        size=1,
        unique_identifier="uid",
        status=ModelArtifactStatus.PENDING_DELETION,
        created_at=datetime.now(),
        updated_at=None,
    )

    mock_get_model_artifact.return_value = model_artifact
    mock_get_orbit_simple.return_value = type(
        "obj",
        (),
        {"bucket_secret_id": 1, "organization_id": organization_id},
    )
    mock_get_collection.return_value = type(
        "obj",
        (),
        {"id": collection_id, "orbit_id": orbit_id},
    )
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

    await handler.confirm_deletion(
        user_id, organization_id, orbit_id, collection_id, model_artifact_id
    )

    mock_get_model_artifact.assert_awaited_once_with(model_artifact_id, collection_id)
    mock_delete_model_artifact.assert_awaited_once_with(model_artifact_id)


@patch(
    "dataforce_studio.handlers.model_artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactRepository.get_model_artifact",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactRepository.delete_model_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_confirm_deletion_not_pending(
    mock_delete: AsyncMock,
    mock_get_model: AsyncMock,
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    manifest_example: Manifest,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    model_artifact_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

    model_artifact = ModelArtifact(
        id=model_artifact_id,
        collection_id=1,
        file_name="model",
        model_name=None,
        metrics={},
        manifest=manifest_example,
        file_hash="hash",
        file_index={},
        bucket_location="loc",
        size=1,
        unique_identifier="uid",
        status=ModelArtifactStatus.UPLOADED,
        created_at=datetime.now(),
        updated_at=None,
    )

    mock_get_model.return_value = model_artifact
    mock_get_orbit_simple.return_value = type(
        "obj",
        (),
        {"bucket_secret_id": 1, "organization_id": organization_id},
    )
    mock_get_collection.return_value = type(
        "obj",
        (),
        {"id": collection_id, "orbit_id": orbit_id},
    )
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

    with pytest.raises(ApplicationError):
        await handler.confirm_deletion(
            user_id,
            organization_id,
            orbit_id,
            collection_id,
            model_artifact_id,
        )

    mock_get_model.assert_awaited_once_with(model_artifact_id, collection_id)
    mock_delete.assert_not_called()


@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactRepository.get_model_artifact",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactRepository.update_model_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_model_artifact(
    mock_update_model_artifact: AsyncMock,
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_model_artifact: AsyncMock,
    manifest_example: Manifest,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    model_artifact_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)
    model_artifact = ModelArtifact(
        id=model_artifact_id,
        collection_id=1,
        file_name="model",
        model_name=None,
        metrics={},
        manifest=manifest_example,
        file_hash="hash",
        file_index={},
        bucket_location="loc",
        size=1,
        unique_identifier="uid",
        status=ModelArtifactStatus.UPLOADED,
        created_at=datetime.now(),
        updated_at=None,
    )

    mock_get_model_artifact.return_value = model_artifact

    tags = ["t1", "t2"]
    expected = ModelArtifact(
        id=model_artifact_id,
        collection_id=1,
        file_name="model",
        model_name=None,
        metrics={},
        manifest=manifest_example,
        file_hash="hash",
        file_index={},
        bucket_location="loc",
        size=1,
        unique_identifier="uid",
        tags=tags,
        status=ModelArtifactStatus.UPLOADED,
        created_at=datetime.now(),
        updated_at=None,
    )

    mock_update_model_artifact.return_value = expected
    mock_get_orbit_simple.return_value = type(
        "obj",
        (),
        {"bucket_secret_id": 1, "organization_id": organization_id},
    )
    mock_get_collection.return_value = type(
        "obj",
        (),
        {"id": collection_id, "orbit_id": orbit_id},
    )
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

    update_in = ModelArtifactUpdateIn(tags=tags)
    result = await handler.update_model_artifact(
        user_id, organization_id, orbit_id, collection_id, model_artifact_id, update_in
    )

    assert result == expected
    expected_update = ModelArtifactUpdate(
        id=model_artifact_id, model_name=None, tags=tags
    )
    mock_update_model_artifact.assert_awaited_once_with(
        model_artifact_id,
        collection_id,
        expected_update,
    )


@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactRepository.get_model_artifact",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactRepository.update_model_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_model_artifact_not_found(
    mock_update_model_artifact: AsyncMock,
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_model_artifact: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    model_artifact_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

    mock_update_model_artifact.return_value = None
    mock_get_orbit_simple.return_value = type(
        "obj",
        (),
        {"bucket_secret_id": 1, "organization_id": organization_id},
    )
    mock_get_collection.return_value = type(
        "obj",
        (),
        {"id": collection_id, "orbit_id": orbit_id},
    )
    mock_get_model_artifact.return_value = None
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

    update_in = ModelArtifactUpdateIn(tags=["t1"])
    with pytest.raises(ModelArtifactNotFoundError):
        await handler.update_model_artifact(
            user_id,
            organization_id,
            orbit_id,
            collection_id,
            model_artifact_id,
            update_in,
        )

    mock_update_model_artifact.assert_not_awaited()
