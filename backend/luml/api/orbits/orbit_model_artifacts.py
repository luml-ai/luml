from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from luml.handlers.model_artifacts import ModelArtifactHandler
from luml.infra.dependencies import UserAuthentication
from luml.infra.endpoint_responses import endpoint_responses
from luml.schemas.general import SortOrder
from luml.schemas.model_artifacts import (
    CreateModelArtifactResponse,
    ModelArtifact,
    ModelArtifactIn,
    ModelArtifactsList,
    ModelArtifactSortBy,
    ModelArtifactUpdateIn,
)

model_artifacts_router = APIRouter(
    prefix="/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/model_artifacts",
    dependencies=[Depends(UserAuthentication(["jwt", "api_key"]))],
    tags=["orbit-model_artifacts"],
)

model_artifacts_handler = ModelArtifactHandler()


@model_artifacts_router.post(
    "", responses=endpoint_responses, response_model=CreateModelArtifactResponse
)
async def create_model_artifact(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    collection_id: UUID,
    model_artifact: ModelArtifactIn,
) -> CreateModelArtifactResponse:
    return await model_artifacts_handler.create_model_artifact(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
        model_artifact,
    )


@model_artifacts_router.patch(
    "/{model_artifact_id}",
    responses=endpoint_responses,
    response_model=ModelArtifact,
)
async def update_model_artifact(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    collection_id: UUID,
    model_artifact_id: UUID,
    model_artifact: ModelArtifactUpdateIn,
) -> ModelArtifact:
    return await model_artifacts_handler.update_model_artifact(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
        model_artifact_id,
        model_artifact,
    )


@model_artifacts_router.get(
    "",
    responses=endpoint_responses,
    response_model=ModelArtifactsList,
)
async def get_model_artifacts(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    collection_id: UUID,
    cursor: str | None = None,
    limit: Annotated[int, Query(gt=0, le=100)] = 50,
    sort_by: Annotated[ModelArtifactSortBy, Query()] = ModelArtifactSortBy.CREATED_AT,
    order: Annotated[SortOrder, Query()] = SortOrder.DESC,
) -> ModelArtifactsList:
    return await model_artifacts_handler.get_collection_model_artifacts(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
        cursor,
        limit,
        sort_by,
        order,
    )


@model_artifacts_router.get(
    "/{model_artifact_id}",
    responses=endpoint_responses,
    response_model=ModelArtifact,
)
async def get_model_artifact_details(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    collection_id: UUID,
    model_artifact_id: UUID,
) -> ModelArtifact:
    return await model_artifacts_handler.get_model_artifact(
        request.user.id, organization_id, orbit_id, collection_id, model_artifact_id
    )


@model_artifacts_router.get(
    "/{model_artifact_id}/download-url", responses=endpoint_responses
)
async def get_model_artifact_download_url(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    collection_id: UUID,
    model_artifact_id: UUID,
) -> dict[str, Any]:
    url = await model_artifacts_handler.request_download_url(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
        model_artifact_id,
    )
    return {"url": url}


@model_artifacts_router.get(
    "/{model_artifact_id}/delete-url", responses=endpoint_responses
)
async def get_model_artifact_delete_url(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    collection_id: UUID,
    model_artifact_id: UUID,
) -> dict[str, Any]:
    url = await model_artifacts_handler.request_delete_url(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
        model_artifact_id,
    )
    return {"url": url}


@model_artifacts_router.delete(
    "/{model_artifact_id}",
    responses=endpoint_responses,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def confirm_model_artifact_delete(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    collection_id: UUID,
    model_artifact_id: UUID,
) -> None:
    await model_artifacts_handler.confirm_deletion(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
        model_artifact_id,
    )


@model_artifacts_router.delete(
    "/{model_artifact_id}/force",
    responses=endpoint_responses,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def force_delete_model_artifact(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    collection_id: UUID,
    model_artifact_id: UUID,
) -> None:
    await model_artifacts_handler.force_delete_model_artifact(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
        model_artifact_id,
    )
