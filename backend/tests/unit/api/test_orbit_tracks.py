from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from luml.schemas.general import SortOrder
from luml.schemas.tracks import TracksList, TrackSortBy

from tests.support.ids import ORBIT_ID, ORGANIZATION_ID, USER_ID

TRACKS_PATH = f"/v1/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}/tracks"


class TestOrbitTracks:
    @patch(
        "luml.handlers.tracks.TracksHandler.list_tracks",
        new_callable=AsyncMock,
    )
    def test_list_tracks_repeated_tags_and_types(
        self, mock_list_tracks: AsyncMock, client: TestClient
    ) -> None:
        mock_list_tracks.return_value = TracksList(items=[], cursor=None)

        response = client.get(
            TRACKS_PATH,
            params=[("tags", "production"), ("tags", "ml"), ("types", "model")],
        )

        assert response.status_code == 200
        assert response.json() == {"items": [], "cursor": None}
        mock_list_tracks.assert_awaited_once_with(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            None,
            50,
            TrackSortBy.CREATED_AT,
            SortOrder.DESC,
            None,
            ["model"],
            ["production", "ml"],
        )

    @patch(
        "luml.handlers.tracks.TracksHandler.list_tracks_tags",
        new_callable=AsyncMock,
    )
    def test_list_tracks_tags(
        self, mock_list_tags: AsyncMock, client: TestClient
    ) -> None:
        mock_list_tags.return_value = ["ml", "production", "staging"]

        response = client.get(f"{TRACKS_PATH}/tags")

        assert response.status_code == 200
        assert response.json() == ["ml", "production", "staging"]
        mock_list_tags.assert_awaited_once_with(USER_ID, ORGANIZATION_ID, ORBIT_ID)
