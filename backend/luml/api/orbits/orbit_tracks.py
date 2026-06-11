from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from luml.handlers.tracks import TracksHandler
from luml.infra.dependencies import UserAuthentication
from luml.infra.endpoint_responses import endpoint_responses
from luml.schemas.general import SortOrder
from luml.schemas.tracks import (
    Stage,
    Track,
    TrackCreateIn,
    TrackEntriesDeleteIn,
    TrackEntriesList,
    TrackEntry,
    TrackEntryCreateIn,
    TrackEntrySortBy,
    TrackEntryUpdateIn,
    TracksList,
    TrackSortBy,
    TrackUpdateIn,
)

tracks_router = APIRouter(
    prefix="/{organization_id}/orbits/{orbit_id}/tracks",
    dependencies=[Depends(UserAuthentication(["jwt", "api_key"]))],
    tags=["orbit-tracks"],
)


tracks_router_entries = APIRouter(
    prefix="/{organization_id}/orbits/{orbit_id}/tracks/{track_id}/entries",
    dependencies=[Depends(UserAuthentication(["jwt", "api_key"]))],
    tags=["orbit-tracks-entries"],
)

tracks_handler = TracksHandler()


@tracks_router.post(
    "",
    responses=endpoint_responses,
    response_model=Track,
)
async def create_track(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    track: TrackCreateIn,
) -> Track:
    return await tracks_handler.create_track(
        request.user.id, organization_id, orbit_id, track
    )


@tracks_router.get(
    "",
    responses=endpoint_responses,
    response_model=TracksList,
)
async def list_tracks(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    cursor: str | None = None,
    limit: Annotated[int, Query(gt=0, le=100)] = 50,
    sort_by: Annotated[TrackSortBy, Query()] = TrackSortBy.CREATED_AT,
    order: Annotated[SortOrder, Query()] = SortOrder.DESC,
    search: str | None = None,
    types: Annotated[list[str] | None, Query()] = None,
) -> TracksList:
    return await tracks_handler.list_tracks(
        request.user.id,
        organization_id,
        orbit_id,
        cursor,
        limit,
        sort_by,
        order,
        search,
        types,
    )


@tracks_router.get(
    "/{track_id}",
    responses=endpoint_responses,
    response_model=Track,
)
async def get_track(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    track_id: UUID,
) -> Track:
    return await tracks_handler.get_track(
        request.user.id, organization_id, orbit_id, track_id
    )


@tracks_router.patch(
    "/{track_id}",
    responses=endpoint_responses,
    response_model=Track,
)
async def update_track(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    track_id: UUID,
    track: TrackUpdateIn,
) -> Track:
    return await tracks_handler.update_track(
        request.user.id, organization_id, orbit_id, track_id, track
    )


@tracks_router.delete(
    "/{track_id}",
    responses=endpoint_responses,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_track(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    track_id: UUID,
) -> None:
    await tracks_handler.delete_track(
        request.user.id, organization_id, orbit_id, track_id
    )


@tracks_router.get(
    "/{track_id}/stages",
    responses=endpoint_responses,
    response_model=list[Stage],
)
async def list_stages(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    track_id: UUID,
) -> list[Stage]:
    return await tracks_handler.list_stages(
        request.user.id, organization_id, orbit_id, track_id
    )


# --- Entries ---


@tracks_router_entries.post(
    "",
    responses=endpoint_responses,
    response_model=TrackEntry,
)
async def create_entry(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    track_id: UUID,
    entry: TrackEntryCreateIn,
) -> TrackEntry:
    return await tracks_handler.create_entry(
        request.user.id, organization_id, orbit_id, track_id, entry
    )


@tracks_router_entries.get(
    "/{entry_id}",
    responses=endpoint_responses,
    response_model=TrackEntry,
)
async def get_entry(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    track_id: UUID,
    entry_id: UUID,
) -> TrackEntry | None:
    return await tracks_handler.get_entry(
        request.user.id, organization_id, orbit_id, track_id, entry_id
    )


@tracks_router_entries.get(
    "/by-stage",
    responses=endpoint_responses,
    response_model=TrackEntry,
)
async def get_entry_by_stage(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    track_id: UUID,
    stage_id: UUID,
) -> TrackEntry | None:
    return await tracks_handler.get_entry_by_stage(
        request.user.id, organization_id, orbit_id, track_id, stage_id
    )


@tracks_router_entries.get(
    "",
    responses=endpoint_responses,
    response_model=TrackEntriesList,
)
async def list_entries(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    track_id: UUID,
    cursor: str | None = None,
    limit: Annotated[int, Query(gt=0, le=100)] = 50,
    sort_by: Annotated[TrackEntrySortBy, Query()] = TrackEntrySortBy.CREATED_AT,
    order: Annotated[SortOrder, Query()] = SortOrder.DESC,
    stage: Annotated[UUID | None, Query()] = None,
) -> TrackEntriesList:
    return await tracks_handler.list_entries(
        request.user.id,
        organization_id,
        orbit_id,
        track_id,
        cursor,
        limit,
        sort_by,
        order,
        stage_id=stage,
    )


@tracks_router_entries.patch(
    "/{entry_id}",
    responses=endpoint_responses,
    response_model=TrackEntry,
)
async def update_entry(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    track_id: UUID,
    entry_id: UUID,
    entry: TrackEntryUpdateIn,
    force: bool = False,
) -> TrackEntry:
    return await tracks_handler.update_entry(
        request.user.id,
        organization_id,
        orbit_id,
        track_id,
        entry_id,
        entry,
        force,
    )


@tracks_router_entries.delete(
    "/{entry_id}",
    responses=endpoint_responses,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_entry(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    track_id: UUID,
    entry_id: UUID,
) -> None:
    await tracks_handler.delete_entry(
        request.user.id, organization_id, orbit_id, track_id, entry_id
    )


@tracks_router_entries.delete(
    "",
    responses=endpoint_responses,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_entries(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    track_id: UUID,
    payload: TrackEntriesDeleteIn,
) -> None:
    await tracks_handler.delete_entries(
        request.user.id, organization_id, orbit_id, track_id, payload.entry_ids
    )
