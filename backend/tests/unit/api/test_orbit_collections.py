from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from luml.infra.exceptions import ApplicationError
from luml.schemas.collections import (
    CollectionsList,
    CollectionSortBy,
    CollectionTypeFilter,
)
from luml.schemas.general import SortOrder

from tests.support.ids import ORBIT_ID, ORGANIZATION_ID, USER_ID

COLLECTIONS_PATH = f"/v1/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}/collections"


class TestOrbitCollections:
    @patch(
        "luml.handlers.collections.CollectionHandler.get_orbit_collections",
        new_callable=AsyncMock,
    )
    def test_get_orbit_collections_repeated_tags_and_types(
        self, mock_get_collections: AsyncMock, client: TestClient
    ) -> None:
        mock_get_collections.return_value = CollectionsList(items=[], cursor=None)

        response = client.get(
            COLLECTIONS_PATH,
            params=[("tags", "production"), ("tags", "ml"), ("types", "model")],
        )

        assert response.status_code == 200
        assert response.json() == {"items": [], "cursor": None}
        mock_get_collections.assert_awaited_once_with(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            None,
            50,
            CollectionSortBy.CREATED_AT,
            SortOrder.DESC,
            None,
            [CollectionTypeFilter.MODEL],
            ["production", "ml"],
        )

    @patch(
        "luml.handlers.collections.CollectionHandler.get_orbit_collections_tags",
        new_callable=AsyncMock,
    )
    def test_get_orbit_collections_tags(
        self, mock_get_tags: AsyncMock, client: TestClient
    ) -> None:
        mock_get_tags.return_value = ["ml", "production", "staging"]

        response = client.get(f"{COLLECTIONS_PATH}/tags")

        assert response.status_code == 200
        assert response.json() == ["ml", "production", "staging"]
        mock_get_tags.assert_awaited_once_with(USER_ID, ORGANIZATION_ID, ORBIT_ID)

    @patch(
        "luml.handlers.collections.CollectionHandler.get_orbit_collections",
        new_callable=AsyncMock,
    )
    def test_list_forwards_cursor_and_maps_invalid_cursor_to_400(
        self, mock_get_collections: AsyncMock, client: TestClient
    ) -> None:
        mock_get_collections.side_effect = ApplicationError("Invalid cursor")

        response = client.get(COLLECTIONS_PATH, params={"cursor": "garbage"})

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid cursor"}
        mock_get_collections.assert_awaited_once_with(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            "garbage",
            50,
            CollectionSortBy.CREATED_AT,
            SortOrder.DESC,
            None,
            None,
            None,
        )
