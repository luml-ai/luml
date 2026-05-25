from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from luml.handlers.tracks import TrackEntriesHandler, TracksHandler, TrackStagesHandler
from luml.infra.dependencies import UserAuthentication
from luml.infra.endpoint_responses import endpoint_responses
from luml.schemas.tracks import (
    Track,
    TrackArtifact,
    TrackArtifactCreate,
    TrackArtifactUpdate,
    TrackArtifactUpdateResponse,
    TrackCreate,
    TrackEntriesList,
    TracksList,
    TrackStage,
    TrackStageCreate,
    TrackStagesList,
    TrackStageUpdate,
    TrackUpdate,
)

tracks_router = APIRouter(
    prefix="/{organization_id}/orbits/{orbit_id}",
    dependencies=[Depends(UserAuthentication(["jwt", "api_key"]))],
    tags=["orbit-tracks"],
)

tracks_handler = TracksHandler()
entries_handler = TrackEntriesHandler()
stages_handler = TrackStagesHandler()


# --- Tracks ---


@tracks_router.post(
    "/tracks",
    responses=endpoint_responses,
    response_model=Track,
)
async def create_track(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    body: TrackCreate,
) -> Track:
    return await tracks_handler.create_track(
        request.user.id, organization_id, orbit_id, body
    )


@tracks_router.get(
    "/tracks",
    responses=endpoint_responses,
    response_model=TracksList,
)
async def list_tracks(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
) -> TracksList:
    return await tracks_handler.list_tracks(
        request.user.id, organization_id, orbit_id
    )


@tracks_router.get(
    "/tracks/{track_id}",
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
    "/tracks/{track_id}",
    responses=endpoint_responses,
    response_model=Track,
)
async def update_track(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    track_id: UUID,
    body: TrackUpdate,
) -> Track:
    return await tracks_handler.update_track(
        request.user.id, organization_id, orbit_id, track_id, body
    )


@tracks_router.delete(
    "/tracks/{track_id}",
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


# --- Entries ---


@tracks_router.post(
    "/tracks/{track_id}/entries",
    responses=endpoint_responses,
    response_model=TrackArtifact,
)
async def add_entry(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    track_id: UUID,
    body: TrackArtifactCreate,
) -> TrackArtifact:
    return await entries_handler.add_entry(
        request.user.id, organization_id, orbit_id, track_id, body
    )


@tracks_router.get(
    "/tracks/{track_id}/entries",
    responses=endpoint_responses,
    response_model=TrackEntriesList,
)
async def list_entries(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    track_id: UUID,
    stage: str | None = None,
    cursor: str | None = None,
    page_size: Annotated[int, Query(gt=0, le=100)] = 20,
) -> TrackEntriesList:
    return await entries_handler.list_entries(
        request.user.id,
        organization_id,
        orbit_id,
        track_id,
        stage,
        cursor,
        page_size,
    )


@tracks_router.patch(
    "/tracks/{track_id}/entries/{entry_id}",
    responses=endpoint_responses,
    response_model=TrackArtifactUpdateResponse,
)
async def patch_entry(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    track_id: UUID,
    entry_id: UUID,
    body: TrackArtifactUpdate,
    force: bool = False,
) -> TrackArtifactUpdateResponse:
    return await entries_handler.patch_entry(
        request.user.id,
        organization_id,
        orbit_id,
        track_id,
        entry_id,
        body,
        force,
    )


@tracks_router.delete(
    "/tracks/{track_id}/entries/{entry_id}",
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
    await entries_handler.delete_entry(
        request.user.id, organization_id, orbit_id, track_id, entry_id
    )


# --- Artifact track membership ---


@tracks_router.get(
    "/artifacts/{artifact_id}/track-entries",
    responses=endpoint_responses,
    response_model=TrackEntriesList,
)
async def list_artifact_track_entries(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    artifact_id: UUID,
) -> TrackEntriesList:
    return await entries_handler.list_entries_for_artifact(
        request.user.id, organization_id, orbit_id, artifact_id
    )


# --- Stages ---


@tracks_router.post(
    "/tracks/{track_id}/stages",
    responses=endpoint_responses,
    response_model=TrackStage,
)
async def create_stage(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    track_id: UUID,
    body: TrackStageCreate,
) -> TrackStage:
    return await stages_handler.create_stage(
        request.user.id, organization_id, orbit_id, track_id, body
    )


@tracks_router.get(
    "/tracks/{track_id}/stages",
    responses=endpoint_responses,
    response_model=TrackStagesList,
)
async def list_stages(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    track_id: UUID,
) -> TrackStagesList:
    return await stages_handler.list_stages(
        request.user.id, organization_id, orbit_id, track_id
    )


@tracks_router.patch(
    "/tracks/{track_id}/stages/{stage_id}",
    responses=endpoint_responses,
    response_model=TrackStage,
)
async def update_stage(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    track_id: UUID,
    stage_id: UUID,
    body: TrackStageUpdate,
) -> TrackStage:
    return await stages_handler.update_stage(
        request.user.id, organization_id, orbit_id, track_id, stage_id, body
    )


@tracks_router.delete(
    "/tracks/{track_id}/stages/{stage_id}",
    responses=endpoint_responses,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_stage(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    track_id: UUID,
    stage_id: UUID,
    force: bool = False,
) -> None:
    await stages_handler.delete_stage(
        request.user.id, organization_id, orbit_id, track_id, stage_id, force
    )
