from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest
import uuid6

from dataforce_studio.handlers.collections import CollectionHandler
from dataforce_studio.infra.exceptions import CollectionDeleteError, NotFoundError
from dataforce_studio.schemas.model_artifacts import (
    Collection,
    CollectionCreate,
    CollectionCreateIn,
    CollectionType,
    CollectionUpdate,
    CollectionUpdateIn,
)
from dataforce_studio.schemas.permissions import Action, Resource

handler = CollectionHandler()


@patch(
    "dataforce_studio.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.CollectionRepository.create_collection",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_collection(
    mock_create: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_permissions: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    data = CollectionCreateIn(
        description="d",
        name="n",
        collection_type=CollectionType.MODEL,
        tags=["t1"],
    )
    expected = Collection(
        id=collection_id,
        created_at=datetime.now(),
        orbit_id=orbit_id,
        total_models=0,
        **data.model_dump(),
    )

    mock_create.return_value = expected
    mock_get_orbit_simple.return_value = Mock(organization_id=organization_id)

    result = await handler.create_collection(user_id, organization_id, orbit_id, data)

    assert result == expected
    expected_db = CollectionCreate(
        orbit_id=orbit_id,
        **data.model_dump(),
    )
    mock_create.assert_awaited_once_with(expected_db)
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id,
        user_id,
        Resource.COLLECTION,
        Action.CREATE,
        orbit_id,
    )


@patch(
    "dataforce_studio.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.CollectionRepository.create_collection",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_collection_orbit_not_found(
    mock_create: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_permissions: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    data = CollectionCreateIn(
        description="d",
        name="n",
        collection_type=CollectionType.MODEL,
        tags=["t1"],
    )

    mock_get_orbit_simple.return_value = None

    with pytest.raises(NotFoundError, match="Orbit not found") as error:
        await handler.create_collection(user_id, organization_id, orbit_id, data)

    assert error.value.status_code == 404
    mock_create.assert_not_called()
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id,
        user_id,
        Resource.COLLECTION,
        Action.CREATE,
        orbit_id,
    )


@patch(
    "dataforce_studio.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.CollectionRepository.get_orbit_collections",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_orbit_collections_orbit_not_found(
    mock_get_collections: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_permissions: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_get_orbit_simple.return_value = None

    with pytest.raises(NotFoundError, match="Orbit not found") as error:
        await handler.get_orbit_collections(user_id, organization_id, orbit_id)

    assert error.value.status_code == 404
    mock_get_collections.assert_not_called()
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id,
        user_id,
        Resource.COLLECTION,
        Action.LIST,
        orbit_id,
    )


@patch(
    "dataforce_studio.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.CollectionRepository.get_orbit_collections",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_orbit_collections_orbit_wrong_org(
    mock_get_collections: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_permissions: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_get_orbit_simple.return_value = Mock(organization_id="ATHXk3sZjCWvrFYwGzb6ZY")

    with pytest.raises(NotFoundError, match="Orbit not found") as error:
        await handler.get_orbit_collections(user_id, organization_id, orbit_id)

    assert error.value.status_code == 404
    mock_get_collections.assert_not_called()
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id,
        user_id,
        Resource.COLLECTION,
        Action.LIST,
        orbit_id,
    )


@patch(
    "dataforce_studio.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.CollectionRepository.create_collection",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_collection_orbit_wrong_org(
    mock_create: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_permissions: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    data = CollectionCreateIn(
        description="d",
        name="n",
        collection_type=CollectionType.MODEL,
        tags=["t1"],
    )

    mock_get_orbit_simple.return_value = Mock(organization_id="ATHXk3sZjCWvrFYwGzb6ZY")

    with pytest.raises(NotFoundError, match="Orbit not found") as error:
        await handler.create_collection(user_id, organization_id, orbit_id, data)

    assert error.value.status_code == 404
    mock_create.assert_not_called()
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id,
        user_id,
        Resource.COLLECTION,
        Action.CREATE,
        orbit_id,
    )


@patch(
    "dataforce_studio.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.CollectionRepository.update_collection",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_collection(
    mock_update: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_permissions: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    data_in = CollectionUpdateIn(name="new")
    expected = Collection(
        id=collection_id,
        orbit_id=orbit_id,
        description="d",
        name="new",
        collection_type=CollectionType.MODEL,
        tags=None,
        total_models=0,
        created_at=datetime.now(),
        updated_at=None,
    )

    mock_update.return_value = expected
    mock_get_orbit_simple.return_value = Mock(organization_id=organization_id)

    result = await handler.update_collection(
        user_id, organization_id, orbit_id, collection_id, data_in
    )

    assert result == expected
    expected_update = CollectionUpdate(
        id=collection_id,
        description=data_in.description,
        name=data_in.name,
        tags=data_in.tags,
    )
    mock_update.assert_awaited_once_with(collection_id, expected_update)
    mock_check_permissions.assert_awaited_once_with(
        organization_id,
        user_id,
        Resource.COLLECTION,
        Action.UPDATE,
        orbit_id,
    )


@patch(
    "dataforce_studio.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.CollectionRepository.update_collection",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_collection_not_found(
    mock_update: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_permissions: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    data_in = CollectionUpdateIn(name="new")

    mock_update.return_value = None
    mock_get_orbit_simple.return_value = Mock(organization_id=organization_id)

    with pytest.raises(NotFoundError, match="Collection not found"):
        await handler.update_collection(
            user_id, organization_id, orbit_id, collection_id, data_in
        )

    expected_update = CollectionUpdate(
        id=collection_id,
        description=data_in.description,
        name=data_in.name,
        tags=data_in.tags,
    )
    mock_update.assert_awaited_once_with(collection_id, expected_update)
    mock_check_permissions.assert_awaited_once_with(
        organization_id,
        user_id,
        Resource.COLLECTION,
        Action.UPDATE,
        orbit_id,
    )


@patch(
    "dataforce_studio.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.CollectionRepository.update_collection",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_collection_orbit_wrong_org(
    mock_update: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_permissions: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    data_in = CollectionUpdateIn(name="new")

    mock_get_orbit_simple.return_value = Mock(organization_id="ATHXk3sZjCWvrFYwGzb6ZY")

    with pytest.raises(NotFoundError, match="Orbit not found") as error:
        await handler.update_collection(
            user_id, organization_id, orbit_id, collection_id, data_in
        )

    assert error.value.status_code == 404
    mock_update.assert_not_called()
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id,
        user_id,
        Resource.COLLECTION,
        Action.UPDATE,
        orbit_id,
    )


@patch(
    "dataforce_studio.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.ModelArtifactRepository.get_collection_model_artifacts_count",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.CollectionRepository.delete_collection",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_collection_empty(
    mock_delete: AsyncMock,
    mock_get_count: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_permissions: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    mock_get_collection.return_value = Collection(
        id=collection_id,
        orbit_id=orbit_id,
        description="d",
        name="n",
        collection_type=CollectionType.MODEL,
        tags=None,
        total_models=0,
        created_at=datetime.now(),
        updated_at=None,
    )

    mock_get_count.return_value = 0
    mock_get_orbit_simple.return_value = Mock(organization_id=organization_id)

    await handler.delete_collection(user_id, organization_id, orbit_id, collection_id)

    mock_delete.assert_awaited_once_with(collection_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id,
        user_id,
        Resource.COLLECTION,
        Action.DELETE,
        orbit_id,
    )


@patch(
    "dataforce_studio.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.ModelArtifactRepository.get_collection_model_artifacts_count",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.CollectionRepository.delete_collection",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_collection_not_empty(
    mock_delete: AsyncMock,
    mock_get_count: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_permissions: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    mock_get_collection.return_value = Collection(
        id=collection_id,
        orbit_id=orbit_id,
        description="d",
        name="n",
        collection_type=CollectionType.MODEL,
        tags=None,
        total_models=0,
        created_at=datetime.now(),
        updated_at=None,
    )

    mock_get_collection.return_value = Collection(
        id=collection_id,
        orbit_id=orbit_id,
        description="d",
        name="n",
        collection_type=CollectionType.MODEL,
        tags=None,
        total_models=0,
        created_at=datetime.now(),
        updated_at=None,
    )
    mock_get_count.return_value = 1
    mock_get_orbit_simple.return_value = Mock(organization_id=organization_id)

    with pytest.raises(CollectionDeleteError, match="cant be deleted"):
        await handler.delete_collection(
            user_id, organization_id, orbit_id, collection_id
        )

    mock_delete.assert_not_called()
    mock_check_permissions.assert_awaited_once_with(
        organization_id,
        user_id,
        Resource.COLLECTION,
        Action.DELETE,
        orbit_id,
    )


@patch(
    "dataforce_studio.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_collection_not_found(
    mock_get_collection: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_permissions: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    mock_get_collection.return_value = None
    mock_get_orbit_simple.return_value = Mock(organization_id=organization_id)

    with pytest.raises(NotFoundError, match="Collection not found"):
        await handler.delete_collection(
            user_id, organization_id, orbit_id, collection_id
        )

    mock_get_collection.assert_awaited_once_with(collection_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id,
        user_id,
        Resource.COLLECTION,
        Action.DELETE,
        orbit_id,
    )


@patch(
    "dataforce_studio.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.ModelArtifactRepository.get_collection_model_artifacts_count",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.CollectionRepository.delete_collection",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_collection_orbit_wrong_org(
    mock_delete: AsyncMock,
    mock_get_count: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_permissions: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    mock_get_collection.return_value = Collection(
        id=collection_id,
        orbit_id=orbit_id,
        description="d",
        name="n",
        collection_type=CollectionType.MODEL,
        tags=None,
        total_models=0,
        created_at=datetime.now(),
        updated_at=None,
    )
    mock_get_count.return_value = 0

    mock_get_orbit_simple.return_value = Mock(organization_id=uuid6.uuid7())

    with pytest.raises(NotFoundError, match="Orbit not found") as error:
        await handler.delete_collection(
            user_id, organization_id, orbit_id, collection_id
        )

    assert error.value.status_code == 404
    mock_delete.assert_not_called()
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id,
        user_id,
        Resource.COLLECTION,
        Action.DELETE,
        orbit_id,
    )


@patch(
    "dataforce_studio.handlers.collections.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.collections.CollectionRepository.get_orbit_collections",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_orbit_collections_success(
    mock_get_collections: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_permissions: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    expected_collections = [
        Collection(
            id=collection_id,
            orbit_id=orbit_id,
            description="Test collection 1",
            name="Collection 1",
            collection_type=CollectionType.MODEL,
            tags=None,
            total_models=5,
            created_at=datetime.now(),
            updated_at=None,
        )
    ]

    mock_get_orbit_simple.return_value = Mock(organization_id=organization_id)
    mock_get_collections.return_value = expected_collections

    result = await handler.get_orbit_collections(user_id, organization_id, orbit_id)

    assert result == expected_collections

    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_collections.assert_awaited_once_with(orbit_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id,
        user_id,
        Resource.COLLECTION,
        Action.LIST,
        orbit_id,
    )
