from datetime import datetime
from unittest.mock import Mock

import pytest
from luml.handlers.tracks import TracksHandler
from luml.infra.exceptions import ApplicationError, NotFoundError
from luml.schemas.artifacts import ArtifactType
from luml.schemas.general import Cursor, SortOrder
from luml.schemas.permissions import Action, Resource
from luml.schemas.tracks import (
    StageUpsertIn,
    TrackCreateIn,
    TracksList,
    TrackSortBy,
    TrackUpdateIn,
)
from luml.utils.pagination import encode_cursor
from sqlalchemy.exc import IntegrityError

from tests.support.ids import (
    ORBIT_ID,
    ORGANIZATION_ID,
    OTHER_ORBIT_ID,
    STAGE_ID,
    TRACK_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.tracks.conftest import _make_track


class TestTracks:
    async def test_create_track_passes_requested_stages_to_repository(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        data = TrackCreateIn(
            name="churn-model",
            artifact_type=ArtifactType.MODEL,
            stages=["Staging", "Prod"],
        )
        expected = _make_track()
        mocks.track_repository.create_track.return_value = expected
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )

        result = await mocks.handler.create_track(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, data
        )

        assert result == expected
        mocks.track_repository.create_track.assert_awaited_once()
        create_call = mocks.track_repository.create_track.await_args
        assert create_call is not None
        assert create_call.kwargs["stage_names"] == ["Staging", "Prod"]
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.TRACK, Action.CREATE, ORBIT_ID
        )

    async def test_create_track_passes_no_stages_when_none_requested(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        data = TrackCreateIn(name="churn-model", artifact_type=ArtifactType.MODEL)
        mocks.track_repository.create_track.return_value = _make_track()
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )

        await mocks.handler.create_track(USER_ID, ORGANIZATION_ID, ORBIT_ID, data)

        create_call = mocks.track_repository.create_track.await_args
        assert create_call is not None
        assert create_call.kwargs["stage_names"] == []

    async def test_create_track_propagates_integrity_error_other_than_duplicate_name(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        data = TrackCreateIn(name="churn-model", artifact_type=ArtifactType.MODEL)
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )
        mocks.track_repository.create_track.side_effect = IntegrityError(
            "", {}, Exception('null value in column "created_by"')
        )

        with pytest.raises(IntegrityError):
            await mocks.handler.create_track(USER_ID, ORGANIZATION_ID, ORBIT_ID, data)

    async def test_create_track_raises_conflict_when_stage_names_repeat(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        data = TrackCreateIn(
            name="churn-model", artifact_type=ArtifactType.MODEL, stages=["Dup", "Dup"]
        )
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )
        mocks.track_repository.create_track.side_effect = IntegrityError(
            "", {}, Exception("uq_track_stages_track_id_name")
        )

        with pytest.raises(ApplicationError, match="Duplicate stage names") as exc:
            await mocks.handler.create_track(USER_ID, ORGANIZATION_ID, ORBIT_ID, data)
        assert exc.value.status_code == 409

    async def test_create_track_raises_not_found_when_orbit_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.orbit_repository.get_orbit_simple.return_value = None
        data = TrackCreateIn(name="churn-model", artifact_type=ArtifactType.MODEL)

        with pytest.raises(NotFoundError, match="Orbit not found"):
            await mocks.handler.create_track(USER_ID, ORGANIZATION_ID, ORBIT_ID, data)

    async def test_get_track_returns_track(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        expected = _make_track()
        mocks.track_repository.get_track.return_value = expected

        result = await mocks.handler.get_track(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID
        )

        assert result == expected
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.TRACK, Action.READ, ORBIT_ID
        )

    async def test_get_track_raises_not_found_when_track_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = None
        with pytest.raises(NotFoundError, match="Track not found"):
            await mocks.handler.get_track(USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID)

    async def test_get_track_raises_not_found_when_track_belongs_to_other_orbit(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track(
            orbit_id=OTHER_ORBIT_ID
        )
        with pytest.raises(NotFoundError, match="Track not found"):
            await mocks.handler.get_track(USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID)

    async def test_list_tracks_returns_orbit_tracks(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        track = _make_track()
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )
        mocks.track_repository.get_orbit_tracks.return_value = ([track], None)

        result = await mocks.handler.list_tracks(USER_ID, ORGANIZATION_ID, ORBIT_ID)

        assert result == TracksList(items=[track], cursor=None)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.TRACK, Action.LIST, ORBIT_ID
        )

    async def test_list_tracks_raises_not_found_when_orbit_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.orbit_repository.get_orbit_simple.return_value = None
        with pytest.raises(NotFoundError, match="Orbit not found"):
            await mocks.handler.list_tracks(USER_ID, ORGANIZATION_ID, ORBIT_ID)

    async def test_list_tracks_passes_cursor_when_cursor_is_valid(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )
        mocks.track_repository.get_orbit_tracks.return_value = ([], None)
        cursor_str = encode_cursor(
            Cursor(
                id=TRACK_ID,
                value=datetime.now(),
                sort_by=TrackSortBy.CREATED_AT.value,
                order=SortOrder.DESC,
                scope_id=ORBIT_ID,
            )
        )

        await mocks.handler.list_tracks(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, cursor_str=cursor_str
        )

        list_call = mocks.track_repository.get_orbit_tracks.await_args
        assert list_call is not None
        pagination = list_call.kwargs["pagination"]
        assert pagination.cursor is not None

    def test_validate_cursor_returns_cursor_when_it_matches(self) -> None:
        cursor = Cursor(
            id=TRACK_ID,
            value="x",
            sort_by=TrackSortBy.CREATED_AT.value,
            order=SortOrder.DESC,
            scope_id=ORBIT_ID,
        )
        result = TracksHandler._validate_cursor(
            cursor, TrackSortBy.CREATED_AT, SortOrder.DESC, ORBIT_ID
        )
        assert result is cursor

    def test_validate_cursor_returns_none_when_sort_differs(self) -> None:
        cursor = Cursor(
            id=TRACK_ID,
            value="x",
            sort_by=TrackSortBy.NAME.value,
            order=SortOrder.DESC,
            scope_id=ORBIT_ID,
        )
        result = TracksHandler._validate_cursor(
            cursor, TrackSortBy.CREATED_AT, SortOrder.DESC, ORBIT_ID
        )
        assert result is None

    async def test_list_tracks_tags_returns_orbit_tags(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )
        mocks.track_repository.get_orbit_tracks_tags.return_value = ["prod", "staging"]

        result = await mocks.handler.list_tracks_tags(
            USER_ID, ORGANIZATION_ID, ORBIT_ID
        )

        assert result == ["prod", "staging"]
        mocks.track_repository.get_orbit_tracks_tags.assert_awaited_once_with(ORBIT_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.TRACK, Action.LIST, ORBIT_ID
        )

    async def test_list_tracks_tags_raises_not_found_when_orbit_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.orbit_repository.get_orbit_simple.return_value = None

        with pytest.raises(NotFoundError, match="Orbit not found"):
            await mocks.handler.list_tracks_tags(USER_ID, ORGANIZATION_ID, ORBIT_ID)

        mocks.track_repository.get_orbit_tracks_tags.assert_not_called()

    async def test_update_track_returns_updated_track(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        data_in = TrackUpdateIn(name="new-name")
        expected = _make_track(name="new-name")
        mocks.track_repository.update_track.return_value = expected
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )

        result = await mocks.handler.update_track(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, data_in
        )

        assert result == expected
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.TRACK, Action.UPDATE, ORBIT_ID
        )

    async def test_update_track_passes_only_set_fields_when_update_is_partial(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        data_in = TrackUpdateIn(name="new-name")
        mocks.track_repository.update_track.return_value = _make_track(name="new-name")
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )

        await mocks.handler.update_track(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, data_in
        )

        update_call = mocks.track_repository.update_track.await_args
        assert update_call is not None
        passed_update = update_call.args[1]
        dumped = passed_update.model_dump(exclude_unset=True, exclude={"id"})
        assert dumped == {"name": "new-name"}
        assert "description" not in dumped
        assert "tags" not in dumped

    async def test_update_track_raises_not_found_when_track_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.update_track.return_value = None
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )

        with pytest.raises(NotFoundError, match="Track not found"):
            await mocks.handler.update_track(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, TrackUpdateIn(name="new")
            )

    async def test_update_track_raises_not_found_when_orbit_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.orbit_repository.get_orbit_simple.return_value = None
        with pytest.raises(NotFoundError, match="Orbit not found"):
            await mocks.handler.update_track(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, TrackUpdateIn(name="x")
            )

    async def test_update_track_raises_conflict_when_stage_names_repeat(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )
        mocks.track_repository.update_track.side_effect = IntegrityError(
            "", {}, Exception("uq_track_stages_track_id_name")
        )
        with pytest.raises(ApplicationError, match="Duplicate stage names") as exc:
            await mocks.handler.update_track(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                TrackUpdateIn(name="t", stages=[StageUpsertIn(name="dup")]),
            )
        assert exc.value.status_code == 409

    async def test_update_track_propagates_integrity_error_other_than_duplicate_name(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )
        mocks.track_repository.update_track.side_effect = IntegrityError(
            "", {}, Exception("some other constraint")
        )
        with pytest.raises(IntegrityError):
            await mocks.handler.update_track(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, TrackUpdateIn(name="x")
            )

    async def test_update_track_syncs_stages_in_the_same_call_without_refetch(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )
        mocks.track_repository.update_track.return_value = _make_track()

        desired = [
            StageUpsertIn(id=STAGE_ID, name="Renamed"),
            StageUpsertIn(name="Brand New"),
        ]
        data = TrackUpdateIn(name="t", stages=desired)

        await mocks.handler.update_track(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, data
        )

        update_call = mocks.track_repository.update_track.await_args
        assert update_call is not None
        assert update_call.kwargs["stages"] == desired
        mocks.track_repository.get_track.assert_not_awaited()

    async def test_update_track_skips_stage_sync_when_stages_are_omitted(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )
        mocks.track_repository.update_track.return_value = _make_track()

        await mocks.handler.update_track(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, TrackUpdateIn(name="t")
        )

        update_call = mocks.track_repository.update_track.await_args
        assert update_call is not None
        assert update_call.kwargs["stages"] is None
        mocks.track_repository.get_track.assert_not_awaited()

    async def test_update_track_propagates_stage_sync_conflict(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )
        mocks.track_repository.update_track.side_effect = ApplicationError(
            "Cannot remove a stage that is assigned to a version.", 409
        )

        data = TrackUpdateIn(name="t", stages=[StageUpsertIn(name="x")])
        with pytest.raises(ApplicationError) as exc:
            await mocks.handler.update_track(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, data
            )
        assert exc.value.status_code == 409

    async def test_delete_track_deletes_track(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )

        await mocks.handler.delete_track(USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID)

        mocks.track_repository.delete_track.assert_awaited_once_with(TRACK_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.TRACK, Action.DELETE, ORBIT_ID
        )

    async def test_delete_track_raises_not_found_when_track_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = None
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID
        )

        with pytest.raises(NotFoundError, match="Track not found"):
            await mocks.handler.delete_track(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID
            )

    async def test_delete_track_raises_not_found_when_orbit_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.orbit_repository.get_orbit_simple.return_value = None
        with pytest.raises(NotFoundError, match="Orbit not found"):
            await mocks.handler.delete_track(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID
            )
