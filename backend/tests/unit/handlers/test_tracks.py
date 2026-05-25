from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from luml.handlers.tracks import TrackEntriesHandler, TracksHandler, TrackStagesHandler
from luml.infra.exceptions import ApplicationError, NotFoundError
from luml.schemas.permissions import Action, Resource
from luml.schemas.tracks import (
    TrackArtifactCreate,
    TrackArtifactUpdate,
    TrackCreate,
    TrackStageCreate,
    TrackStageUpdate,
    TrackUpdate,
)

tracks_handler = TracksHandler()
entries_handler = TrackEntriesHandler()
stages_handler = TrackStagesHandler()

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ORG_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
ORBIT_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")
TRACK_ID = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
ENTRY_ID = UUID("0199c337-09f5-7a01-9f5f-5f68db62cf71")
STAGE_ID = UUID("0199c337-09f6-7a01-9f5f-5f68db62cf72")
ARTIFACT_ID = UUID("0199c337-09f7-7a01-9f5f-5f68db62cf73")
COLLECTION_ID = UUID("0199c337-09f8-7a01-9f5f-5f68db62cf74")


def _make_track_orm(
    orbit_id: UUID = ORBIT_ID,
    name: str = "my-track",
    artifact_type: str = "model",
    next_version: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=TRACK_ID,
        orbit_id=orbit_id,
        name=name,
        artifact_type=artifact_type,
        description=None,
        tags=[],
        created_by=USER_ID,
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
        total_entries=0,
        next_version=next_version,
    )


def _make_entry_orm(
    track_id: UUID = TRACK_ID,
    version: int = 1,
    stage: SimpleNamespace | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=ENTRY_ID,
        track_id=track_id,
        artifact_id=ARTIFACT_ID,
        version=version,
        stage=stage,
        stage_id=stage.id if stage else None,
        created_at=datetime(2024, 1, 1),
        added_by=USER_ID,
    )


def _make_stage_orm(
    track_id: UUID = TRACK_ID, name: str = "Production"
) -> SimpleNamespace:
    return SimpleNamespace(
        id=STAGE_ID,
        track_id=track_id,
        name=name,
        created_at=datetime(2024, 1, 1),
    )


