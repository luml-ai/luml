from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from luml.handlers.artifacts import ArtifactHandler
from luml.infra.dependencies import UserAuthentication
from luml.infra.endpoint_responses import endpoint_responses
from luml.schemas.artifacts import (
    Artifact,
    ArtifactIn,
    ArtifactsList,
    ArtifactType,
    ArtifactUpdateIn,
    CreateArtifactResponse,
)
from luml.schemas.general import SortOrder

artifacts_router = APIRouter(
    prefix="/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/artifacts",
    dependencies=[Depends(UserAuthentication(["jwt", "api_key"]))],
    tags=["orbit-artifacts"],
)

artifacts_handler = ArtifactHandler()


@artifacts_router.post(
    "", responses=endpoint_responses, response_model=CreateArtifactResponse
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
    "/{artifact_id}",
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
    "",
    responses=endpoint_responses,
    response_model=ArtifactsList,
)
async def get_artifacts(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    collection_id: UUID,
    cursor: str | None = None,
    limit: Annotated[int, Query(gt=0, le=100)] = 50,
    sort_by: str = "created_at",
    order: SortOrder = SortOrder.DESC,
    types: Annotated[list[ArtifactType] | None, Query()] = None,  # noqa: A002
) -> ArtifactsList:
    return await artifacts_handler.get_collection_artifacts(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
        cursor,
        limit,
        sort_by,
        order,
        types,
    )


@artifacts_router.get(
    "/{artifact_id}",
    responses=endpoint_responses,
    response_model=Artifact,
)
async def get_artifact_details(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    collection_id: UUID,
    artifact_id: UUID,
) -> Artifact:
    return await artifacts_handler.get_artifact(
        request.user.id, organization_id, orbit_id, collection_id, artifact_id
    )


@artifacts_router.get("/{artifact_id}/download-url", responses=endpoint_responses)
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


@artifacts_router.get("/{artifact_id}/delete-url", responses=endpoint_responses)
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
    "/{artifact_id}",
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
    "/{artifact_id}/force",
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
