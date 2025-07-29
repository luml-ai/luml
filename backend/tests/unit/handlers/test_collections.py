import random
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from dataforce_studio.handlers.collections import CollectionHandler
from dataforce_studio.infra.exceptions import CollectionDeleteError, NotFoundError
from dataforce_studio.schemas.ml_models import (
    Collection,
    CollectionCreate,
    CollectionCreateIn,
    CollectionType,
    CollectionUpdate,
    CollectionUpdateIn,
)
from dataforce_studio.schemas.orbit import OrbitRole
from dataforce_studio.schemas.organization import OrgRole

handler = CollectionHandler()


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
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
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    data = CollectionCreateIn(
        description="d",
        name="n",
        collection_type=CollectionType.MODEL,
        tags=["t1"],
    )
    expected = Collection(
        id=1,
        created_at=datetime.now(),
        orbit_id=orbit_id,
        total_models=0,
        **data.model_dump(),
    )

    class Orbit:
        def __init__(self, organization_id: int) -> None:
            self.organization_id = organization_id

    mock_create.return_value = expected
    mock_get_orbit_simple.return_value = Orbit(organization_id)
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

    result = await handler.create_collection(user_id, organization_id, orbit_id, data)

    assert result == expected
    expected_db = CollectionCreate(
        orbit_id=orbit_id,
        **data.model_dump(),
    )
    mock_create.assert_awaited_once_with(expected_db)
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
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
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    data = CollectionCreateIn(
        description="d",
        name="n",
        collection_type=CollectionType.MODEL,
        tags=["t1"],
    )

    mock_get_orbit_simple.return_value = None
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

    with pytest.raises(NotFoundError, match="Orbit not found") as error:
        await handler.create_collection(user_id, organization_id, orbit_id, data)

    assert error.value.status_code == 404
    mock_create.assert_not_called()
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
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
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)

    mock_get_orbit_simple.return_value = None
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

    with pytest.raises(NotFoundError, match="Orbit not found") as error:
        await handler.get_orbit_collections(user_id, organization_id, orbit_id)

    assert error.value.status_code == 404
    mock_get_collections.assert_not_called()
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
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
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)

    class Orbit:
        def __init__(self, organization_id: int) -> None:
            self.organization_id = organization_id

    mock_get_orbit_simple.return_value = Orbit(organization_id + 1)
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

    with pytest.raises(NotFoundError, match="Orbit not found") as error:
        await handler.get_orbit_collections(user_id, organization_id, orbit_id)

    assert error.value.status_code == 404
    mock_get_collections.assert_not_called()
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
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
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    data = CollectionCreateIn(
        description="d",
        name="n",
        collection_type=CollectionType.MODEL,
        tags=["t1"],
    )

    class Orbit:
        def __init__(self, organization_id: int) -> None:
            self.organization_id = organization_id

    mock_get_orbit_simple.return_value = Orbit(organization_id + 1)
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

    with pytest.raises(NotFoundError, match="Orbit not found") as error:
        await handler.create_collection(user_id, organization_id, orbit_id, data)

    assert error.value.status_code == 404
    mock_create.assert_not_called()
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
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
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

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

    class Orbit:
        def __init__(self, organization_id: int) -> None:
            self.organization_id = organization_id

    mock_update.return_value = expected
    mock_get_orbit_simple.return_value = Orbit(organization_id)
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

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


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
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
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

    data_in = CollectionUpdateIn(name="new")

    class Orbit:
        def __init__(self, organization_id: int) -> None:
            self.organization_id = organization_id

    mock_update.return_value = None
    mock_get_orbit_simple.return_value = Orbit(organization_id)
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

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


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
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
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

    data_in = CollectionUpdateIn(name="new")

    class Orbit:
        def __init__(self, organization_id: int) -> None:
            self.organization_id = organization_id

    mock_get_orbit_simple.return_value = Orbit(organization_id + 1)
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

    with pytest.raises(NotFoundError, match="Orbit not found") as error:
        await handler.update_collection(
            user_id, organization_id, orbit_id, collection_id, data_in
        )

    assert error.value.status_code == 404
    mock_update.assert_not_called()
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
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
    "dataforce_studio.handlers.collections.MLModelRepository.get_collection_models_count",
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
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

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

    class Orbit:
        def __init__(self, organization_id: int) -> None:
            self.organization_id = organization_id

    mock_get_count.return_value = 0
    mock_get_orbit_simple.return_value = Orbit(organization_id)
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

    await handler.delete_collection(user_id, organization_id, orbit_id, collection_id)

    mock_delete.assert_awaited_once_with(collection_id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
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
    "dataforce_studio.handlers.collections.MLModelRepository.get_collection_models_count",
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
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

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

    class Orbit:
        def __init__(self, organization_id: int) -> None:
            self.organization_id = organization_id

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
    mock_get_orbit_simple.return_value = Orbit(organization_id)
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

    with pytest.raises(CollectionDeleteError, match="cant be deleted"):
        await handler.delete_collection(
            user_id, organization_id, orbit_id, collection_id
        )

    mock_delete.assert_not_called()


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
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
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

    class Orbit:
        def __init__(self, organization_id: int) -> None:
            self.organization_id = organization_id

    mock_get_collection.return_value = None
    mock_get_orbit_simple.return_value = Orbit(organization_id)
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

    with pytest.raises(NotFoundError, match="Collection not found"):
        await handler.delete_collection(
            user_id, organization_id, orbit_id, collection_id
        )

    mock_get_collection.assert_awaited_once_with(collection_id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.OrbitRepository.get_orbit_member_role",
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
    "dataforce_studio.handlers.collections.MLModelRepository.get_collection_models_count",
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
    mock_get_orbit_role: AsyncMock,
    mock_get_org_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    collection_id = random.randint(1, 10000)

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

    class Orbit:
        def __init__(self, organization_id: int) -> None:
            self.organization_id = organization_id

    mock_get_orbit_simple.return_value = Orbit(organization_id + 1)
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_orbit_role.return_value = OrbitRole.MEMBER

    with pytest.raises(NotFoundError, match="Orbit not found") as error:
        await handler.delete_collection(
            user_id, organization_id, orbit_id, collection_id
        )

    assert error.value.status_code == 404
    mock_delete.assert_not_called()
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
