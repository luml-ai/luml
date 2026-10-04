from datetime import datetime
from unittest.mock import Mock

import pytest
from luml.handlers.collections import CollectionHandler
from luml.infra.exceptions import ApplicationError, NotFoundError
from luml.schemas.collections import (
    Collection,
    CollectionsList,
    CollectionSortBy,
    CollectionType,
)
from luml.schemas.general import Cursor, PaginationParams, SortOrder
from luml.schemas.permissions import Action, Resource

from tests.support.ids import (
    COLLECTION_ID,
    ORBIT_ID,
    ORGANIZATION_ID,
    OTHER_ORGANIZATION_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks


class TestCollectionListing:
    @pytest.mark.parametrize("cursor", ["garbage", "WzFd"])
    async def test_get_orbit_collections_raises_bad_request_when_cursor_is_invalid(
        self, mocks: CollaboratorMocks[CollectionHandler], cursor: str
    ) -> None:
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )

        with pytest.raises(ApplicationError, match="^Invalid cursor$") as error:
            await mocks.handler.get_orbit_collections(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, cursor_str=cursor
            )

        assert error.value.status_code == 400
        mocks.repository.get_orbit_collections.assert_not_called()

    async def test_get_orbit_collections_returns_first_page_when_cursor_is_empty(
        self, mocks: CollaboratorMocks[CollectionHandler]
    ) -> None:
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )
        mocks.repository.get_orbit_collections.return_value = ([], None)

        result = await mocks.handler.get_orbit_collections(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, cursor_str=""
        )

        assert result == CollectionsList(items=[], cursor=None)
        assert mocks.repository.get_orbit_collections.await_args is not None
        assert (
            mocks.repository.get_orbit_collections.await_args.kwargs[
                "pagination"
            ].cursor
            is None
        )

    async def test_get_orbit_collections_raises_not_found_when_orbit_is_missing(
        self, mocks: CollaboratorMocks[CollectionHandler]
    ) -> None:
        mocks.orbit_repository.get_orbit_simple.return_value = None

        with pytest.raises(NotFoundError, match="Orbit not found") as error:
            await mocks.handler.get_orbit_collections(
                USER_ID, ORGANIZATION_ID, ORBIT_ID
            )

        assert error.value.status_code == 404
        mocks.repository.get_orbit_collections.assert_not_called()
        mocks.orbit_repository.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.COLLECTION,
            Action.LIST,
            ORBIT_ID,
        )

    async def test_get_orbit_collections_raises_not_found_when_orbit_org_differs(
        self, mocks: CollaboratorMocks[CollectionHandler]
    ) -> None:
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=OTHER_ORGANIZATION_ID
        )

        with pytest.raises(NotFoundError, match="Orbit not found") as error:
            await mocks.handler.get_orbit_collections(
                USER_ID, ORGANIZATION_ID, ORBIT_ID
            )

        assert error.value.status_code == 404
        mocks.repository.get_orbit_collections.assert_not_called()
        mocks.orbit_repository.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.COLLECTION,
            Action.LIST,
            ORBIT_ID,
        )

    async def test_get_orbit_collections_returns_repository_page(
        self, mocks: CollaboratorMocks[CollectionHandler]
    ) -> None:
        expected_collections = [
            Collection(
                id=COLLECTION_ID,
                orbit_id=ORBIT_ID,
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

        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )
        mocks.repository.get_orbit_collections.return_value = (
            expected_collections,
            None,
        )

        result = await mocks.handler.get_orbit_collections(
            USER_ID, ORGANIZATION_ID, ORBIT_ID
        )

        assert result == expected

        mocks.orbit_repository.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.repository.get_orbit_collections.assert_awaited_once_with(
            orbit_id=ORBIT_ID,
            pagination=PaginationParams(
                cursor=None,
                sort_by="created_at",
                order=SortOrder.DESC,
                limit=100,
                scope_id=ORBIT_ID,
            ),
            search=None,
            types=None,
            tags=None,
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.COLLECTION,
            Action.LIST,
            ORBIT_ID,
        )

    async def test_get_orbit_collections_tags_returns_repository_tags(
        self, mocks: CollaboratorMocks[CollectionHandler]
    ) -> None:
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )
        mocks.repository.get_orbit_collections_tags.return_value = [
            "prod",
            "staging",
        ]

        result = await mocks.handler.get_orbit_collections_tags(
            USER_ID, ORGANIZATION_ID, ORBIT_ID
        )

        assert result == ["prod", "staging"]
        mocks.orbit_repository.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.repository.get_orbit_collections_tags.assert_awaited_once_with(ORBIT_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.COLLECTION,
            Action.LIST,
            ORBIT_ID,
        )

    async def test_get_orbit_collections_tags_raises_not_found_when_orbit_is_missing(
        self, mocks: CollaboratorMocks[CollectionHandler]
    ) -> None:
        mocks.orbit_repository.get_orbit_simple.return_value = None

        with pytest.raises(NotFoundError, match="Orbit not found"):
            await mocks.handler.get_orbit_collections_tags(
                USER_ID, ORGANIZATION_ID, ORBIT_ID
            )

        mocks.repository.get_orbit_collections_tags.assert_not_called()

    def test_validate_cursor_returns_cursor_when_sort_order_and_scope_match(
        self,
    ) -> None:
        cursor = Cursor(
            id=COLLECTION_ID,
            value=None,
            sort_by="created_at",
            order=SortOrder.DESC,
            scope_id=ORBIT_ID,
        )

        result = CollectionHandler._validate_cursor(
            cursor, CollectionSortBy.CREATED_AT, SortOrder.DESC, ORBIT_ID
        )

        assert result is cursor
