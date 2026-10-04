from datetime import datetime
from unittest.mock import Mock
from uuid import UUID

import pytest
from luml.handlers.collections import CollectionHandler
from luml.infra.exceptions import NotFoundError
from luml.schemas.collections import (
    Collection,
    CollectionCreate,
    CollectionCreateIn,
    CollectionDetails,
    CollectionType,
    CollectionUpdate,
    CollectionUpdateIn,
)
from luml.schemas.permissions import Action, Resource
from pydantic import ValidationError

from tests.support.ids import (
    COLLECTION_ID,
    ORBIT_ID,
    ORGANIZATION_ID,
    OTHER_ORGANIZATION_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.collections.conftest import _foreign_collection


class TestCollectionCrud:
    def test_collection_update_in_rejects_empty_name(self) -> None:
        with pytest.raises(ValidationError):
            CollectionUpdateIn(name="")

    def test_collection_update_in_accepts_none_name(self) -> None:
        data = CollectionUpdateIn(name=None)
        assert data.name is None

    def test_collection_update_in_accepts_valid_name(self) -> None:
        data = CollectionUpdateIn(name="valid name")
        assert data.name == "valid name"

    async def test_create_collection_returns_created_collection(
        self, mocks: CollaboratorMocks[CollectionHandler]
    ) -> None:
        data = CollectionCreateIn(
            description="d",
            name="n",
            type=CollectionType.MODEL,
            tags=["t1"],
        )
        expected = Collection(
            id=COLLECTION_ID,
            created_at=datetime.now(),
            orbit_id=ORBIT_ID,
            total_artifacts=0,
            **data.model_dump(),
        )

        mocks.repository.create_collection.return_value = expected
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )

        result = await mocks.handler.create_collection(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, data
        )

        assert result == expected
        expected_db = CollectionCreate(
            orbit_id=ORBIT_ID,
            **data.model_dump(),
        )
        mocks.repository.create_collection.assert_awaited_once_with(expected_db)
        mocks.orbit_repository.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.COLLECTION,
            Action.CREATE,
            ORBIT_ID,
        )

    async def test_create_collection_raises_not_found_when_orbit_is_missing(
        self, mocks: CollaboratorMocks[CollectionHandler]
    ) -> None:
        data = CollectionCreateIn(
            description="d",
            name="n",
            type=CollectionType.MODEL,
            tags=["t1"],
        )

        mocks.orbit_repository.get_orbit_simple.return_value = None

        with pytest.raises(NotFoundError, match="Orbit not found") as error:
            await mocks.handler.create_collection(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, data
            )

        assert error.value.status_code == 404
        mocks.repository.create_collection.assert_not_called()
        mocks.orbit_repository.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.COLLECTION,
            Action.CREATE,
            ORBIT_ID,
        )

    async def test_create_collection_raises_not_found_when_orbit_org_differs(
        self, mocks: CollaboratorMocks[CollectionHandler]
    ) -> None:
        data = CollectionCreateIn(
            description="d",
            name="n",
            type=CollectionType.MODEL,
            tags=["t1"],
        )

        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=OTHER_ORGANIZATION_ID
        )

        with pytest.raises(NotFoundError, match="Orbit not found") as error:
            await mocks.handler.create_collection(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, data
            )

        assert error.value.status_code == 404
        mocks.repository.create_collection.assert_not_called()
        mocks.orbit_repository.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.COLLECTION,
            Action.CREATE,
            ORBIT_ID,
        )

    async def test_update_collection_returns_updated_collection(
        self, mocks: CollaboratorMocks[CollectionHandler]
    ) -> None:
        data_in = CollectionUpdateIn(name="new")
        expected = Collection(
            id=COLLECTION_ID,
            orbit_id=ORBIT_ID,
            description="d",
            name="new",
            type=CollectionType.MODEL,
            tags=None,
            total_artifacts=0,
            created_at=datetime.now(),
            updated_at=None,
        )

        mocks.repository.update_collection.return_value = expected
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )

        result = await mocks.handler.update_collection(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, data_in
        )

        assert result == expected
        expected_update = CollectionUpdate(
            id=COLLECTION_ID,
            description=data_in.description,
            name=data_in.name,
            tags=data_in.tags,
        )
        mocks.repository.update_collection.assert_awaited_once_with(
            COLLECTION_ID, ORBIT_ID, expected_update
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.COLLECTION,
            Action.UPDATE,
            ORBIT_ID,
        )

    async def test_update_collection_raises_not_found_when_collection_is_missing(
        self, mocks: CollaboratorMocks[CollectionHandler]
    ) -> None:
        data_in = CollectionUpdateIn(name="new")

        mocks.repository.update_collection.return_value = None
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )

        with pytest.raises(NotFoundError, match="Collection not found"):
            await mocks.handler.update_collection(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, data_in
            )

        expected_update = CollectionUpdate(
            id=COLLECTION_ID,
            description=data_in.description,
            name=data_in.name,
            tags=data_in.tags,
        )
        mocks.repository.update_collection.assert_awaited_once_with(
            COLLECTION_ID, ORBIT_ID, expected_update
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.COLLECTION,
            Action.UPDATE,
            ORBIT_ID,
        )

    async def test_update_collection_raises_not_found_when_orbit_org_differs(
        self, mocks: CollaboratorMocks[CollectionHandler]
    ) -> None:
        data_in = CollectionUpdateIn(name="new")

        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=OTHER_ORGANIZATION_ID
        )

        with pytest.raises(NotFoundError, match="Orbit not found") as error:
            await mocks.handler.update_collection(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, data_in
            )

        assert error.value.status_code == 404
        mocks.repository.update_collection.assert_not_called()
        mocks.orbit_repository.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.COLLECTION,
            Action.UPDATE,
            ORBIT_ID,
        )

    async def test_update_collection_raises_not_found_when_collection_in_foreign_orbit(
        self, mocks: CollaboratorMocks[CollectionHandler]
    ) -> None:
        stored = {COLLECTION_ID: _foreign_collection()}

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

        mocks.repository.update_collection.side_effect = scoped_update
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )

        with pytest.raises(NotFoundError, match="Collection not found") as error:
            await mocks.handler.update_collection(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                COLLECTION_ID,
                CollectionUpdateIn(name="renamed"),
            )

        assert error.value.status_code == 404
        assert stored[COLLECTION_ID] == _foreign_collection()
        mocks.repository.update_collection.assert_awaited_once_with(
            COLLECTION_ID,
            ORBIT_ID,
            CollectionUpdate(
                id=COLLECTION_ID, description=None, name="renamed", tags=None
            ),
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.COLLECTION,
            Action.UPDATE,
            ORBIT_ID,
        )

    async def test_get_collection_details_returns_artifacts_extra_values_and_tags(
        self, mocks: CollaboratorMocks[CollectionHandler]
    ) -> None:
        collection = Collection(
            id=COLLECTION_ID,
            orbit_id=ORBIT_ID,
            name="my-collection",
            description="desc",
            type=CollectionType.MODEL,
            tags=["t1"],
            total_artifacts=3,
            created_at=datetime.now(),
            updated_at=None,
        )
        get_extra_values = (
            mocks.artifacts_repository.get_collection_artifacts_extra_values
        )
        get_tags = mocks.artifacts_repository.get_collection_artifacts_tags
        mocks.repository.get_collection.return_value = collection
        get_extra_values.return_value = ["accuracy", "f1"]
        get_tags.return_value = ["tag1"]

        result = await mocks.handler.get_collection_details(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID
        )

        assert isinstance(result, CollectionDetails)
        assert result.artifacts_extra_values == ["accuracy", "f1"]
        assert result.artifacts_tags == ["tag1"]
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.COLLECTION, Action.READ, ORBIT_ID
        )
        mocks.repository.get_collection.assert_awaited_once_with(COLLECTION_ID)
        get_extra_values.assert_awaited_once_with(COLLECTION_ID)
        get_tags.assert_awaited_once_with(COLLECTION_ID)

    async def test_get_collection_details_raises_not_found_when_collection_is_missing(
        self, mocks: CollaboratorMocks[CollectionHandler]
    ) -> None:
        mocks.repository.get_collection.return_value = None

        with pytest.raises(NotFoundError, match="Collection not found"):
            await mocks.handler.get_collection_details(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID
            )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.COLLECTION, Action.READ, ORBIT_ID
        )
        mocks.repository.get_collection.assert_awaited_once_with(COLLECTION_ID)
