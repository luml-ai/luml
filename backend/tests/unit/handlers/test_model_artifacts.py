from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from dataforce_studio.handlers.model_artifacts import ModelArtifactHandler
from dataforce_studio.infra.exceptions import (
    ApplicationError,
    BucketSecretNotFoundError,
    CollectionNotFoundError,
    ModelArtifactNotFoundError,
    OrbitNotFoundError,
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
from dataforce_studio.schemas.permissions import Action, Resource
from dataforce_studio.schemas.s3 import PartDetails, UploadDetails

handler = ModelArtifactHandler()


@patch(
    "dataforce_studio.handlers.model_artifacts.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_secret_or_raise(
    mock_get_bucket_secret: AsyncMock, test_bucket: BucketSecret
) -> None:
    expected = test_bucket.model_copy()
    mock_get_bucket_secret.return_value = expected

    secret = await handler._get_secret_or_raise(expected.id)

    assert secret == expected
    assert isinstance(expected, BucketSecret)
    mock_get_bucket_secret.assert_awaited_once()


@patch(
    "dataforce_studio.handlers.model_artifacts.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_secret_or_raise_not_found(mock_get_bucket_secret: AsyncMock) -> None:
    secret_id = 1
    mock_get_bucket_secret.return_value = None

    with pytest.raises(BucketSecretNotFoundError) as error:
        await handler._get_secret_or_raise(secret_id)

    assert error.value.status_code == 404
    mock_get_bucket_secret.assert_awaited_once_with(secret_id)


@patch(
    "dataforce_studio.handlers.model_artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_orbit_and_collection_access(
    mock_get_orbit_simple: AsyncMock, mock_get_collection: AsyncMock
) -> None:
    organization_id = 1
    orbit_id = 1
    collection_id = 1
    orbit = Mock(organization_id=organization_id)
    collection = Mock(orbit_id=orbit_id)

    mock_get_orbit_simple.return_value = orbit
    mock_get_collection.return_value = collection

    result = await handler._check_orbit_and_collection_access(
        organization_id, orbit_id, collection_id
    )

    assert result == (orbit, collection)
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_collection.assert_awaited_once_with(collection_id)


@patch(
    "dataforce_studio.handlers.model_artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_orbit_and_collection_access_orbit_not_found(
    mock_get_orbit_simple: AsyncMock,
) -> None:
    organization_id = 1
    orbit_id = 1
    collection_id = 1

    mock_get_orbit_simple.return_value = None

    with pytest.raises(OrbitNotFoundError) as error:
        await handler._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )

    assert error.value.status_code == 404
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)


@patch(
    "dataforce_studio.handlers.model_artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_orbit_and_collection_access_collection_not_found(
    mock_get_orbit_simple: AsyncMock, mock_get_collection: AsyncMock
) -> None:
    organization_id = 1
    orbit_id = 1
    collection_id = 1
    orbit = Mock(organization_id=organization_id)

    mock_get_orbit_simple.return_value = orbit
    mock_get_collection.return_value = None

    with pytest.raises(CollectionNotFoundError) as error:
        await handler._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )

    assert error.value.status_code == 404
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_collection.assert_awaited_once_with(collection_id)


@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactRepository.get_collection_model_artifact",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_collection_model_artifact(
    mock_check_orbit_action_access: AsyncMock,
    mock_check_orbit_and_collection_access: AsyncMock,
    mock_get_collection_model_artifact: AsyncMock,
    manifest_example: Manifest,
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 1
    collection_id = 1

    expected = [
        ModelArtifact(
            id=1,
            collection_id=collection_id,
            file_name="model1.pkl",
            model_name="model1",
            metrics={"accuracy": 0.95},
            manifest=manifest_example,
            file_hash="hash1",
            file_index={},
            bucket_location="loc1",
            size=100,
            unique_identifier="uid1",
            tags=["tag1"],
            status=ModelArtifactStatus.UPLOADED,
            created_at=datetime.now(),
            updated_at=None,
        )
    ]

    mock_get_collection_model_artifact.return_value = expected

    result = await handler.get_collection_model_artifact(
        user_id, organization_id, orbit_id, collection_id
    )

    assert result == expected
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.MODEL, Action.LIST
    )
    mock_check_orbit_and_collection_access.assert_awaited_once_with(
        organization_id, orbit_id, collection_id
    )
    mock_get_collection_model_artifact.assert_awaited_once_with(collection_id)