# --- TracksHandler tests ---


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
@patch(
    "luml.handlers.tracks.TrackRepository.list_tracks",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_track_happy_path(
    mock_list_tracks: AsyncMock,
    mock_create_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_list_tracks.return_value = []
    track_orm = _make_track_orm()
    mock_create_track.return_value = track_orm

    data = TrackCreate(name="my-track", artifact_type="model")
    result = await tracks_handler.create_track(USER_ID, ORG_ID, ORBIT_ID, data)

    assert result.name == "my-track"
    mock_check_perms.assert_awaited_once_with(
        ORG_ID, USER_ID, Resource.TRACK, Action.CREATE, ORBIT_ID
    )
    mock_create_track.assert_awaited_once_with(data, ORBIT_ID, USER_ID)


@patch(
    "luml.handlers.permissions.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.list_tracks",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_track_duplicate_name(
    mock_list_tracks: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_list_tracks.return_value = [_make_track_orm(name="my-track")]

    data = TrackCreate(name="my-track", artifact_type="model")
    with pytest.raises(ApplicationError, match="already exists") as exc_info:
        await tracks_handler.create_track(USER_ID, ORG_ID, ORBIT_ID, data)
    assert exc_info.value.status_code == 409


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
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = None

    data = TrackCreate(name="my-track", artifact_type="model")
    with pytest.raises(NotFoundError, match="Orbit not found"):
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
    "luml.handlers.tracks.TrackRepository.list_tracks",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_tracks(
    mock_list_tracks: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_list_tracks.return_value = [_make_track_orm()]

    result = await tracks_handler.list_tracks(USER_ID, ORG_ID, ORBIT_ID)

    assert len(result.items) == 1
    mock_check_perms.assert_awaited_once_with(
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
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_track_happy_path(
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_get_track.return_value = _make_track_orm()

    result = await tracks_handler.get_track(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID)

    assert result.id == TRACK_ID
    mock_check_perms.assert_awaited_once_with(
        ORG_ID, USER_ID, Resource.TRACK, Action.READ, ORBIT_ID
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
async def test_get_track_not_found(
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_get_track.return_value = None

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
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.list_tracks",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.update_track",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_track_happy_path(
    mock_update: AsyncMock,
    mock_list_tracks: AsyncMock,
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    track = _make_track_orm()
    mock_get_track.return_value = track
    mock_list_tracks.return_value = [track]
    updated_track = _make_track_orm(name="new-name")
    mock_update.return_value = updated_track

    data = TrackUpdate(name="new-name")
    result = await tracks_handler.update_track(
        USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, data
    )

    assert result.name == "new-name"
    mock_check_perms.assert_awaited_once_with(
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
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.delete_track",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_track_happy_path(
    mock_delete: AsyncMock,
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    track = _make_track_orm()
    mock_get_track.return_value = track

    await tracks_handler.delete_track(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID)

    mock_delete.assert_awaited_once_with(track)
    mock_check_perms.assert_awaited_once_with(
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
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_get_track.return_value = None

    with pytest.raises(NotFoundError, match="Track not found"):
        await tracks_handler.delete_track(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID)


# --- TrackEntriesHandler tests ---


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
    "luml.handlers.tracks.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.list_entries",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.add_entry",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_add_entry_happy_path(
    mock_add_entry: AsyncMock,
    mock_list_entries: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_artifact: AsyncMock,
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    track = _make_track_orm(next_version=3)
    mock_get_track.return_value = track
    mock_get_artifact.return_value = SimpleNamespace(
        collection_id=COLLECTION_ID, type="model"
    )
    mock_get_collection.return_value = SimpleNamespace(orbit_id=ORBIT_ID)
    mock_list_entries.return_value = []
    entry = _make_entry_orm(version=3)
    mock_add_entry.return_value = entry

    data = TrackArtifactCreate(artifact_id=ARTIFACT_ID)
    result = await entries_handler.add_entry(
        USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, data
    )

    assert result.version == 3
    mock_check_perms.assert_awaited_once_with(
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
async def test_add_entry_wrong_artifact_type(
    mock_get_collection: AsyncMock,
    mock_get_artifact: AsyncMock,
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_get_track.return_value = _make_track_orm(artifact_type="model")
    mock_get_artifact.return_value = SimpleNamespace(
        collection_id=COLLECTION_ID, type="dataset"
    )
    mock_get_collection.return_value = SimpleNamespace(orbit_id=ORBIT_ID)

    data = TrackArtifactCreate(artifact_id=ARTIFACT_ID)
    with pytest.raises(ApplicationError, match="does not match") as exc_info:
        await entries_handler.add_entry(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, data)
    assert exc_info.value.status_code == 422


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
    "luml.handlers.tracks.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_add_entry_artifact_from_different_orbit(
    mock_get_collection: AsyncMock,
    mock_get_artifact: AsyncMock,
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_get_track.return_value = _make_track_orm()
    mock_get_artifact.return_value = SimpleNamespace(
        collection_id=COLLECTION_ID, type="model"
    )
    other_orbit_id = UUID("0199c337-09f9-7a01-9f5f-5f68db62cf75")
    mock_get_collection.return_value = SimpleNamespace(orbit_id=other_orbit_id)

    data = TrackArtifactCreate(artifact_id=ARTIFACT_ID)
    with pytest.raises(ApplicationError, match="same orbit") as exc_info:
        await entries_handler.add_entry(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, data)
    assert exc_info.value.status_code == 422


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
    "luml.handlers.tracks.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.list_entries",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_add_entry_duplicate_artifact(
    mock_list_entries: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_artifact: AsyncMock,
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_get_track.return_value = _make_track_orm()
    mock_get_artifact.return_value = SimpleNamespace(
        collection_id=COLLECTION_ID, type="model"
    )
    mock_get_collection.return_value = SimpleNamespace(orbit_id=ORBIT_ID)
    mock_list_entries.return_value = [SimpleNamespace(artifact_id=ARTIFACT_ID)]

    data = TrackArtifactCreate(artifact_id=ARTIFACT_ID)
    with pytest.raises(ApplicationError, match="already an entry") as exc_info:
        await entries_handler.add_entry(USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, data)
    assert exc_info.value.status_code == 409


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
    "luml.handlers.tracks.TrackRepository.get_entry",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_stage",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_entry_holding_stage",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.update_entry_stage",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_patch_entry_assign_free_stage(
    mock_update_stage: AsyncMock,
    mock_get_holder: AsyncMock,
    mock_get_stage: AsyncMock,
    mock_get_entry: AsyncMock,
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_get_track.return_value = _make_track_orm()
    entry = _make_entry_orm()
    mock_get_entry.return_value = entry
    stage = _make_stage_orm()
    mock_get_stage.return_value = stage
    mock_get_holder.return_value = None
    updated_entry = _make_entry_orm(stage=stage)
    mock_update_stage.return_value = updated_entry

    data = TrackArtifactUpdate(stage_id=STAGE_ID)
    result = await entries_handler.patch_entry(
        USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, ENTRY_ID, data
    )

    assert result.entry.stage is not None
    assert result.entry.stage.name == "Production"
    mock_check_perms.assert_awaited_once_with(
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
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_entry",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_stage",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_entry_holding_stage",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_patch_entry_stage_taken_no_force(
    mock_get_holder: AsyncMock,
    mock_get_stage: AsyncMock,
    mock_get_entry: AsyncMock,
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_get_track.return_value = _make_track_orm()
    entry = _make_entry_orm()
    mock_get_entry.return_value = entry
    stage = _make_stage_orm()
    mock_get_stage.return_value = stage
    holder_id = UUID("0199c337-09fa-7a01-9f5f-5f68db62cf76")
    mock_get_holder.return_value = SimpleNamespace(
        id=holder_id, version=1, stage_id=STAGE_ID
    )

    data = TrackArtifactUpdate(stage_id=STAGE_ID)
    with pytest.raises(ApplicationError) as exc_info:
        await entries_handler.patch_entry(
            USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, ENTRY_ID, data, force=False
        )
    assert exc_info.value.status_code == 409


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
    "luml.handlers.tracks.TrackRepository.get_entry",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_stage",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_entry_holding_stage",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.update_entry_stage",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_patch_entry_stage_taken_with_force(
    mock_update_stage: AsyncMock,
    mock_get_holder: AsyncMock,
    mock_get_stage: AsyncMock,
    mock_get_entry: AsyncMock,
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_get_track.return_value = _make_track_orm()
    entry = _make_entry_orm()
    mock_get_entry.return_value = entry
    stage = _make_stage_orm()
    mock_get_stage.return_value = stage
    holder_id = UUID("0199c337-09fa-7a01-9f5f-5f68db62cf76")
    holder = SimpleNamespace(id=holder_id, version=1, stage_id=STAGE_ID)
    mock_get_holder.return_value = holder
    updated_entry = _make_entry_orm(stage=stage)
    mock_update_stage.side_effect = [SimpleNamespace(), updated_entry]

    data = TrackArtifactUpdate(stage_id=STAGE_ID)
    result = await entries_handler.patch_entry(
        USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, ENTRY_ID, data, force=True
    )

    assert result.entry.stage is not None
    assert mock_update_stage.await_count == 2
    mock_update_stage.assert_any_await(holder, None)


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
    "luml.handlers.tracks.TrackRepository.get_entry",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_stage",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_patch_entry_stage_from_wrong_track(
    mock_get_stage: AsyncMock,
    mock_get_entry: AsyncMock,
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_get_track.return_value = _make_track_orm()
    mock_get_entry.return_value = _make_entry_orm()
    other_track_id = UUID("0199c337-09fb-7a01-9f5f-5f68db62cf77")
    mock_get_stage.return_value = _make_stage_orm(track_id=other_track_id)

    data = TrackArtifactUpdate(stage_id=STAGE_ID)
    with pytest.raises(ApplicationError, match="does not belong") as exc_info:
        await entries_handler.patch_entry(
            USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, ENTRY_ID, data
        )
    assert exc_info.value.status_code == 422


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
    "luml.handlers.tracks.TrackRepository.get_entry",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.update_entry_stage",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_patch_entry_remove_stage(
    mock_update_stage: AsyncMock,
    mock_get_entry: AsyncMock,
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_get_track.return_value = _make_track_orm()
    stage = _make_stage_orm()
    entry = _make_entry_orm(stage=stage)
    mock_get_entry.return_value = entry
    updated_entry = _make_entry_orm(stage=None)
    mock_update_stage.return_value = updated_entry

    data = TrackArtifactUpdate(stage_id=None)
    result = await entries_handler.patch_entry(
        USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, ENTRY_ID, data
    )

    assert result.entry.stage is None
    mock_update_stage.assert_awaited_once_with(entry, None)


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
    "luml.handlers.tracks.TrackRepository.get_entry",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.delete_entry",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_entry_happy_path(
    mock_delete: AsyncMock,
    mock_get_entry: AsyncMock,
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_get_track.return_value = _make_track_orm()
    entry = _make_entry_orm()
    mock_get_entry.return_value = entry

    await entries_handler.delete_entry(
        USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, ENTRY_ID
    )

    mock_delete.assert_awaited_once_with(entry)
    mock_check_perms.assert_awaited_once_with(
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
    "luml.handlers.tracks.TrackRepository.list_entries_for_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_entries_for_artifact(
    mock_list: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_list.return_value = [_make_entry_orm()]

    result = await entries_handler.list_entries_for_artifact(
        USER_ID, ORG_ID, ORBIT_ID, ARTIFACT_ID
    )

    assert len(result.items) == 1
    mock_list.assert_awaited_once_with(ORBIT_ID, ARTIFACT_ID)


# --- TrackStagesHandler tests ---


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
    "luml.handlers.tracks.TrackRepository.list_stages",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.create_stage",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_stage_happy_path(
    mock_create: AsyncMock,
    mock_list_stages: AsyncMock,
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_get_track.return_value = _make_track_orm()
    mock_list_stages.return_value = []
    stage = _make_stage_orm(name="QA")
    mock_create.return_value = stage

    data = TrackStageCreate(name="QA")
    result = await stages_handler.create_stage(
        USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, data
    )

    assert result.name == "QA"
    mock_check_perms.assert_awaited_once_with(
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
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.list_stages",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_stage_duplicate_name(
    mock_list_stages: AsyncMock,
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_get_track.return_value = _make_track_orm()
    mock_list_stages.return_value = [_make_stage_orm(name="Production")]

    data = TrackStageCreate(name="Production")
    with pytest.raises(ApplicationError, match="already exists") as exc_info:
        await stages_handler.create_stage(
            USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, data
        )
    assert exc_info.value.status_code == 409


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
    "luml.handlers.tracks.TrackRepository.get_stage",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.list_stages",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.update_stage",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_stage_happy_path(
    mock_update: AsyncMock,
    mock_list_stages: AsyncMock,
    mock_get_stage: AsyncMock,
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_get_track.return_value = _make_track_orm()
    stage = _make_stage_orm(name="Staging")
    mock_get_stage.return_value = stage
    mock_list_stages.return_value = [stage]
    updated = _make_stage_orm(name="QA")
    mock_update.return_value = updated

    data = TrackStageUpdate(name="QA")
    result = await stages_handler.update_stage(
        USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, STAGE_ID, data
    )

    assert result.name == "QA"
    mock_check_perms.assert_awaited_once_with(
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
    "luml.handlers.tracks.TrackRepository.get_track",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_stage",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_entry_holding_stage",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.delete_stage",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_stage_not_in_use(
    mock_delete: AsyncMock,
    mock_get_holder: AsyncMock,
    mock_get_stage: AsyncMock,
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_get_track.return_value = _make_track_orm()
    stage = _make_stage_orm()
    mock_get_stage.return_value = stage
    mock_get_holder.return_value = None

    await stages_handler.delete_stage(
        USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, STAGE_ID
    )

    mock_delete.assert_awaited_once_with(stage)
    mock_check_perms.assert_awaited_once_with(
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
@patch(
    "luml.handlers.tracks.TrackRepository.get_stage",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_entry_holding_stage",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_stage_in_use_no_force(
    mock_get_holder: AsyncMock,
    mock_get_stage: AsyncMock,
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_get_track.return_value = _make_track_orm()
    mock_get_stage.return_value = _make_stage_orm()
    mock_get_holder.return_value = _make_entry_orm()

    with pytest.raises(ApplicationError, match="assigned to entries") as exc_info:
        await stages_handler.delete_stage(
            USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, STAGE_ID, force=False
        )
    assert exc_info.value.status_code == 409


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
    "luml.handlers.tracks.TrackRepository.get_stage",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.get_entry_holding_stage",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.clear_stage_from_entries",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.tracks.TrackRepository.delete_stage",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_stage_in_use_with_force(
    mock_delete: AsyncMock,
    mock_clear: AsyncMock,
    mock_get_holder: AsyncMock,
    mock_get_stage: AsyncMock,
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_get_track.return_value = _make_track_orm()
    stage = _make_stage_orm()
    mock_get_stage.return_value = stage
    mock_get_holder.return_value = _make_entry_orm()

    await stages_handler.delete_stage(
        USER_ID, ORG_ID, ORBIT_ID, TRACK_ID, STAGE_ID, force=True
    )

    mock_clear.assert_awaited_once_with(STAGE_ID)
    mock_delete.assert_awaited_once_with(stage)


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
    "luml.handlers.tracks.TrackRepository.list_stages",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_stages(
    mock_list_stages: AsyncMock,
    mock_get_track: AsyncMock,
    mock_get_orbit: AsyncMock,
    mock_check_perms: AsyncMock,
) -> None:
    mock_get_orbit.return_value = SimpleNamespace(organization_id=ORG_ID)
    mock_get_track.return_value = _make_track_orm()
    mock_list_stages.return_value = [
        _make_stage_orm(name="Production"),
        _make_stage_orm(name="Staging"),
    ]

    result = await stages_handler.list_stages(
        USER_ID, ORG_ID, ORBIT_ID, TRACK_ID
    )

    assert len(result.items) == 2
    mock_check_perms.assert_awaited_once_with(
        ORG_ID, USER_ID, Resource.TRACK, Action.LIST, ORBIT_ID
    )
