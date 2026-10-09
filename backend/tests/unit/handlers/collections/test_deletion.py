from datetime import datetime
from unittest.mock import Mock

import pytest
from luml.handlers.collections import CollectionHandler
from luml.infra.exceptions import CollectionDeleteError, NotFoundError
from luml.schemas.collections import Collection, CollectionType
from luml.schemas.permissions import Action, Resource

from tests.support.ids import (
    COLLECTION_ID,
    ORBIT_ID,
    ORGANIZATION_ID,
    OTHER_ORGANIZATION_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.collections.conftest import _foreign_collection


class TestCollectionDeletion:
    async def test_delete_collection_deletes_empty_collection(
        self, mocks: CollaboratorMocks[CollectionHandler]
    ) -> None:
        mocks.repository.get_collection.return_value = Collection(
            id=COLLECTION_ID,
            orbit_id=ORBIT_ID,
            description="d",
            name="n",
            type=CollectionType.MODEL,
            tags=None,
            total_artifacts=0,
            created_at=datetime.now(),
            updated_at=None,
        )
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )

        await mocks.handler.delete_collection(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID
        )

        mocks.repository.delete_collection.assert_awaited_once_with(
            COLLECTION_ID, ORBIT_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.COLLECTION,
            Action.DELETE,
            ORBIT_ID,
        )

    async def test_delete_collection_raises_delete_error_when_collection_has_artifacts(
        self, mocks: CollaboratorMocks[CollectionHandler]
    ) -> None:
        mocks.repository.get_collection.return_value = Collection(
            id=COLLECTION_ID,
            orbit_id=ORBIT_ID,
            description="d",
            name="n",
            type=CollectionType.MODEL,
            tags=None,
            total_artifacts=0,
            created_at=datetime.now(),
            updated_at=None,
        )
        mocks.repository.delete_collection.side_effect = CollectionDeleteError(
            "Collection has artifacts and cant be deleted"
        )
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )

        with pytest.raises(CollectionDeleteError, match="cant be deleted"):
            await mocks.handler.delete_collection(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID
            )

        mocks.repository.delete_collection.assert_awaited_once_with(
            COLLECTION_ID, ORBIT_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.COLLECTION,
            Action.DELETE,
            ORBIT_ID,
        )

    async def test_delete_collection_raises_not_found_when_collection_is_missing(
        self, mocks: CollaboratorMocks[CollectionHandler]
    ) -> None:
        mocks.repository.get_collection.return_value = None
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )

        with pytest.raises(NotFoundError, match="Collection not found"):
            await mocks.handler.delete_collection(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID
            )

        mocks.repository.get_collection.assert_awaited_once_with(COLLECTION_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.COLLECTION,
            Action.DELETE,
            ORBIT_ID,
        )

    async def test_delete_collection_raises_not_found_when_orbit_org_differs(
        self, mocks: CollaboratorMocks[CollectionHandler]
    ) -> None:
        mocks.repository.get_collection.return_value = Collection(
            id=COLLECTION_ID,
            orbit_id=ORBIT_ID,
            description="d",
            name="n",
            type=CollectionType.MODEL,
            tags=None,
            total_artifacts=0,
            created_at=datetime.now(),
            updated_at=None,
        )
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=OTHER_ORGANIZATION_ID
        )

        with pytest.raises(NotFoundError, match="Orbit not found") as error:
            await mocks.handler.delete_collection(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID
            )

        assert error.value.status_code == 404
        mocks.repository.delete_collection.assert_not_called()
        mocks.orbit_repository.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.COLLECTION,
            Action.DELETE,
            ORBIT_ID,
        )

    async def test_delete_collection_raises_not_found_before_counting_foreign_artifacts(
        self, mocks: CollaboratorMocks[CollectionHandler]
    ) -> None:
        mocks.repository.get_collection.return_value = _foreign_collection()
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )
        mocks.artifacts_repository.get_collection_artifacts_count.return_value = 5

        with pytest.raises(NotFoundError, match="Collection not found") as error:
            await mocks.handler.delete_collection(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID
            )

        assert error.value.status_code == 404
        mocks.artifacts_repository.get_collection_artifacts_count.assert_not_awaited()
        mocks.repository.delete_collection.assert_not_awaited()
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.COLLECTION,
            Action.DELETE,
            ORBIT_ID,
        )
