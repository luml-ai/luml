from datetime import datetime
from unittest.mock import Mock
from uuid import UUID

import pytest
from luml.handlers.tracks import TracksHandler
from luml.infra.exceptions import (
    ApplicationError,
    ArtifactTypeMismatchError,
    NotFoundError,
)
from luml.schemas.artifacts import ArtifactType
from luml.schemas.general import Cursor, SortOrder
from luml.schemas.permissions import Action, Resource
from luml.schemas.tracks import (
    TrackEntryCreateIn,
    TrackEntrySortBy,
    TrackEntryUpdate,
    TrackEntryUpdateIn,
)
from luml.utils.pagination import encode_cursor
from sqlalchemy.exc import IntegrityError

from tests.support.ids import (
    ARTIFACT_ID,
    COLLECTION_ID,
    ENTRY_ID,
    ORBIT_ID,
    ORGANIZATION_ID,
    OTHER_ORBIT_ID,
    STAGE_ID,
    TRACK_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.tracks.conftest import (
    USER_EMAIL,
    USER_NAME,
    _integrity_error,
    _make_entry,
    _make_stage,
    _make_track,
)


class TestTrackEntries:
    async def test_create_entry_creates_entry_without_stage(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.artifact_repository.get_artifact.return_value = Mock(
            type="model", collection_id=COLLECTION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            orbit_id=ORBIT_ID
        )
        mocks.user_repository.get_public_user_by_id.return_value = Mock(
            full_name=USER_NAME, email=USER_EMAIL
        )
        expected = _make_entry(version=1)
        mocks.entry_repository.create_entry.return_value = expected

        result = await mocks.handler.create_entry(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            TRACK_ID,
            TrackEntryCreateIn(artifact_id=ARTIFACT_ID),
        )

        assert result == expected
        create_call = mocks.entry_repository.create_entry.await_args
        assert create_call is not None
        assert create_call.args[0].stage_id is None
        assert create_call.args[0].added_by == USER_NAME
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.TRACK, Action.CREATE, ORBIT_ID
        )

    async def test_create_entry_passes_requested_stage(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.artifact_repository.get_artifact.return_value = Mock(
            type="model", collection_id=COLLECTION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            orbit_id=ORBIT_ID
        )
        mocks.user_repository.get_public_user_by_id.return_value = Mock(
            full_name=USER_NAME, email=USER_EMAIL
        )
        mocks.stage_repository.get_stage.return_value = _make_stage()
        mocks.entry_repository.get_entry_by_stage.return_value = None
        mocks.entry_repository.create_entry.return_value = _make_entry(
            stage_id=STAGE_ID
        )

        await mocks.handler.create_entry(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            TRACK_ID,
            TrackEntryCreateIn(artifact_id=ARTIFACT_ID, stage_id=STAGE_ID),
        )

        create_call = mocks.entry_repository.create_entry.await_args
        assert create_call is not None
        assert create_call.args[0].stage_id == STAGE_ID

    async def test_create_entry_raises_unprocessable_when_stage_belongs_to_other_track(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        foreign_track_id = UUID("0199c337-09fe-7a01-9f5f-000000000099")
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.artifact_repository.get_artifact.return_value = Mock(
            type="model", collection_id=COLLECTION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            orbit_id=ORBIT_ID
        )
        mocks.stage_repository.get_stage.return_value = _make_stage(
            track_id=foreign_track_id
        )

        with pytest.raises(ApplicationError, match="does not belong") as exc:
            await mocks.handler.create_entry(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                TrackEntryCreateIn(artifact_id=ARTIFACT_ID, stage_id=STAGE_ID),
            )
        assert exc.value.status_code == 422

    async def test_create_entry_raises_conflict_when_stage_is_already_assigned(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.artifact_repository.get_artifact.return_value = Mock(
            type="model", collection_id=COLLECTION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            orbit_id=ORBIT_ID
        )
        mocks.stage_repository.get_stage.return_value = _make_stage()
        mocks.entry_repository.get_entry_by_stage.return_value = _make_entry(version=2)

        with pytest.raises(ApplicationError, match="already assigned") as exc:
            await mocks.handler.create_entry(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                TrackEntryCreateIn(artifact_id=ARTIFACT_ID, stage_id=STAGE_ID),
            )
        assert exc.value.status_code == 409

    async def test_create_entry_raises_type_mismatch_when_artifact_type_differs(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track(
            artifact_type=ArtifactType.MODEL
        )
        mocks.artifact_repository.get_artifact.return_value = Mock(
            type="dataset", collection_id=COLLECTION_ID
        )

        with pytest.raises(ArtifactTypeMismatchError):
            await mocks.handler.create_entry(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                TrackEntryCreateIn(artifact_id=ARTIFACT_ID),
            )

    async def test_create_entry_raises_unprocessable_when_artifact_is_in_other_orbit(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.artifact_repository.get_artifact.return_value = Mock(
            type="model", collection_id=COLLECTION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            orbit_id=OTHER_ORBIT_ID
        )

        with pytest.raises(ApplicationError, match="same orbit") as exc:
            await mocks.handler.create_entry(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                TrackEntryCreateIn(artifact_id=ARTIFACT_ID),
            )
        assert exc.value.status_code == 422

    async def test_create_entry_raises_conflict_when_artifact_is_already_an_entry(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.artifact_repository.get_artifact.return_value = Mock(
            type="model", collection_id=COLLECTION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            orbit_id=ORBIT_ID
        )
        mocks.user_repository.get_public_user_by_id.return_value = Mock(
            full_name=USER_NAME, email=USER_EMAIL
        )
        mocks.entry_repository.create_entry.side_effect = IntegrityError(
            "", {}, Exception("uq_track_entries_track_id_artifact_id")
        )

        with pytest.raises(ApplicationError, match="already an entry") as exc:
            await mocks.handler.create_entry(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                TrackEntryCreateIn(artifact_id=ARTIFACT_ID),
            )
        assert exc.value.status_code == 409

    async def test_create_entry_raises_not_found_when_artifact_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.artifact_repository.get_artifact.return_value = None

        with pytest.raises(NotFoundError, match="Artifact not found"):
            await mocks.handler.create_entry(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                TrackEntryCreateIn(artifact_id=ARTIFACT_ID),
            )

    async def test_create_entry_raises_not_found_when_track_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = None
        with pytest.raises(NotFoundError, match="Track not found"):
            await mocks.handler.create_entry(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                TrackEntryCreateIn(artifact_id=ARTIFACT_ID),
            )

    async def test_create_entry_raises_not_found_when_user_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.artifact_repository.get_artifact.return_value = Mock(
            type="model", collection_id=COLLECTION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            orbit_id=ORBIT_ID
        )
        mocks.user_repository.get_public_user_by_id.return_value = None

        with pytest.raises(NotFoundError, match="User not found"):
            await mocks.handler.create_entry(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                TrackEntryCreateIn(artifact_id=ARTIFACT_ID),
            )

    async def test_create_entry_records_email_when_user_has_no_full_name(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.artifact_repository.get_artifact.return_value = Mock(
            type="model", collection_id=COLLECTION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            orbit_id=ORBIT_ID
        )
        mocks.user_repository.get_public_user_by_id.return_value = Mock(
            full_name=None, email=USER_EMAIL
        )
        mocks.entry_repository.create_entry.return_value = _make_entry(
            added_by=USER_EMAIL
        )

        await mocks.handler.create_entry(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            TRACK_ID,
            TrackEntryCreateIn(artifact_id=ARTIFACT_ID),
        )

        create_call = mocks.entry_repository.create_entry.await_args
        assert create_call is not None
        assert create_call.args[0].added_by == USER_EMAIL

    @pytest.mark.parametrize(
        ("error", "status", "message"),
        [
            (
                _integrity_error(constraint_name="uq_track_entries_track_id_stage_id"),
                409,
                "already assigned to another entry",
            ),
            (
                _integrity_error("fk_track_entries_stage_id_track_stages", "23503"),
                422,
                "does not belong to this track",
            ),
            (
                _integrity_error("track_entries_artifact_id_fkey", "23503"),
                404,
                "Artifact not found",
            ),
            (
                _integrity_error("track_entries_track_id_fkey", "23503"),
                404,
                "Track not found",
            ),
            (
                _integrity_error(
                    constraint_name="uq_track_entries_track_id_artifact_id"
                ),
                409,
                "already an entry in this track",
            ),
        ],
    )
    async def test_create_entry_maps_integrity_error_when_race_is_lost_after_checks(
        self,
        mocks: CollaboratorMocks[TracksHandler],
        error: IntegrityError,
        status: int,
        message: str,
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.artifact_repository.get_artifact.return_value = Mock(
            type="model", collection_id=COLLECTION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            orbit_id=ORBIT_ID
        )
        mocks.user_repository.get_public_user_by_id.return_value = Mock(
            full_name=USER_NAME, email=USER_EMAIL
        )
        mocks.stage_repository.get_stage.return_value = _make_stage(name="Production")
        mocks.entry_repository.get_entry_by_stage.return_value = None
        mocks.entry_repository.create_entry.side_effect = error

        with pytest.raises(ApplicationError, match=message) as exc:
            await mocks.handler.create_entry(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                TrackEntryCreateIn(artifact_id=ARTIFACT_ID, stage_id=STAGE_ID),
            )
        assert exc.value.status_code == status

    @pytest.mark.parametrize(
        "error",
        [
            _integrity_error(constraint_name="uq_track_entries_track_id_version"),
            _integrity_error("track_entries_orbit_id_fkey", "23503"),
            IntegrityError("", {}, Exception('null value in column "version"')),
        ],
    )
    async def test_create_entry_propagates_integrity_error_of_unrelated_constraint(
        self, mocks: CollaboratorMocks[TracksHandler], error: IntegrityError
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.artifact_repository.get_artifact.return_value = Mock(
            type="model", collection_id=COLLECTION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            orbit_id=ORBIT_ID
        )
        mocks.user_repository.get_public_user_by_id.return_value = Mock(
            full_name=USER_NAME, email=USER_EMAIL
        )
        mocks.entry_repository.create_entry.side_effect = error

        with pytest.raises(IntegrityError) as exc:
            await mocks.handler.create_entry(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                TrackEntryCreateIn(artifact_id=ARTIFACT_ID),
            )
        assert exc.value is error

    async def test_create_entry_propagates_integrity_error_of_unknown_foreign_key(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.artifact_repository.get_artifact.return_value = Mock(
            type="model", collection_id=COLLECTION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            orbit_id=ORBIT_ID
        )
        mocks.user_repository.get_public_user_by_id.return_value = Mock(
            full_name=USER_NAME, email=USER_EMAIL
        )
        mocks.entry_repository.create_entry.side_effect = _integrity_error(
            "track_entries_orbit_id_fkey", "23503"
        )

        with pytest.raises(IntegrityError):
            await mocks.handler.create_entry(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                TrackEntryCreateIn(artifact_id=ARTIFACT_ID),
            )

    async def test_get_entry_returns_entry(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        expected = _make_entry()
        mocks.entry_repository.get_entry.return_value = expected

        result = await mocks.handler.get_entry(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, ENTRY_ID
        )
        assert result == expected

    async def test_get_entry_raises_not_found_when_entry_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.entry_repository.get_entry.return_value = None

        with pytest.raises(NotFoundError, match="Entry not found"):
            await mocks.handler.get_entry(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, ENTRY_ID
            )

    async def test_get_entry_raises_not_found_when_entry_belongs_to_other_track(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        foreign_track_id = UUID("0199c337-09fe-7a01-9f5f-000000000005")
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.entry_repository.get_entry.return_value = _make_entry(
            track_id=foreign_track_id
        )

        with pytest.raises(NotFoundError, match="Entry not found"):
            await mocks.handler.get_entry(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, ENTRY_ID
            )

    async def test_get_entry_raises_not_found_when_track_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = None
        with pytest.raises(NotFoundError, match="Track not found"):
            await mocks.handler.get_entry(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, ENTRY_ID
            )

    async def test_get_entry_by_stage_returns_stage_entry(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.stage_repository.get_stage.return_value = _make_stage()
        expected = _make_entry()
        mocks.entry_repository.get_entry_by_stage.return_value = expected

        result = await mocks.handler.get_entry_by_stage(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, STAGE_ID
        )
        assert result == expected

    async def test_get_entry_by_stage_raises_not_found_when_stage_has_no_entry(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.stage_repository.get_stage.return_value = _make_stage()
        mocks.entry_repository.get_entry_by_stage.return_value = None

        with pytest.raises(NotFoundError, match="Entry not found"):
            await mocks.handler.get_entry_by_stage(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, STAGE_ID
            )

    async def test_get_entry_by_stage_raises_not_found_when_stage_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.stage_repository.get_stage.return_value = None
        with pytest.raises(NotFoundError, match="Stage not found"):
            await mocks.handler.get_entry_by_stage(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, STAGE_ID
            )

    async def test_get_entry_by_stage_raises_not_found_when_track_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = None
        with pytest.raises(NotFoundError, match="Track not found"):
            await mocks.handler.get_entry_by_stage(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, STAGE_ID
            )

    async def test_list_entries_returns_track_entries(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        entry = _make_entry()
        mocks.entry_repository.list_entries.return_value = ([entry], None)

        result = await mocks.handler.list_entries(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID
        )

        assert result.items == [entry]
        assert result.cursor is None

    async def test_list_entries_raises_not_found_when_track_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = None
        with pytest.raises(NotFoundError, match="Track not found"):
            await mocks.handler.list_entries(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID
            )

    async def test_list_entries_passes_cursor_when_cursor_is_valid(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.entry_repository.list_entries.return_value = ([], None)
        cursor_str = encode_cursor(
            Cursor(
                id=ENTRY_ID,
                value=datetime.now(),
                sort_by=TrackEntrySortBy.CREATED_AT.value,
                order=SortOrder.DESC,
                scope_id=TRACK_ID,
            )
        )

        await mocks.handler.list_entries(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, cursor_str=cursor_str
        )

        list_call = mocks.entry_repository.list_entries.await_args
        assert list_call is not None
        pagination = list_call.kwargs["pagination"]
        assert pagination.cursor is not None

    async def test_list_entries_for_artifact_returns_artifact_entries(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        entries = [_make_entry()]
        mocks.entry_repository.list_entries_for_artifact.return_value = entries

        result = await mocks.handler.list_entries_for_artifact(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, ARTIFACT_ID
        )

        assert result == entries
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.TRACK, Action.READ, ORBIT_ID
        )

    async def test_update_entry_assigns_free_stage(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.entry_repository.get_entry.return_value = _make_entry()
        mocks.stage_repository.get_stage.return_value = _make_stage()
        mocks.entry_repository.get_entry_by_stage.return_value = None
        expected = _make_entry(stage_id=STAGE_ID)
        mocks.entry_repository.update_entry.return_value = expected

        result = await mocks.handler.update_entry(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            TRACK_ID,
            ENTRY_ID,
            TrackEntryUpdateIn(stage_id=STAGE_ID),
        )

        assert result == expected
        mocks.entry_repository.update_entry.assert_awaited_once()

    async def test_update_entry_raises_conflict_when_stage_is_held_and_not_forced(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        holding_entry_id = UUID("0199c337-09fa-7001-af00-000000000002")
        mocks.entry_repository.get_entry.return_value = _make_entry()
        mocks.stage_repository.get_stage.return_value = _make_stage(name="Production")
        mocks.entry_repository.get_entry_by_stage.return_value = _make_entry(
            id=holding_entry_id, version=1
        )

        with pytest.raises(ApplicationError, match="already assigned") as exc:
            await mocks.handler.update_entry(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                ENTRY_ID,
                TrackEntryUpdateIn(stage_id=STAGE_ID),
            )
        assert exc.value.status_code == 409

    async def test_update_entry_reassigns_held_stage_when_forced(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        holding_entry_id = UUID("0199c337-09fa-7001-af00-000000000002")
        mocks.entry_repository.get_entry.return_value = _make_entry()
        mocks.stage_repository.get_stage.return_value = _make_stage(name="Production")
        mocks.entry_repository.get_entry_by_stage.return_value = _make_entry(
            id=holding_entry_id, version=1
        )
        expected = _make_entry(stage_id=STAGE_ID)
        mocks.entry_repository.update_entry.return_value = expected

        result = await mocks.handler.update_entry(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            TRACK_ID,
            ENTRY_ID,
            TrackEntryUpdateIn(stage_id=STAGE_ID),
            force=True,
        )

        assert result == expected
        mocks.entry_repository.update_entry.assert_awaited_once_with(
            ENTRY_ID, TrackEntryUpdate(stage_id=STAGE_ID), force=True
        )

    async def test_update_entry_raises_unprocessable_when_stage_belongs_to_other_track(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        foreign_track_id = UUID("0199c337-09fa-7001-af00-000000000003")
        mocks.entry_repository.get_entry.return_value = _make_entry()
        mocks.stage_repository.get_stage.return_value = _make_stage(
            track_id=foreign_track_id
        )

        with pytest.raises(ApplicationError, match="does not belong") as exc:
            await mocks.handler.update_entry(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                ENTRY_ID,
                TrackEntryUpdateIn(stage_id=STAGE_ID),
            )
        assert exc.value.status_code == 422

    async def test_update_entry_removes_stage(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.entry_repository.get_entry.return_value = _make_entry(stage_id=STAGE_ID)
        expected = _make_entry(stage_id=None)
        mocks.entry_repository.update_entry.return_value = expected

        result = await mocks.handler.update_entry(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            TRACK_ID,
            ENTRY_ID,
            TrackEntryUpdateIn(stage_id=None),
        )

        assert result.stage_id is None

    async def test_update_entry_raises_not_found_when_entry_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.entry_repository.get_entry.return_value = None
        with pytest.raises(NotFoundError, match="Entry not found"):
            await mocks.handler.update_entry(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                ENTRY_ID,
                TrackEntryUpdateIn(),
            )

    async def test_update_entry_raises_not_found_when_update_finds_no_entry(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.entry_repository.get_entry.return_value = _make_entry()
        mocks.entry_repository.update_entry.return_value = None
        with pytest.raises(NotFoundError, match="Entry not found"):
            await mocks.handler.update_entry(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                ENTRY_ID,
                TrackEntryUpdateIn(),
            )

    @pytest.mark.parametrize(
        ("error", "status", "message"),
        [
            (
                _integrity_error(constraint_name="uq_track_entries_track_id_stage_id"),
                409,
                "already assigned to another entry",
            ),
            (
                _integrity_error("fk_track_entries_stage_id_track_stages", "23503"),
                422,
                "does not belong to this track",
            ),
        ],
    )
    async def test_update_entry_maps_integrity_error_when_race_is_lost_after_checks(
        self,
        mocks: CollaboratorMocks[TracksHandler],
        error: IntegrityError,
        status: int,
        message: str,
    ) -> None:
        mocks.entry_repository.get_entry.return_value = _make_entry()
        mocks.stage_repository.get_stage.return_value = _make_stage(name="Production")
        mocks.entry_repository.get_entry_by_stage.return_value = None
        mocks.entry_repository.update_entry.side_effect = error

        with pytest.raises(ApplicationError, match=message) as exc:
            await mocks.handler.update_entry(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                ENTRY_ID,
                TrackEntryUpdateIn(stage_id=STAGE_ID),
            )
        assert exc.value.status_code == status

    async def test_delete_entry_deletes_entry(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.entry_repository.get_entry.return_value = _make_entry()

        await mocks.handler.delete_entry(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, ENTRY_ID
        )

        mocks.entry_repository.delete_entry.assert_awaited_once_with(ENTRY_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.TRACK, Action.DELETE, ORBIT_ID
        )

    async def test_delete_entry_raises_not_found_when_entry_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.entry_repository.get_entry.return_value = None
        with pytest.raises(NotFoundError, match="Entry not found"):
            await mocks.handler.delete_entry(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, ENTRY_ID
            )

    async def test_delete_entries_deletes_track_entries(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        entry_ids = [ENTRY_ID, UUID("0199c337-09fd-7b02-af60-000000000004")]

        await mocks.handler.delete_entries(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, entry_ids
        )

        mocks.entry_repository.delete_entries.assert_awaited_once_with(
            TRACK_ID, entry_ids
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.TRACK, Action.DELETE, ORBIT_ID
        )

    async def test_delete_entries_raises_not_found_when_track_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = None
        with pytest.raises(NotFoundError, match="Track not found"):
            await mocks.handler.delete_entries(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, [ENTRY_ID]
            )
        mocks.entry_repository.delete_entries.assert_not_awaited()
