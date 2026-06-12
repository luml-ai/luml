from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from luml.handlers.artifacts import ArtifactHandler
from luml.infra.dependencies import UserAuthentication
from luml.infra.endpoint_responses import endpoint_responses
from luml.schemas.artifacts import (
    Artifact,
    ArtifactDetails,
    ArtifactIn,
    ArtifactsList,
    ArtifactType,
    ArtifactUpdateIn,
    CreateArtifactResponse,
)
from luml.schemas.general import SortOrder

artifacts_router = APIRouter(
    prefix="/{organization_id}/orbits/{orbit_id}",
    dependencies=[Depends(UserAuthentication(["jwt", "api_key"]))],
    tags=["orbit-artifacts"],
)

artifacts_handler = ArtifactHandler()


@artifacts_router.post(
    "/collections/{collection_id}/artifacts",
    responses=endpoint_responses,
    response_model=CreateArtifactResponse,
)
async def create_artifact(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    collection_id: UUID,
    artifact: ArtifactIn,
) -> CreateArtifactResponse:
    return await artifacts_handler.create_artifact(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
        artifact,
    )


@artifacts_router.patch(
    "/collections/{collection_id}/artifacts/{artifact_id}",
    responses=endpoint_responses,
    response_model=Artifact,
)
async def update_artifact(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    collection_id: UUID,
    artifact_id: UUID,
    artifact: ArtifactUpdateIn,
) -> Artifact:
    return await artifacts_handler.update_artifact(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
        artifact_id,
        artifact,
    )


@artifacts_router.get(
    "/artifacts",
    responses=endpoint_responses,
    response_model=ArtifactsList,
)
async def get_orbit_artifacts(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    types: Annotated[list[ArtifactType] | None, Query()] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(gt=0, le=100)] = 50,
    sort_by: str = "created_at",
    order: SortOrder = SortOrder.DESC,
    collection_ids: Annotated[list[UUID] | None, Query()] = None,
    search: str | None = None,
) -> ArtifactsList:
    return await artifacts_handler.get_collection_artifacts(
        user_id=request.user.id,
        organization_id=organization_id,
        orbit_id=orbit_id,
        artifact_types=types,
        cursor_str=cursor,
        limit=limit,
        sort_by=sort_by,
        order=order,
        collection_ids=collection_ids,
        search=search,
    )


@artifacts_router.get(
    "/collections/{collection_id}/artifacts/{artifact_id}",
    responses=endpoint_responses,
    response_model=ArtifactDetails,
)
async def get_artifact_details(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    collection_id: UUID,
    artifact_id: UUID,
) -> ArtifactDetails:
    return await artifacts_handler.get_artifact(
        request.user.id, organization_id, orbit_id, collection_id, artifact_id
    )


@artifacts_router.get(
    "/collections/{collection_id}/artifacts/{artifact_id}/download-url",
    responses=endpoint_responses,
)
async def get_artifact_download_url(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    collection_id: UUID,
    artifact_id: UUID,
) -> dict[str, Any]:
    url = await artifacts_handler.request_download_url(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
        artifact_id,
    )
    return {"url": url}


@artifacts_router.get(
    "/collections/{collection_id}/artifacts/{artifact_id}/delete-url",
    responses=endpoint_responses,
)
async def get_artifact_delete_url(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    collection_id: UUID,
    artifact_id: UUID,
) -> dict[str, Any]:
    url = await artifacts_handler.request_delete_url(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
        artifact_id,
    )
    return {"url": url}


@artifacts_router.delete(
    "/collections/{collection_id}/artifacts/{artifact_id}",
    responses=endpoint_responses,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def confirm_artifact_delete(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    collection_id: UUID,
    artifact_id: UUID,
) -> None:
    await artifacts_handler.confirm_deletion(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
        artifact_id,
    )


@artifacts_router.delete(
    "/collections/{collection_id}/artifacts/{artifact_id}/force",
    responses=endpoint_responses,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def force_delete_artifact(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    collection_id: UUID,
    artifact_id: UUID,
) -> None:
    await artifacts_handler.force_delete_artifact(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
        artifact_id,
    )
