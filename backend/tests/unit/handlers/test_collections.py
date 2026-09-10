from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid7

import pytest
from luml.handlers.collections import CollectionHandler
from luml.infra.exceptions import CollectionDeleteError, NotFoundError
from luml.schemas.collections import (
    Collection,
    CollectionCreate,
    CollectionCreateIn,
    CollectionDetails,
    CollectionsList,
    CollectionSortBy,
    CollectionType,
    CollectionUpdate,
    CollectionUpdateIn,
)
from luml.schemas.general import Cursor, PaginationParams, SortOrder
from luml.schemas.permissions import Action, Resource
from pydantic import ValidationError

handler = CollectionHandler()


def test_collection_update_in_name_empty_string() -> None:
    with pytest.raises(ValidationError):
        CollectionUpdateIn(name="")


def test_collection_update_in_name_none_allowed() -> None:
    data = CollectionUpdateIn(name=None)
    assert data.name is None


def test_collection_update_in_name_valid() -> None:
    data = CollectionUpdateIn(name="valid name")
    assert data.name == "valid name"


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.create_collection",
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
        type=CollectionType.MODEL,
        tags=["t1"],
    )
    expected = Collection(
        id=collection_id,
        created_at=datetime.now(),
        orbit_id=orbit_id,
        total_artifacts=0,
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
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.create_collection",
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
        type=CollectionType.MODEL,
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
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.get_orbit_collections",
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
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.get_orbit_collections",
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
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.create_collection",
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
        type=CollectionType.MODEL,
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
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.update_collection",
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
        type=CollectionType.MODEL,
        tags=None,
        total_artifacts=0,
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
    mock_update.assert_awaited_once_with(collection_id, orbit_id, expected_update)
    mock_check_permissions.assert_awaited_once_with(
        organization_id,
        user_id,
        Resource.COLLECTION,
        Action.UPDATE,
        orbit_id,
    )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.update_collection",
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
    mock_update.assert_awaited_once_with(collection_id, orbit_id, expected_update)
    mock_check_permissions.assert_awaited_once_with(
        organization_id,
        user_id,
        Resource.COLLECTION,
        Action.UPDATE,
        orbit_id,
    )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.update_collection",
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
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.ArtifactRepository.get_collection_artifacts_count",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.delete_collection",
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
        type=CollectionType.MODEL,
        tags=None,
        total_artifacts=0,
        created_at=datetime.now(),
        updated_at=None,
    )

    mock_get_count.return_value = 0
    mock_get_orbit_simple.return_value = Mock(organization_id=organization_id)

    await handler.delete_collection(user_id, organization_id, orbit_id, collection_id)

    mock_delete.assert_awaited_once_with(collection_id, orbit_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id,
        user_id,
        Resource.COLLECTION,
        Action.DELETE,
        orbit_id,
    )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.delete_collection",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_collection_not_empty(
    mock_delete: AsyncMock,
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
        type=CollectionType.MODEL,
        tags=None,
        total_artifacts=0,
        created_at=datetime.now(),
        updated_at=None,
    )

    mock_get_collection.return_value = Collection(
        id=collection_id,
        orbit_id=orbit_id,
        description="d",
        name="n",
        type=CollectionType.MODEL,
        tags=None,
        total_artifacts=0,
        created_at=datetime.now(),
        updated_at=None,
    )
    mock_delete.side_effect = CollectionDeleteError(
        "Collection has artifacts and cant be deleted"
    )
    mock_get_orbit_simple.return_value = Mock(organization_id=organization_id)

    with pytest.raises(CollectionDeleteError, match="cant be deleted"):
        await handler.delete_collection(
            user_id, organization_id, orbit_id, collection_id
        )

    mock_delete.assert_awaited_once_with(collection_id, orbit_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id,
        user_id,
        Resource.COLLECTION,
        Action.DELETE,
        orbit_id,
    )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.get_collection",
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
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.ArtifactRepository.get_collection_artifacts_count",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.delete_collection",
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
        type=CollectionType.MODEL,
        tags=None,
        total_artifacts=0,
        created_at=datetime.now(),
        updated_at=None,
    )
    mock_get_count.return_value = 0

    mock_get_orbit_simple.return_value = Mock(organization_id=uuid7())

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
    "luml.handlers.collections.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.get_orbit_collections",
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
            type=CollectionType.MODEL,
            tags=None,
            total_artifacts=5,
            created_at=datetime.now(),
            updated_at=None,
        )
    ]
    expected = CollectionsList(
        items=expected_collections,
        cursor=None,
    )

    mock_get_orbit_simple.return_value = Mock(organization_id=organization_id)
    mock_get_collections.return_value = (expected_collections, None)

    result = await handler.get_orbit_collections(user_id, organization_id, orbit_id)

    assert result == expected

    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_collections.assert_awaited_once_with(
        orbit_id=orbit_id,
        pagination=PaginationParams(
            cursor=None,
            sort_by="created_at",
            order=SortOrder.DESC,
            limit=100,
            scope_id=orbit_id,
        ),
        search=None,
        types=None,
        tags=None,
    )
    mock_check_permissions.assert_awaited_once_with(
        organization_id,
        user_id,
        Resource.COLLECTION,
        Action.LIST,
        orbit_id,
    )


