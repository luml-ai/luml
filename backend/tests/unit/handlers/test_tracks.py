from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
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
    Stage,
    StageCreateIn,
    StageUpdateIn,
    StageUpsertIn,
    Track,
    TrackCreateIn,
    TrackEntry,
    TrackEntryCreateIn,
    TrackEntrySortBy,
    TrackEntryUpdate,
    TrackEntryUpdateIn,
    TracksList,
    TrackSortBy,
    TrackUpdateIn,
)
from luml.utils.pagination import encode_cursor
from sqlalchemy.exc import IntegrityError

tracks_handler = TracksHandler()

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ORG_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
ORBIT_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")
TRACK_ID = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
ENTRY_ID = UUID("0199c337-09f5-7b02-af60-6079ec73d081")
ARTIFACT_ID = UUID("0199c337-09f6-7c03-bf71-7180fd84e192")
STAGE_ID = UUID("0199c337-09f7-7d04-cf82-8291ae95f2a3")
COLLECTION_ID = UUID("0199c337-09f8-7e05-df93-93a2bfa603b4")


def _make_track(**overrides: object) -> Track:
    defaults: dict[str, object] = {
        "id": TRACK_ID,
        "orbit_id": ORBIT_ID,
        "name": "churn-model",
        "artifact_type": "model",
        "description": None,
        "tags": None,
        "next_version": 1,
        "total_entries": 0,
        "created_at": datetime.now(),
        "updated_at": None,
    }
    defaults.update(overrides)
    return Track(**defaults)  # type: ignore[arg-type]


def _make_entry(**overrides: object) -> TrackEntry:
    defaults: dict[str, object] = {
        "id": ENTRY_ID,
        "track_id": TRACK_ID,
        "artifact_id": ARTIFACT_ID,
        "version": 1,
        "stage_id": None,
        "added_by": USER_ID,
        "created_at": datetime.now(),
        "updated_at": None,
    }
    defaults.update(overrides)
    return TrackEntry(**defaults)  # type: ignore[arg-type]


def _make_stage(**overrides: object) -> Stage:
    defaults: dict[str, object] = {
        "id": STAGE_ID,
        "track_id": TRACK_ID,
        "name": "Staging",
        "created_at": datetime.now(),
        "updated_at": None,
    }
    defaults.update(overrides)
    return Stage(**defaults)  # type: ignore[arg-type]


