import random
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from dataforce_studio.handlers.ml_models import MLModelHandler
from dataforce_studio.infra.exceptions import ApplicationError, MLModelNotFoundError
from dataforce_studio.schemas.ml_models import (
    Manifest,
    MLModel,
    MLModelIn,
    MLModelStatus,
    MLModelUpdate,
    MLModelUpdateIn,
)
from dataforce_studio.schemas.orbit import OrbitRole
from dataforce_studio.schemas.organization import OrgRole

handler = MLModelHandler()


manifest_example_obj = Manifest(
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


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.MLModelRepository.create_ml_model",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.MLModelHandler._get_presigned_url",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_ml_model_with_tags(
    mock_get_presigned: AsyncMock,
    mock_create_model: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

    model = MLModel(
        id=1,
        collection_id=collection_id,
        file_name="model",
        model_name=None,
        metrics={},
        manifest=manifest_example_obj,
        file_hash="hash",
        file_index={},
        bucket_location="loc",
        size=1,
        unique_identifier="uid",
        tags=["tag"],
        status=MLModelStatus.PENDING_UPLOAD,
        created_at=datetime.utcnow(),
        updated_at=None,
    )

    mock_create_model.return_value = model
    mock_get_orbit_simple.return_value = type(
        "obj",
        (),
        {"bucket_secret_id": 1, "organization_id": organization_id},
    )
    mock_get_collection.return_value = type("obj", (), {"orbit_id": orbit_id})
    mock_get_presigned.return_value = "url"
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER
    ml_model_in = MLModelIn(
        metrics={},
        manifest=manifest_example_obj,
        file_hash="hash",
        file_index={},
        size=1,
        file_name="file.txt",
        model_name=None,
        tags=["tag"],
    )
    result_model, url = await handler.create_ml_model(
        user_id,
        organization_id,
        orbit_id,
        collection_id,
        ml_model_in,
    )

    assert result_model == model
    assert url == "url"
    mock_create_model.assert_awaited_once()
    mock_get_presigned.assert_awaited_once()


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.MLModelRepository.get_ml_model",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.MLModelHandler._get_download_url",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_ml_model(
    mock_get_download_url: AsyncMock,
    mock_get_model: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    model_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

    model = MLModel(
        id=model_id,
        collection_id=1,
        file_name="model",
        model_name=None,
        metrics={},
        manifest=manifest_example_obj,
        file_hash="hash",
        file_index={},
        bucket_location="loc",
        size=1,
        unique_identifier="uid",
        status=MLModelStatus.UPLOADED,
        created_at=datetime.utcnow(),
        updated_at=None,
    )

    mock_get_model.return_value = model
    mock_get_orbit_simple.return_value = type("obj", (), {"bucket_secret_id": 1})
    mock_get_orbit_simple.return_value = type(
        "obj",
        (),
        {"bucket_secret_id": 1, "organization_id": organization_id},
    )
    mock_get_collection.return_value = type("obj", (), {"orbit_id": orbit_id})
    mock_get_download_url.return_value = "url"
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

    result_model, url = await handler.get_ml_model(
        user_id, organization_id, orbit_id, collection_id, model_id
    )

    assert result_model == model
    assert url == "url"
    mock_get_model.assert_awaited_once_with(model_id, collection_id)
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_download_url.assert_awaited_once_with(1, model.bucket_location)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.MLModelRepository.get_ml_model",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.MLModelHandler._get_download_url",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_ml_model_not_found(
    mock_get_download_url: AsyncMock,
    mock_get_model: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    model_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

    mock_get_model.return_value = None
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER
    mock_get_orbit_simple.return_value = type(
        "obj",
        (),
        {"bucket_secret_id": 1, "organization_id": organization_id},
    )
    mock_get_collection.return_value = type("obj", (), {"orbit_id": orbit_id})

    with pytest.raises(MLModelNotFoundError) as error:
        await handler.get_ml_model(
            user_id, organization_id, orbit_id, collection_id, model_id
        )

    assert error.value.status_code == 404
    mock_get_model.assert_awaited_once_with(model_id, collection_id)
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_download_url.assert_not_called()


@patch(
    "dataforce_studio.handlers.ml_models.CollectionRepository.get_collection",
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
    "dataforce_studio.handlers.ml_models.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.MLModelRepository.get_ml_model",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.MLModelHandler._get_download_url",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_request_download_url(
    mock_get_download_url: AsyncMock,
    mock_get_model: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
    mock_get_collection: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    model_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

    model = MLModel(
        id=model_id,
        collection_id=1,
        file_name="model",
        model_name=None,
        metrics={},
        manifest=manifest_example_obj,
        file_hash="hash",
        file_index={},
        bucket_location="loc",
        size=1,
        unique_identifier="uid",
        status=MLModelStatus.UPLOADED,
        created_at=datetime.utcnow(),
        updated_at=None,
    )

    mock_get_model.return_value = model
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
    mock_get_download_url.return_value = "url"
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

    url = await handler.request_download_url(
        user_id, organization_id, orbit_id, collection_id, model_id
    )

    assert url == "url"
    mock_get_download_url.assert_awaited_once_with(1, model.bucket_location)


@patch(
    "dataforce_studio.handlers.ml_models.CollectionRepository.get_collection",
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
    "dataforce_studio.handlers.ml_models.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.MLModelRepository.get_ml_model",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.MLModelRepository.update_status",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.MLModelHandler._get_delete_url",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_request_delete_url(
    mock_get_delete_url: AsyncMock,
    mock_update_status: AsyncMock,
    mock_get_model: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
    mock_get_collection: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    model_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

    model = MLModel(
        id=model_id,
        collection_id=1,
        file_name="model",
        model_name=None,
        metrics={},
        manifest=manifest_example_obj,
        file_hash="hash",
        file_index={},
        bucket_location="loc",
        size=1,
        unique_identifier="uid",
        status=MLModelStatus.UPLOADED,
        created_at=datetime.utcnow(),
        updated_at=None,
    )

    mock_get_model.return_value = model
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
    mock_get_delete_url.return_value = "url"
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

    url = await handler.request_delete_url(
        user_id, organization_id, orbit_id, collection_id, model_id
    )

    assert url == "url"
    mock_update_status.assert_awaited_once_with(
        model_id, MLModelStatus.PENDING_DELETION
    )
    mock_get_delete_url.assert_awaited_once_with(1, model.bucket_location)


@patch(
    "dataforce_studio.handlers.ml_models.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.OrbitRepository.get_orbit_simple",
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
    "dataforce_studio.handlers.ml_models.MLModelRepository.get_ml_model",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.MLModelRepository.delete_ml_model",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_confirm_deletion_pending(
    mock_delete: AsyncMock,
    mock_get_model: AsyncMock,
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    model_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

    model = MLModel(
        id=model_id,
        collection_id=1,
        file_name="model",
        model_name=None,
        metrics={},
        manifest=manifest_example_obj,
        file_hash="hash",
        file_index={},
        bucket_location="loc",
        size=1,
        unique_identifier="uid",
        status=MLModelStatus.PENDING_DELETION,
        created_at=datetime.utcnow(),
        updated_at=None,
    )

    mock_get_model.return_value = model
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
        user_id, organization_id, orbit_id, collection_id, model_id
    )

    mock_get_model.assert_awaited_once_with(model_id, collection_id)
    mock_delete.assert_awaited_once_with(model_id)


@patch(
    "dataforce_studio.handlers.ml_models.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.OrbitRepository.get_orbit_simple",
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
    "dataforce_studio.handlers.ml_models.MLModelRepository.get_ml_model",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.MLModelRepository.delete_ml_model",
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
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    model_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

    model = MLModel(
        id=model_id,
        collection_id=1,
        file_name="model",
        model_name=None,
        metrics={},
        manifest=manifest_example_obj,
        file_hash="hash",
        file_index={},
        bucket_location="loc",
        size=1,
        unique_identifier="uid",
        status=MLModelStatus.UPLOADED,
        created_at=datetime.utcnow(),
        updated_at=None,
    )

    mock_get_model.return_value = model
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
            model_id,
        )

    mock_get_model.assert_awaited_once_with(model_id, collection_id)
    mock_delete.assert_not_called()


@patch(
    "dataforce_studio.handlers.ml_models.MLModelRepository.get_ml_model",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.OrbitRepository.get_orbit_simple",
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
    "dataforce_studio.handlers.ml_models.MLModelRepository.update_ml_model",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_model(
    mock_update: AsyncMock,
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_model: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    model_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)
    model = MLModel(
        id=model_id,
        collection_id=1,
        file_name="model",
        model_name=None,
        metrics={},
        manifest=manifest_example_obj,
        file_hash="hash",
        file_index={},
        bucket_location="loc",
        size=1,
        unique_identifier="uid",
        status=MLModelStatus.UPLOADED,
        created_at=datetime.utcnow(),
        updated_at=None,
    )

    mock_get_model.return_value = model

    tags = ["t1", "t2"]
    expected = MLModel(
        id=model_id,
        collection_id=1,
        file_name="model",
        model_name=None,
        metrics={},
        manifest=manifest_example_obj,
        file_hash="hash",
        file_index={},
        bucket_location="loc",
        size=1,
        unique_identifier="uid",
        tags=tags,
        status=MLModelStatus.UPLOADED,
        created_at=datetime.utcnow(),
        updated_at=None,
    )

    mock_update.return_value = expected
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

    update_in = MLModelUpdateIn(tags=tags)
    result = await handler.update_model(
        user_id, organization_id, orbit_id, collection_id, model_id, update_in
    )

    assert result == expected
    expected_update = MLModelUpdate(id=model_id, model_name=None, tags=tags)
    mock_update.assert_awaited_once_with(
        model_id,
        collection_id,
        expected_update,
    )


@patch(
    "dataforce_studio.handlers.ml_models.MLModelRepository.get_ml_model",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.ml_models.OrbitRepository.get_orbit_simple",
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
    "dataforce_studio.handlers.ml_models.MLModelRepository.update_ml_model",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_model_not_found(
    mock_update: AsyncMock,
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_ml_model: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    model_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

    mock_update.return_value = None
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
    mock_get_ml_model.return_value = None
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

    update_in = MLModelUpdateIn(tags=["t1"])
    with pytest.raises(MLModelNotFoundError):
        await handler.update_model(
            user_id, organization_id, orbit_id, collection_id, model_id, update_in
        )

    mock_update.assert_not_awaited()