@patch(
    "luml.handlers.collections.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.get_orbit_collections_tags",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_orbit_collections_tags_success(
    mock_get_tags: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_permissions: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_get_orbit_simple.return_value = Mock(organization_id=organization_id)
    mock_get_tags.return_value = ["prod", "staging"]

    result = await handler.get_orbit_collections_tags(
        user_id, organization_id, orbit_id
    )

    assert result == ["prod", "staging"]
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_tags.assert_awaited_once_with(orbit_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id,
        user_id,
        Resource.COLLECTION,
        Action.LIST,
        orbit_id,
    )


@patch(
    "luml.handlers.collections.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.get_orbit_collections_tags",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_orbit_collections_tags_orbit_not_found(
    mock_get_tags: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_permissions: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_get_orbit_simple.return_value = None

    with pytest.raises(NotFoundError, match="Orbit not found"):
        await handler.get_orbit_collections_tags(user_id, organization_id, orbit_id)

    mock_get_tags.assert_not_called()


def test_validate_cursor_matching() -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    cursor = Cursor(
        id=collection_id,
        value=None,
        sort_by="created_at",
        order=SortOrder.DESC,
        scope_id=orbit_id,
    )

    result = CollectionHandler._validate_cursor(
        cursor, CollectionSortBy.CREATED_AT, SortOrder.DESC, orbit_id
    )

    assert result is cursor


@patch(
    "luml.handlers.collections.ArtifactRepository.get_collection_artifacts_tags",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.ArtifactRepository.get_collection_artifacts_extra_values",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_collection_details_success(
    mock_check_permissions: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_extra_values: AsyncMock,
    mock_get_tags: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    now = datetime.now()

    collection = Collection(
        id=collection_id,
        orbit_id=orbit_id,
        name="my-collection",
        description="desc",
        type=CollectionType.MODEL,
        tags=["t1"],
        total_artifacts=3,
        created_at=now,
        updated_at=None,
    )
    mock_get_collection.return_value = collection
    mock_get_extra_values.return_value = ["accuracy", "f1"]
    mock_get_tags.return_value = ["tag1"]

    result = await handler.get_collection_details(
        user_id, organization_id, orbit_id, collection_id
    )

    assert isinstance(result, CollectionDetails)
    assert result.artifacts_extra_values == ["accuracy", "f1"]
    assert result.artifacts_tags == ["tag1"]
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.COLLECTION, Action.READ, orbit_id
    )
    mock_get_collection.assert_awaited_once_with(collection_id)
    mock_get_extra_values.assert_awaited_once_with(collection_id)
    mock_get_tags.assert_awaited_once_with(collection_id)


@patch(
    "luml.handlers.collections.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_collection_details_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_collection: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    mock_get_collection.return_value = None

    with pytest.raises(NotFoundError, match="Collection not found"):
        await handler.get_collection_details(
            user_id, organization_id, orbit_id, collection_id
        )

    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.COLLECTION, Action.READ, orbit_id
    )
    mock_get_collection.assert_awaited_once_with(collection_id)


USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
OTHER_ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
OTHER_ORBIT_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")
OWNER_ORBIT_ID = UUID("0199c337-0aa1-7c33-8f6c-2c6d0a4e91be")
OWNER_COLLECTION_ID = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")


def _owner_collection() -> Collection:
    return Collection(
        id=OWNER_COLLECTION_ID,
        orbit_id=OWNER_ORBIT_ID,
        description="owner description",
        name="owner-collection",
        type=CollectionType.MODEL,
        tags=["owner"],
        total_artifacts=0,
        created_at=datetime(2026, 1, 1),
        updated_at=None,
    )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.update_collection",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_collection_from_foreign_orbit(
    mock_update: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_permissions: AsyncMock,
) -> None:
    stored = {OWNER_COLLECTION_ID: _owner_collection()}

    async def scoped_update(
        collection_id: UUID, orbit_id: UUID, update: CollectionUpdate
    ) -> Collection | None:
        collection = stored.get(collection_id)
        if not collection or collection.orbit_id != orbit_id:
            return None
        stored[collection_id] = collection.model_copy(
            update=update.model_dump(exclude_unset=True, exclude={"id"})
        )
        return stored[collection_id]

    mock_update.side_effect = scoped_update
    mock_get_orbit_simple.return_value = Mock(organization_id=OTHER_ORGANIZATION_ID)

    with pytest.raises(NotFoundError, match="Collection not found") as error:
        await handler.update_collection(
            USER_ID,
            OTHER_ORGANIZATION_ID,
            OTHER_ORBIT_ID,
            OWNER_COLLECTION_ID,
            CollectionUpdateIn(name="renamed"),
        )

    assert error.value.status_code == 404
    assert stored[OWNER_COLLECTION_ID] == _owner_collection()
    mock_update.assert_awaited_once_with(
        OWNER_COLLECTION_ID,
        OTHER_ORBIT_ID,
        CollectionUpdate(
            id=OWNER_COLLECTION_ID, description=None, name="renamed", tags=None
        ),
    )
    mock_check_permissions.assert_awaited_once_with(
        OTHER_ORGANIZATION_ID,
        USER_ID,
        Resource.COLLECTION,
        Action.UPDATE,
        OTHER_ORBIT_ID,
    )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.ArtifactRepository.get_collection_artifacts_count",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.collections.CollectionRepository.delete_collection",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_collection_from_foreign_orbit(
    mock_delete: AsyncMock,
    mock_get_count: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_permissions: AsyncMock,
) -> None:
    mock_get_collection.return_value = _owner_collection()
    mock_get_orbit_simple.return_value = Mock(organization_id=OTHER_ORGANIZATION_ID)
    # A non-zero count would surface as CollectionDeleteError if the orbit check ran
    # after it, confirming to the caller that the foreign collection exists.
    mock_get_count.return_value = 5

    with pytest.raises(NotFoundError, match="Collection not found") as error:
        await handler.delete_collection(
            USER_ID, OTHER_ORGANIZATION_ID, OTHER_ORBIT_ID, OWNER_COLLECTION_ID
        )

    assert error.value.status_code == 404
    mock_get_count.assert_not_awaited()
    mock_delete.assert_not_awaited()
    mock_check_permissions.assert_awaited_once_with(
        OTHER_ORGANIZATION_ID,
        USER_ID,
        Resource.COLLECTION,
        Action.DELETE,
        OTHER_ORBIT_ID,
    )