# ---- TracksHandler ----


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.create_track",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_track(
    mock_create_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    data = TrackCreateIn(
        name="churn-model", artifact_type=ArtifactType.MODEL, stages=["Staging", "Prod"]
    )
    expected = _make_track()
    mock_create_track.return_value = expected
    mock_get_orbit.return_value = Mock(organization_id=ORG_ID)

    result = await tracks_handler.create_track(USER_ID, ORG_ID, ORBIT_ID, data)

    assert result == expected
    mock_create_track.assert_awaited_once()
    # Stages passed through as-is (no default fallback).
    assert mock_create_track.await_args.kwargs["stage_names"] == ["Staging", "Prod"]
    mock_perms.assert_awaited_once_with(
        ORG_ID, USER_ID, Resource.TRACK, Action.CREATE, ORBIT_ID
    )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.create_track",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_track_without_stages(
    mock_create_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    # No stages provided -> no default fallback, track created with none.
    data = TrackCreateIn(name="churn-model", artifact_type=ArtifactType.MODEL)
    mock_create_track.return_value = _make_track()
    mock_get_orbit.return_value = Mock(organization_id=ORG_ID)

    await tracks_handler.create_track(USER_ID, ORG_ID, ORBIT_ID, data)

    assert mock_create_track.await_args.kwargs["stage_names"] == []


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.create_track",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_track_other_integrity_error_propagates(
    mock_create_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    # An unrelated constraint (e.g. a not-null violation) must not be masked
    # as a duplicate-name 409 — it should surface as-is.
    data = TrackCreateIn(name="churn-model", artifact_type=ArtifactType.MODEL)
    mock_get_orbit.return_value = Mock(organization_id=ORG_ID)
    mock_create_track.side_effect = IntegrityError(
        "", {}, Exception('null value in column "created_by"')
    )

    with pytest.raises(IntegrityError):
        await tracks_handler.create_track(USER_ID, ORG_ID, ORBIT_ID, data)


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.create_track",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_track_duplicate_stage_name(
    mock_create_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    data = TrackCreateIn(
        name="churn-model", artifact_type=ArtifactType.MODEL, stages=["Dup", "Dup"]
    )
    mock_get_orbit.return_value = Mock(organization_id=ORG_ID)
    mock_create_track.side_effect = IntegrityError(
        "", {}, Exception("uq_track_stages_track_id_name")
    )

    with pytest.raises(ApplicationError, match="Duplicate stage names") as exc:
        await tracks_handler.create_track(USER_ID, ORG_ID, ORBIT_ID, data)
    assert exc.value.status_code == 409


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_track_orbit_not_found(
    mock_get_orbit: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = None
    data = TrackCreateIn(name="churn-model", artifact_type=ArtifactType.MODEL)

    with pytest.raises(NotFoundError, match="Orbit not found"):
        await tracks_handler.create_track(USER_ID, ORG_ID, ORBIT_ID, data)


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_track(
    mock_get: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    expected = _make_track()
    mock_get.return_value = expected

    result = await tracks_handler.get_track(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID)

    assert result == expected
    mock_perms.assert_awaited_once_with(
        ORG_ID, USER_ID, Resource.TRACK, Action.READ, ORBIT_ID
    )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_track_not_found(
    mock_get: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get.return_value = None
    with pytest.raises(NotFoundError, match="Track not found"):
        await tracks_handler.get_track(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID)


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_track_wrong_orbit(
    mock_get: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    other_orbit = UUID("0199c337-09fa-7001-af00-000000000001")
    mock_get.return_value = _make_track(orbit_id=other_orbit)
    with pytest.raises(NotFoundError, match="Track not found"):
        await tracks_handler.get_track(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID)


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_orbit_tracks",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_tracks(
    mock_list: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    track = _make_track()
    mock_get_orbit.return_value = Mock(organization_id=ORG_ID)
    mock_list.return_value = ([track], None)

    result = await tracks_handler.list_tracks(USER_ID, ORG_ID, ORBIT_ID)

    assert result == TracksList(items=[track], cursor=None)
    mock_perms.assert_awaited_once_with(
        ORG_ID, USER_ID, Resource.TRACK, Action.LIST, ORBIT_ID
    )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.update_track",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_track(
    mock_update: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    data_in = TrackUpdateIn(name="new-name")
    expected = _make_track(name="new-name")
    mock_update.return_value = expected
    mock_get_orbit.return_value = Mock(organization_id=ORG_ID)

    result = await tracks_handler.update_track(
        USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, data_in
    )

    assert result == expected
    mock_perms.assert_awaited_once_with(
        ORG_ID, USER_ID, Resource.TRACK, Action.UPDATE, ORBIT_ID
    )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.update_track",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_track_partial_does_not_null_unset_fields(
    mock_update: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    # Only `name` is provided -> the TrackUpdate passed to the repo must mark
    # only `name` as set, so exclude_unset leaves description/tags untouched.
    data_in = TrackUpdateIn(name="new-name")
    mock_update.return_value = _make_track(name="new-name")
    mock_get_orbit.return_value = Mock(organization_id=ORG_ID)

    await tracks_handler.update_track(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, data_in)

    passed_update = mock_update.await_args.args[1]
    dumped = passed_update.model_dump(exclude_unset=True, exclude={"id"})
    assert dumped == {"name": "new-name"}
    assert "description" not in dumped
    assert "tags" not in dumped


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.update_track",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_track_not_found(
    mock_update: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_update.return_value = None
    mock_get_orbit.return_value = Mock(organization_id=ORG_ID)

    with pytest.raises(NotFoundError, match="Track not found"):
        await tracks_handler.update_track(
            USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, TrackUpdateIn(name="new")
        )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.delete_track",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_track(
    mock_delete: AsyncMock,
    mock_get: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get.return_value = _make_track()
    mock_get_orbit.return_value = Mock(organization_id=ORG_ID)

    await tracks_handler.delete_track(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID)

    mock_delete.assert_awaited_once_with(TRACK_ID)
    mock_perms.assert_awaited_once_with(
        ORG_ID, USER_ID, Resource.TRACK, Action.DELETE, ORBIT_ID
    )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_track_not_found(
    mock_get: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get.return_value = None
    mock_get_orbit.return_value = Mock(organization_id=ORG_ID)

    with pytest.raises(NotFoundError, match="Track not found"):
        await tracks_handler.delete_track(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID)


# ---- TrackEntriesHandler ----


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.create_entry",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_entry(
    mock_create: AsyncMock,
    mock_get_coll: AsyncMock,
    mock_get_art: AsyncMock,
    mock_get_track: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_track.return_value = _make_track()
    mock_get_art.return_value = Mock(type="model", collection_id=COLLECTION_ID)
    mock_get_coll.return_value = Mock(orbit_id=ORBIT_ID)
    expected = _make_entry(version=1)
    mock_create.return_value = expected

    result = await tracks_handler.create_entry(
        USER_ID,
        ORG_ID,
        ORBIT_ID,
        TRACK_ID,
        TrackEntryCreateIn(artifact_id=ARTIFACT_ID),
    )

    assert result == expected
    # No stage requested -> repo receives stage_id=None.
    assert mock_create.await_args.args[0].stage_id is None
    mock_perms.assert_awaited_once_with(
        ORG_ID, USER_ID, Resource.TRACK, Action.CREATE, ORBIT_ID
    )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@patch("luml.handlers.tracks.ArtifactRepository.get_artifact", new_callable=AsyncMock)
@patch(
    "luml.handlers.tracks.CollectionRepository.get_collection", new_callable=AsyncMock
)
@patch("luml.handlers.tracks.TrackStageRepository.get_stage", new_callable=AsyncMock)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.get_entry_by_stage",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackEntryRepository.create_entry", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_create_entry_with_stage(
    mock_create: AsyncMock,
    mock_by_stage: AsyncMock,
    mock_get_stage: AsyncMock,
    mock_get_coll: AsyncMock,
    mock_get_art: AsyncMock,
    mock_get_track: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_track.return_value = _make_track()
    mock_get_art.return_value = Mock(type="model", collection_id=COLLECTION_ID)
    mock_get_coll.return_value = Mock(orbit_id=ORBIT_ID)
    mock_get_stage.return_value = _make_stage()  # belongs to TRACK_ID
    mock_by_stage.return_value = None  # stage free
    mock_create.return_value = _make_entry(stage_id=STAGE_ID)

    await tracks_handler.create_entry(
        USER_ID,
        ORG_ID,
        ORBIT_ID,
        TRACK_ID,
        TrackEntryCreateIn(artifact_id=ARTIFACT_ID, stage_id=STAGE_ID),
    )

    assert mock_create.await_args.args[0].stage_id == STAGE_ID


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@patch("luml.handlers.tracks.ArtifactRepository.get_artifact", new_callable=AsyncMock)
@patch(
    "luml.handlers.tracks.CollectionRepository.get_collection", new_callable=AsyncMock
)
@patch("luml.handlers.tracks.TrackStageRepository.get_stage", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_create_entry_stage_from_wrong_track(
    mock_get_stage: AsyncMock,
    mock_get_coll: AsyncMock,
    mock_get_art: AsyncMock,
    mock_get_track: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    other_track = UUID("0199c337-09fe-7a01-9f5f-000000000099")
    mock_get_track.return_value = _make_track()
    mock_get_art.return_value = Mock(type="model", collection_id=COLLECTION_ID)
    mock_get_coll.return_value = Mock(orbit_id=ORBIT_ID)
    mock_get_stage.return_value = _make_stage(track_id=other_track)

    with pytest.raises(ApplicationError, match="does not belong") as exc:
        await tracks_handler.create_entry(
            USER_ID,
            ORG_ID,
            ORBIT_ID,
            TRACK_ID,
            TrackEntryCreateIn(artifact_id=ARTIFACT_ID, stage_id=STAGE_ID),
        )
    assert exc.value.status_code == 422


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@patch("luml.handlers.tracks.ArtifactRepository.get_artifact", new_callable=AsyncMock)
@patch(
    "luml.handlers.tracks.CollectionRepository.get_collection", new_callable=AsyncMock
)
@patch("luml.handlers.tracks.TrackStageRepository.get_stage", new_callable=AsyncMock)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.get_entry_by_stage",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_entry_stage_already_used(
    mock_by_stage: AsyncMock,
    mock_get_stage: AsyncMock,
    mock_get_coll: AsyncMock,
    mock_get_art: AsyncMock,
    mock_get_track: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_track.return_value = _make_track()
    mock_get_art.return_value = Mock(type="model", collection_id=COLLECTION_ID)
    mock_get_coll.return_value = Mock(orbit_id=ORBIT_ID)
    mock_get_stage.return_value = _make_stage()
    # Stage already assigned to another entry.
    mock_by_stage.return_value = _make_entry(version=2)

    with pytest.raises(ApplicationError, match="already assigned") as exc:
        await tracks_handler.create_entry(
            USER_ID,
            ORG_ID,
            ORBIT_ID,
            TRACK_ID,
            TrackEntryCreateIn(artifact_id=ARTIFACT_ID, stage_id=STAGE_ID),
        )
    assert exc.value.status_code == 400


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_entry_wrong_type(
    mock_get_art: AsyncMock,
    mock_get_track: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_track.return_value = _make_track(artifact_type=ArtifactType.MODEL)
    mock_get_art.return_value = Mock(type="dataset", collection_id=COLLECTION_ID)

    with pytest.raises(ArtifactTypeMismatchError):
        await tracks_handler.create_entry(
            USER_ID,
            ORG_ID,
            ORBIT_ID,
            TRACK_ID,
            TrackEntryCreateIn(artifact_id=ARTIFACT_ID),
        )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_entry_different_orbit(
    mock_get_coll: AsyncMock,
    mock_get_art: AsyncMock,
    mock_get_track: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    other_orbit = UUID("0199c337-09fa-7001-af00-000000000001")
    mock_get_track.return_value = _make_track()
    mock_get_art.return_value = Mock(type="model", collection_id=COLLECTION_ID)
    mock_get_coll.return_value = Mock(orbit_id=other_orbit)

    with pytest.raises(ApplicationError, match="same orbit") as exc:
        await tracks_handler.create_entry(
            USER_ID,
            ORG_ID,
            ORBIT_ID,
            TRACK_ID,
            TrackEntryCreateIn(artifact_id=ARTIFACT_ID),
        )
    assert exc.value.status_code == 422


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.create_entry",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_entry_duplicate(
    mock_create: AsyncMock,
    mock_get_coll: AsyncMock,
    mock_get_art: AsyncMock,
    mock_get_track: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_track.return_value = _make_track()
    mock_get_art.return_value = Mock(type="model", collection_id=COLLECTION_ID)
    mock_get_coll.return_value = Mock(orbit_id=ORBIT_ID)
    mock_create.side_effect = IntegrityError("", {}, None)

    with pytest.raises(ApplicationError, match="already an entry") as exc:
        await tracks_handler.create_entry(
            USER_ID,
            ORG_ID,
            ORBIT_ID,
            TRACK_ID,
            TrackEntryCreateIn(artifact_id=ARTIFACT_ID),
        )
    assert exc.value.status_code == 409


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_entry_artifact_not_found(
    mock_get_art: AsyncMock,
    mock_get_track: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_track.return_value = _make_track()
    mock_get_art.return_value = None

    with pytest.raises(NotFoundError, match="Artifact not found"):
        await tracks_handler.create_entry(
            USER_ID,
            ORG_ID,
            ORBIT_ID,
            TRACK_ID,
            TrackEntryCreateIn(artifact_id=ARTIFACT_ID),
        )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.list_entries",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_entries(
    mock_list: AsyncMock,
    mock_get_track: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_track.return_value = _make_track()
    entry = _make_entry()
    mock_list.return_value = ([entry], None)

    result = await tracks_handler.list_entries(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID)

    assert result.items == [entry]
    assert result.cursor is None


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.get_entry",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackStageRepository.get_stage",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.get_entry_by_stage",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.update_entry",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_entry_assign_free_stage(
    mock_update: AsyncMock,
    mock_by_stage: AsyncMock,
    mock_get_stage: AsyncMock,
    mock_get_entry: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_entry.return_value = _make_entry()
    mock_get_stage.return_value = _make_stage()
    mock_by_stage.return_value = None
    expected = _make_entry(stage_id=STAGE_ID)
    mock_update.return_value = expected

    result = await tracks_handler.update_entry(
        USER_ID,
        ORG_ID,
        ORBIT_ID,
        TRACK_ID,
        ENTRY_ID,
        TrackEntryUpdateIn(stage_id=STAGE_ID),
    )

    assert result == expected
    mock_update.assert_awaited_once()


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.get_entry",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackStageRepository.get_stage",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.get_entry_by_stage",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_entry_stage_conflict_no_force(
    mock_by_stage: AsyncMock,
    mock_get_stage: AsyncMock,
    mock_get_entry: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    other_entry_id = UUID("0199c337-09fa-7001-af00-000000000002")
    mock_get_entry.return_value = _make_entry()
    mock_get_stage.return_value = _make_stage(name="Production")
    mock_by_stage.return_value = _make_entry(id=other_entry_id, version=1)

    with pytest.raises(ApplicationError, match="already assigned") as exc:
        await tracks_handler.update_entry(
            USER_ID,
            ORG_ID,
            ORBIT_ID,
            TRACK_ID,
            ENTRY_ID,
            TrackEntryUpdateIn(stage_id=STAGE_ID),
        )
    assert exc.value.status_code == 409


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.get_entry",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackStageRepository.get_stage",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.get_entry_by_stage",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.update_entry",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_entry_stage_conflict_with_force(
    mock_update: AsyncMock,
    mock_by_stage: AsyncMock,
    mock_get_stage: AsyncMock,
    mock_get_entry: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    other_entry_id = UUID("0199c337-09fa-7001-af00-000000000002")
    mock_get_entry.return_value = _make_entry()
    mock_get_stage.return_value = _make_stage(name="Production")
    mock_by_stage.return_value = _make_entry(id=other_entry_id, version=1)
    expected = _make_entry(stage_id=STAGE_ID)
    mock_update.return_value = expected

    result = await tracks_handler.update_entry(
        USER_ID,
        ORG_ID,
        ORBIT_ID,
        TRACK_ID,
        ENTRY_ID,
        TrackEntryUpdateIn(stage_id=STAGE_ID),
        force=True,
    )

    assert result == expected
    mock_update.assert_awaited_once_with(
        ENTRY_ID, TrackEntryUpdate(stage_id=STAGE_ID), force=True
    )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.get_entry",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackStageRepository.get_stage",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_entry_stage_from_wrong_track(
    mock_get_stage: AsyncMock,
    mock_get_entry: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    other_track = UUID("0199c337-09fa-7001-af00-000000000003")
    mock_get_entry.return_value = _make_entry()
    mock_get_stage.return_value = _make_stage(track_id=other_track)

    with pytest.raises(ApplicationError, match="does not belong") as exc:
        await tracks_handler.update_entry(
            USER_ID,
            ORG_ID,
            ORBIT_ID,
            TRACK_ID,
            ENTRY_ID,
            TrackEntryUpdateIn(stage_id=STAGE_ID),
        )
    assert exc.value.status_code == 422


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.get_entry",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.update_entry",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_entry_remove_stage(
    mock_update: AsyncMock,
    mock_get_entry: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_entry.return_value = _make_entry(stage_id=STAGE_ID)
    expected = _make_entry(stage_id=None)
    mock_update.return_value = expected

    result = await tracks_handler.update_entry(
        USER_ID,
        ORG_ID,
        ORBIT_ID,
        TRACK_ID,
        ENTRY_ID,
        TrackEntryUpdateIn(stage_id=None),
    )

    assert result.stage_id is None


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.get_entry",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.delete_entry",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_entry(
    mock_delete: AsyncMock,
    mock_get: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get.return_value = _make_entry()

    await tracks_handler.delete_entry(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, ENTRY_ID)

    mock_delete.assert_awaited_once_with(ENTRY_ID)
    mock_perms.assert_awaited_once_with(
        ORG_ID, USER_ID, Resource.TRACK, Action.DELETE, ORBIT_ID
    )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.get_entry",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_entry_not_found(
    mock_get: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get.return_value = None
    with pytest.raises(NotFoundError, match="Entry not found"):
        await tracks_handler.delete_entry(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, ENTRY_ID)


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.delete_entries", new_callable=AsyncMock
)
@pytest.mark.asyncio
async def test_delete_entries(
    mock_delete_entries: AsyncMock,
    mock_get_track: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_track.return_value = _make_track()
    entry_ids = [ENTRY_ID, UUID("0199c337-09fd-7b02-af60-000000000004")]

    await tracks_handler.delete_entries(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, entry_ids)

    mock_delete_entries.assert_awaited_once_with(TRACK_ID, entry_ids)
    mock_perms.assert_awaited_once_with(
        ORG_ID, USER_ID, Resource.TRACK, Action.DELETE, ORBIT_ID
    )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.delete_entries", new_callable=AsyncMock
)
@pytest.mark.asyncio
async def test_delete_entries_track_not_found(
    mock_delete_entries: AsyncMock,
    mock_get_track: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_track.return_value = None
    with pytest.raises(NotFoundError, match="Track not found"):
        await tracks_handler.delete_entries(
            USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, [ENTRY_ID]
        )
    mock_delete_entries.assert_not_awaited()


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.list_entries_for_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_entries_for_artifact(
    mock_list: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    entries = [_make_entry()]
    mock_list.return_value = entries

    result = await tracks_handler.list_entries_for_artifact(
        USER_ID, ORG_ID, ORBIT_ID, ARTIFACT_ID
    )

    assert result == entries
    mock_perms.assert_awaited_once_with(
        ORG_ID, USER_ID, Resource.TRACK, Action.READ, ORBIT_ID
    )


# ---- TrackStagesHandler ----


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackStageRepository.create_stage",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_stage(
    mock_create: AsyncMock,
    mock_get_track: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_track.return_value = _make_track()
    expected = _make_stage(name="QA")
    mock_create.return_value = expected

    result = await tracks_handler.create_stage(
        USER_ID,
        ORG_ID,
        ORBIT_ID,
        TRACK_ID,
        StageCreateIn(name="QA"),
    )

    assert result == expected


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackStageRepository.create_stage",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_stage_duplicate_name(
    mock_create: AsyncMock,
    mock_get_track: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_track.return_value = _make_track()
    mock_create.side_effect = IntegrityError("", {}, None)

    with pytest.raises(ApplicationError, match="already exists") as exc:
        await tracks_handler.create_stage(
            USER_ID,
            ORG_ID,
            ORBIT_ID,
            TRACK_ID,
            StageCreateIn(name="Staging"),
        )
    assert exc.value.status_code == 409


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackStageRepository.list_stages",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_stages(
    mock_list: AsyncMock,
    mock_get_track: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_track.return_value = _make_track()
    stages = [_make_stage()]
    mock_list.return_value = stages

    result = await tracks_handler.list_stages(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID)

    assert result == stages


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackStageRepository.update_stage",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_stage(
    mock_update: AsyncMock,
    mock_get_track: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_track.return_value = _make_track()
    expected = _make_stage(name="Renamed")
    mock_update.return_value = expected

    result = await tracks_handler.update_stage(
        USER_ID,
        ORG_ID,
        ORBIT_ID,
        TRACK_ID,
        STAGE_ID,
        StageUpdateIn(name="Renamed"),
    )

    assert result == expected


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackStageRepository.update_stage",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_stage_not_found(
    mock_update: AsyncMock,
    mock_get_track: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_track.return_value = _make_track()
    mock_update.return_value = None

    with pytest.raises(NotFoundError, match="Stage not found"):
        await tracks_handler.update_stage(
            USER_ID,
            ORG_ID,
            ORBIT_ID,
            TRACK_ID,
            STAGE_ID,
            StageUpdateIn(name="Renamed"),
        )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackStageRepository.is_stage_in_use",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackStageRepository.delete_stage",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_stage_not_in_use(
    mock_delete: AsyncMock,
    mock_in_use: AsyncMock,
    mock_get_track: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_track.return_value = _make_track()
    mock_in_use.return_value = False

    await tracks_handler.delete_stage(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, STAGE_ID)

    mock_delete.assert_awaited_once_with(STAGE_ID)


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackStageRepository.is_stage_in_use",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_stage_in_use_no_force(
    mock_in_use: AsyncMock,
    mock_get_track: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_track.return_value = _make_track()
    mock_in_use.return_value = True

    with pytest.raises(ApplicationError, match="currently assigned") as exc:
        await tracks_handler.delete_stage(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, STAGE_ID)
    assert exc.value.status_code == 409


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackStageRepository.is_stage_in_use",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackStageRepository.clear_stage_from_entries",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackStageRepository.delete_stage",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_stage_in_use_with_force(
    mock_delete: AsyncMock,
    mock_clear: AsyncMock,
    mock_in_use: AsyncMock,
    mock_get_track: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_track.return_value = _make_track()
    mock_in_use.return_value = True

    await tracks_handler.delete_stage(
        USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, STAGE_ID, force=True
    )

    mock_clear.assert_awaited_once_with(TRACK_ID, STAGE_ID)
    mock_delete.assert_awaited_once_with(STAGE_ID)


# ---- Artifact deletion blocked by tracks ----


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.TrackEntryRepository.has_entries_for_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_artifact_deletion_checks_blocked_by_tracks(
    mock_has_entries: AsyncMock,
    mock_get_details: AsyncMock,
    mock_check_access: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    from luml.handlers.artifacts import ArtifactHandler

    handler = ArtifactHandler()

    mock_check_access.return_value = None
    mock_get_details.return_value = Mock(deployments=None)
    mock_has_entries.return_value = True

    with pytest.raises(
        ApplicationError, match="referenced by one or more tracks"
    ) as exc:
        await handler._artifact_deletion_checks(
            USER_ID, ORG_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
        )
    assert exc.value.status_code == 409


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.TrackEntryRepository.has_entries_for_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_artifact_deletion_checks_not_blocked_when_no_entries(
    mock_has_entries: AsyncMock,
    mock_get_details: AsyncMock,
    mock_check_access: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    from luml.handlers.artifacts import ArtifactHandler

    handler = ArtifactHandler()

    artifact_mock = Mock(deployments=None)
    mock_check_access.return_value = None
    mock_get_details.return_value = artifact_mock
    mock_has_entries.return_value = False

    result = await handler._artifact_deletion_checks(
        USER_ID, ORG_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
    )
    assert result == artifact_mock


# ---- Coverage: cursor validation ----


def test_validate_cursor_matches_returns_cursor() -> None:
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


def test_validate_cursor_mismatch_returns_none() -> None:
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


# ---- Coverage: orbit / track / duplicate guards ----


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.OrbitRepository.get_orbit_simple", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_list_tracks_orbit_not_found(
    mock_get_orbit: AsyncMock, mock_perms: AsyncMock
) -> None:
    mock_get_orbit.return_value = None
    with pytest.raises(NotFoundError, match="Orbit not found"):
        await tracks_handler.list_tracks(USER_ID, ORG_ID, ORBIT_ID)


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.OrbitRepository.get_orbit_simple", new_callable=AsyncMock)
@patch("luml.handlers.tracks.TrackRepository.get_orbit_tracks", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_list_tracks_with_valid_cursor(
    mock_list: AsyncMock, mock_get_orbit: AsyncMock, mock_perms: AsyncMock
) -> None:
    mock_get_orbit.return_value = Mock(organization_id=ORG_ID)
    mock_list.return_value = ([], None)
    cursor_str = encode_cursor(
        Cursor(
            id=TRACK_ID,
            value=datetime.now(),
            sort_by=TrackSortBy.CREATED_AT.value,
            order=SortOrder.DESC,
            scope_id=ORBIT_ID,
        )
    )

    await tracks_handler.list_tracks(USER_ID, ORG_ID, ORBIT_ID, cursor_str=cursor_str)

    pagination = mock_list.await_args.kwargs["pagination"]
    assert pagination.cursor is not None


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.OrbitRepository.get_orbit_simple", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_update_track_orbit_not_found(
    mock_get_orbit: AsyncMock, mock_perms: AsyncMock
) -> None:
    mock_get_orbit.return_value = None
    with pytest.raises(NotFoundError, match="Orbit not found"):
        await tracks_handler.update_track(
            USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, TrackUpdateIn(name="x")
        )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.OrbitRepository.get_orbit_simple", new_callable=AsyncMock)
@patch("luml.handlers.tracks.TrackRepository.update_track", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_update_track_duplicate_stage_name(
    mock_update: AsyncMock, mock_get_orbit: AsyncMock, mock_perms: AsyncMock
) -> None:
    # Track names are not unique; only duplicate stage names map to 409.
    mock_get_orbit.return_value = Mock(organization_id=ORG_ID)
    mock_update.side_effect = IntegrityError(
        "", {}, Exception("uq_track_stages_track_id_name")
    )
    with pytest.raises(ApplicationError, match="Duplicate stage names") as exc:
        await tracks_handler.update_track(
            USER_ID,
            ORG_ID,
            ORBIT_ID,
            TRACK_ID,
            TrackUpdateIn(name="t", stages=[StageUpsertIn(name="dup")]),
        )
    assert exc.value.status_code == 409


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.OrbitRepository.get_orbit_simple", new_callable=AsyncMock)
@patch("luml.handlers.tracks.TrackRepository.update_track", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_update_track_other_integrity_error_propagates(
    mock_update: AsyncMock, mock_get_orbit: AsyncMock, mock_perms: AsyncMock
) -> None:
    mock_get_orbit.return_value = Mock(organization_id=ORG_ID)
    mock_update.side_effect = IntegrityError("", {}, Exception("some other constraint"))
    with pytest.raises(IntegrityError):
        await tracks_handler.update_track(
            USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, TrackUpdateIn(name="x")
        )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.OrbitRepository.get_orbit_simple", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_delete_track_orbit_not_found(
    mock_get_orbit: AsyncMock, mock_perms: AsyncMock
) -> None:
    mock_get_orbit.return_value = None
    with pytest.raises(NotFoundError, match="Orbit not found"):
        await tracks_handler.delete_track(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID)


# ---- Coverage: entry read endpoints ----


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_create_entry_track_not_found(
    mock_get_track: AsyncMock, mock_perms: AsyncMock
) -> None:
    mock_get_track.return_value = None
    with pytest.raises(NotFoundError, match="Track not found"):
        await tracks_handler.create_entry(
            USER_ID,
            ORG_ID,
            ORBIT_ID,
            TRACK_ID,
            TrackEntryCreateIn(artifact_id=ARTIFACT_ID),
        )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@patch("luml.handlers.tracks.TrackEntryRepository.get_entry", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_get_entry(
    mock_get_entry: AsyncMock, mock_get_track: AsyncMock, mock_perms: AsyncMock
) -> None:
    mock_get_track.return_value = _make_track()
    expected = _make_entry()
    mock_get_entry.return_value = expected

    result = await tracks_handler.get_entry(
        USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, ENTRY_ID
    )
    assert result == expected


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@patch("luml.handlers.tracks.TrackEntryRepository.get_entry", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_get_entry_returns_none_when_missing(
    mock_get_entry: AsyncMock, mock_get_track: AsyncMock, mock_perms: AsyncMock
) -> None:
    mock_get_track.return_value = _make_track()
    mock_get_entry.return_value = None

    result = await tracks_handler.get_entry(
        USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, ENTRY_ID
    )
    assert result is None


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@patch("luml.handlers.tracks.TrackEntryRepository.get_entry", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_get_entry_wrong_track(
    mock_get_entry: AsyncMock, mock_get_track: AsyncMock, mock_perms: AsyncMock
) -> None:
    other_track = UUID("0199c337-09fe-7a01-9f5f-000000000005")
    mock_get_track.return_value = _make_track()
    mock_get_entry.return_value = _make_entry(track_id=other_track)

    with pytest.raises(NotFoundError, match="Entry not found"):
        await tracks_handler.get_entry(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, ENTRY_ID)


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_get_entry_track_not_found(
    mock_get_track: AsyncMock, mock_perms: AsyncMock
) -> None:
    mock_get_track.return_value = None
    with pytest.raises(NotFoundError, match="Track not found"):
        await tracks_handler.get_entry(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, ENTRY_ID)


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@patch("luml.handlers.tracks.TrackStageRepository.get_stage", new_callable=AsyncMock)
@patch(
    "luml.handlers.tracks.TrackEntryRepository.get_entry_by_stage",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_entry_by_stage(
    mock_by_stage: AsyncMock,
    mock_get_stage: AsyncMock,
    mock_get_track: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_track.return_value = _make_track()
    mock_get_stage.return_value = _make_stage()
    expected = _make_entry()
    mock_by_stage.return_value = expected

    result = await tracks_handler.get_entry_by_stage(
        USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, STAGE_ID
    )
    assert result == expected


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@patch("luml.handlers.tracks.TrackStageRepository.get_stage", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_get_entry_by_stage_stage_not_found(
    mock_get_stage: AsyncMock, mock_get_track: AsyncMock, mock_perms: AsyncMock
) -> None:
    mock_get_track.return_value = _make_track()
    mock_get_stage.return_value = None
    with pytest.raises(NotFoundError, match="Stage not found"):
        await tracks_handler.get_entry_by_stage(
            USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, STAGE_ID
        )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_get_entry_by_stage_track_not_found(
    mock_get_track: AsyncMock, mock_perms: AsyncMock
) -> None:
    mock_get_track.return_value = None
    with pytest.raises(NotFoundError, match="Track not found"):
        await tracks_handler.get_entry_by_stage(
            USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, STAGE_ID
        )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_list_entries_track_not_found(
    mock_get_track: AsyncMock, mock_perms: AsyncMock
) -> None:
    mock_get_track.return_value = None
    with pytest.raises(NotFoundError, match="Track not found"):
        await tracks_handler.list_entries(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID)


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@patch("luml.handlers.tracks.TrackEntryRepository.list_entries", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_list_entries_with_valid_cursor(
    mock_list: AsyncMock, mock_get_track: AsyncMock, mock_perms: AsyncMock
) -> None:
    mock_get_track.return_value = _make_track()
    mock_list.return_value = ([], None)
    cursor_str = encode_cursor(
        Cursor(
            id=ENTRY_ID,
            value=datetime.now(),
            sort_by=TrackEntrySortBy.CREATED_AT.value,
            order=SortOrder.DESC,
            scope_id=TRACK_ID,
        )
    )

    await tracks_handler.list_entries(
        USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, cursor_str=cursor_str
    )

    pagination = mock_list.await_args.kwargs["pagination"]
    assert pagination.cursor is not None


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackEntryRepository.get_entry", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_update_entry_not_found(
    mock_get_entry: AsyncMock, mock_perms: AsyncMock
) -> None:
    mock_get_entry.return_value = None
    with pytest.raises(NotFoundError, match="Entry not found"):
        await tracks_handler.update_entry(
            USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, ENTRY_ID, TrackEntryUpdateIn()
        )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackEntryRepository.get_entry", new_callable=AsyncMock)
@patch("luml.handlers.tracks.TrackEntryRepository.update_entry", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_update_entry_update_returns_none(
    mock_update: AsyncMock, mock_get_entry: AsyncMock, mock_perms: AsyncMock
) -> None:
    mock_get_entry.return_value = _make_entry()
    mock_update.return_value = None
    with pytest.raises(NotFoundError, match="Entry not found"):
        await tracks_handler.update_entry(
            USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, ENTRY_ID, TrackEntryUpdateIn()
        )


# ---- Coverage: stage handler guards ----


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_create_stage_track_not_found(
    mock_get_track: AsyncMock, mock_perms: AsyncMock
) -> None:
    mock_get_track.return_value = None
    with pytest.raises(NotFoundError, match="Track not found"):
        await tracks_handler.create_stage(
            USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, StageCreateIn(name="x")
        )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_list_stages_track_not_found(
    mock_get_track: AsyncMock, mock_perms: AsyncMock
) -> None:
    mock_get_track.return_value = None
    with pytest.raises(NotFoundError, match="Track not found"):
        await tracks_handler.list_stages(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID)


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_update_stage_track_not_found(
    mock_get_track: AsyncMock, mock_perms: AsyncMock
) -> None:
    mock_get_track.return_value = None
    with pytest.raises(NotFoundError, match="Track not found"):
        await tracks_handler.update_stage(
            USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, STAGE_ID, StageUpdateIn(name="x")
        )


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@patch("luml.handlers.tracks.TrackStageRepository.update_stage", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_update_stage_duplicate_name(
    mock_update: AsyncMock, mock_get_track: AsyncMock, mock_perms: AsyncMock
) -> None:
    mock_get_track.return_value = _make_track()
    mock_update.side_effect = IntegrityError("", {}, None)
    with pytest.raises(ApplicationError, match="already exists") as exc:
        await tracks_handler.update_stage(
            USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, STAGE_ID, StageUpdateIn(name="dup")
        )
    assert exc.value.status_code == 409


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_delete_stage_track_not_found(
    mock_get_track: AsyncMock, mock_perms: AsyncMock
) -> None:
    mock_get_track.return_value = None
    with pytest.raises(NotFoundError, match="Track not found"):
        await tracks_handler.delete_stage(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, STAGE_ID)


# ---- update_track stage sync ----


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.OrbitRepository.get_orbit_simple", new_callable=AsyncMock)
@patch("luml.handlers.tracks.TrackRepository.update_track", new_callable=AsyncMock)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_update_track_syncs_stages(
    mock_get_track: AsyncMock,
    mock_update: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = Mock(organization_id=ORG_ID)
    mock_update.return_value = _make_track()

    desired = [
        StageUpsertIn(id=STAGE_ID, name="Renamed"),
        StageUpsertIn(name="Brand New"),
    ]
    data = TrackUpdateIn(name="t", stages=desired)

    await tracks_handler.update_track(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, data)

    # Stages are synced inside update_track (one transaction), not separately.
    assert mock_update.await_args.kwargs["stages"] == desired
    # No redundant re-fetch: update_track already returns fresh stages.
    mock_get_track.assert_not_awaited()


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.OrbitRepository.get_orbit_simple", new_callable=AsyncMock)
@patch("luml.handlers.tracks.TrackRepository.update_track", new_callable=AsyncMock)
@patch("luml.handlers.tracks.TrackRepository.get_track", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_update_track_stages_none_skips_sync(
    mock_get_track: AsyncMock,
    mock_update: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = Mock(organization_id=ORG_ID)
    mock_update.return_value = _make_track()

    # stages omitted -> update_track called with stages=None, no re-fetch.
    await tracks_handler.update_track(
        USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, TrackUpdateIn(name="t")
    )

    assert mock_update.await_args.kwargs["stages"] is None
    mock_get_track.assert_not_awaited()


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch("luml.handlers.tracks.OrbitRepository.get_orbit_simple", new_callable=AsyncMock)
@patch("luml.handlers.tracks.TrackRepository.update_track", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_update_track_stage_sync_conflict_propagates(
    mock_update: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = Mock(organization_id=ORG_ID)
    # The atomic update_track raises the stage conflict directly.
    mock_update.side_effect = ApplicationError(
        "Cannot remove a stage that is assigned to a version.", 409
    )

    data = TrackUpdateIn(name="t", stages=[StageUpsertIn(name="x")])
    with pytest.raises(ApplicationError) as exc:
        await tracks_handler.update_track(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, data)
    assert exc.value.status_code == 409