@patch(
    "dataforce_studio.handlers.model_artifacts.PermissionsHandler.check_orbit_action_access",
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
    "dataforce_studio.handlers.model_artifacts.ModelArtifactHandler._get_s3_service",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_model_artifact(
    mock_get_s3_service: AsyncMock,
    mock_get_secret_or_raise: AsyncMock,
    mock_create_model_artifact: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_orbit_action_access: AsyncMock,
    test_bucket: BucketSecret,
    manifest_example: Manifest,
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 1
    collection_id = 1

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
    mock_get_orbit_simple.return_value = Mock(
        bucket_secret_id=1, organization_id=organization_id
    )
    mock_get_collection.return_value = Mock(orbit_id=orbit_id)
    mock_get_secret_or_raise.return_value = mock_secret
    mock_s3_service = AsyncMock()
    mock_upload_data = UploadDetails(
        upload_id=None,
        parts=[
            PartDetails(
                part_number=1,
                url="url",
                start_byte=0,
                end_byte=model_artifact.size,
                part_size=model_artifact.size,
            )
        ],
        complete_url=None,
    )
    mock_s3_service.create_upload.return_value = mock_upload_data
    mock_get_s3_service.return_value = mock_s3_service
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
    result = await handler.create_model_artifact(
        user_id,
        organization_id,
        orbit_id,
        collection_id,
        model_artifact_in,
    )

    assert result.model == model_artifact
    assert result.url is not None
    mock_create_model_artifact.assert_awaited_once()
    mock_get_s3_service.assert_awaited_once()
    mock_s3_service.create_upload.assert_awaited_once()


@patch(
    "dataforce_studio.handlers.model_artifacts.PermissionsHandler.check_orbit_action_access",
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
    "dataforce_studio.handlers.model_artifacts.ModelArtifactHandler._get_s3_service",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_model_artifact(
    mock_get_s3_service: AsyncMock,
    mock_get_secret_or_raise: AsyncMock,
    mock_get_model_artifact: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_orbit_action_access: AsyncMock,
    test_bucket: BucketSecret,
    manifest_example: Manifest,
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 1
    model_artifact_id = 1
    collection_id = 1

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
    mock_get_orbit_simple.return_value = Mock(bucket_secret_id=1)
    mock_get_orbit_simple.return_value = Mock(
        bucket_secret_id=1, organization_id=organization_id
    )
    mock_get_collection.return_value = Mock(orbit_id=orbit_id)
    mock_get_secret_or_raise.return_value = mock_secret
    mock_s3_service = AsyncMock()
    mock_s3_service.get_download_url.return_value = "url"
    mock_get_s3_service.return_value = mock_s3_service

    result_model_artifact, url = await handler.get_model_artifact(
        user_id, organization_id, orbit_id, collection_id, model_artifact_id
    )

    assert result_model_artifact == model_artifact
    assert url == "url"
    mock_get_model_artifact.assert_awaited_once_with(model_artifact_id)
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_s3_service.assert_awaited_once()
    mock_s3_service.get_download_url.assert_awaited_once_with(
        model_artifact.bucket_location
    )


@patch(
    "dataforce_studio.handlers.model_artifacts.PermissionsHandler.check_orbit_action_access",
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
    "dataforce_studio.handlers.model_artifacts.ModelArtifactHandler._get_s3_service",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_model_artifact_not_found(
    mock_get_s3_service: AsyncMock,
    mock_get_model_artifact: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_check_orbit_action_access: AsyncMock,
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 1
    model_artifact_id = 1
    collection_id = 1

    mock_get_model_artifact.return_value = None
    mock_get_orbit_simple.return_value = Mock(
        bucket_secret_id=1, organization_id=organization_id
    )
    mock_get_collection.return_value = Mock(orbit_id=orbit_id)

    with pytest.raises(ModelArtifactNotFoundError) as error:
        await handler.get_model_artifact(
            user_id, organization_id, orbit_id, collection_id, model_artifact_id
        )

    assert error.value.status_code == 404
    mock_get_model_artifact.assert_awaited_once_with(model_artifact_id)
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_s3_service.assert_not_awaited()


@patch(
    "dataforce_studio.handlers.model_artifacts.PermissionsHandler.check_orbit_action_access",
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
    "dataforce_studio.handlers.model_artifacts.ModelArtifactHandler._get_secret_or_raise",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactHandler._get_s3_service",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_request_download_url(
    mock_get_s3_service: AsyncMock,
    mock_get_secret_or_raise: AsyncMock,
    mock_get_model_artifact: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_check_orbit_action_access: AsyncMock,
    test_bucket: BucketSecret,
    manifest_example: Manifest,
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 1
    model_artifact_id = 1
    collection_id = 1

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
    mock_get_orbit_simple.return_value = Mock(
        bucket_secret_id=1, organization_id=organization_id
    )
    mock_get_collection.return_value = Mock(id=collection_id, orbit_id=orbit_id)
    mock_get_secret_or_raise.return_value = mock_secret
    mock_s3_service = AsyncMock()
    mock_s3_service.get_download_url.return_value = "url"
    mock_get_s3_service.return_value = mock_s3_service

    url = await handler.request_download_url(
        user_id, organization_id, orbit_id, collection_id, model_artifact_id
    )

    assert url == "url"
    mock_get_s3_service.assert_awaited_once()
    mock_s3_service.get_download_url.assert_awaited_once_with(
        model_artifact.bucket_location
    )


@patch(
    "dataforce_studio.handlers.model_artifacts.PermissionsHandler.check_orbit_action_access",
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
    "dataforce_studio.handlers.model_artifacts.ModelArtifactRepository.update_status",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactHandler._get_secret_or_raise",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.model_artifacts.ModelArtifactHandler._get_s3_service",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_request_delete_url(
    mock_get_s3_service: AsyncMock,
    mock_get_secret_or_raise: AsyncMock,
    mock_update_status: AsyncMock,
    mock_get_model_artifact: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_check_orbit_action_access: AsyncMock,
    test_bucket: BucketSecret,
    manifest_example: Manifest,
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 1
    model_artifact_id = 1
    collection_id = 1

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
    mock_get_orbit_simple.return_value = Mock(
        bucket_secret_id=1, organization_id=organization_id
    )
    mock_get_collection.return_value = Mock(id=collection_id, orbit_id=orbit_id)
    mock_get_secret_or_raise.return_value = mock_secret
    mock_s3_service = AsyncMock()
    mock_s3_service.get_delete_url.return_value = "url"
    mock_get_s3_service.return_value = mock_s3_service

    url = await handler.request_delete_url(
        user_id, organization_id, orbit_id, collection_id, model_artifact_id
    )

    assert url == "url"
    mock_update_status.assert_awaited_once_with(
        model_artifact_id, ModelArtifactStatus.PENDING_DELETION
    )
    mock_get_s3_service.assert_awaited_once()
    mock_s3_service.get_delete_url.assert_awaited_once_with(
        model_artifact.bucket_location
    )


@patch(
    "dataforce_studio.handlers.model_artifacts.PermissionsHandler.check_orbit_action_access",
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
    "dataforce_studio.handlers.model_artifacts.ModelArtifactRepository.delete_model_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_confirm_deletion_pending(
    mock_delete_model_artifact: AsyncMock,
    mock_get_model_artifact: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_check_orbit_action_access: AsyncMock,
    manifest_example: Manifest,
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 1
    model_artifact_id = 1
    collection_id = 1

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
    mock_get_orbit_simple.return_value = Mock(
        bucket_secret_id=1, organization_id=organization_id
    )
    mock_get_collection.return_value = Mock(id=collection_id, orbit_id=orbit_id)

    await handler.confirm_deletion(
        user_id, organization_id, orbit_id, collection_id, model_artifact_id
    )

    mock_get_model_artifact.assert_awaited_once_with(model_artifact_id)
    mock_delete_model_artifact.assert_awaited_once_with(model_artifact_id)


@patch(
    "dataforce_studio.handlers.model_artifacts.PermissionsHandler.check_orbit_action_access",
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
    "dataforce_studio.handlers.model_artifacts.ModelArtifactRepository.delete_model_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_confirm_deletion_not_pending(
    mock_delete: AsyncMock,
    mock_get_model: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_check_orbit_action_access: AsyncMock,
    manifest_example: Manifest,
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 1
    model_artifact_id = 1
    collection_id = 1

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
    mock_get_orbit_simple.return_value = Mock(
        bucket_secret_id=1, organization_id=organization_id
    )
    mock_get_collection.return_value = Mock(id=collection_id, orbit_id=orbit_id)

    with pytest.raises(ApplicationError):
        await handler.confirm_deletion(
            user_id,
            organization_id,
            orbit_id,
            collection_id,
            model_artifact_id,
        )

    mock_get_model.assert_awaited_once_with(model_artifact_id)
    mock_delete.assert_not_called()


@patch(
    "dataforce_studio.handlers.model_artifacts.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
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
    "dataforce_studio.handlers.model_artifacts.ModelArtifactRepository.update_model_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_model_artifact(
    mock_update_model_artifact: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_model_artifact: AsyncMock,
    mock_check_orbit_action_access: AsyncMock,
    manifest_example: Manifest,
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 1
    model_artifact_id = 1
    collection_id = 1

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
    mock_get_orbit_simple.return_value = Mock(
        bucket_secret_id=1, organization_id=organization_id
    )
    mock_get_collection.return_value = Mock(id=collection_id, orbit_id=orbit_id)

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
    "dataforce_studio.handlers.model_artifacts.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
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
    "dataforce_studio.handlers.model_artifacts.ModelArtifactRepository.update_model_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_model_artifact_not_found(
    mock_update_model_artifact: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_model_artifact: AsyncMock,
    mock_check_orbit_action_access: AsyncMock,
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 1
    model_artifact_id = 1
    collection_id = 1

    mock_update_model_artifact.return_value = None
    mock_get_orbit_simple.return_value = Mock(
        bucket_secret_id=1, organization_id=organization_id
    )
    mock_get_collection.return_value = Mock(id=collection_id, orbit_id=orbit_id)
    mock_get_model_artifact.return_value = None

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
