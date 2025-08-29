from typing import Any

from fastapi import APIRouter, Depends, Request, status

from dataforce_studio.handlers.model_artifacts import ModelArtifactHandler
from dataforce_studio.infra.dependencies import UserAuthentication
from dataforce_studio.infra.endpoint_responses import endpoint_responses
from dataforce_studio.schemas.model_artifacts import (
    CreateModelArtifactResponse,
    ModelArtifact,
    ModelArtifactIn,
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
    organization_id: int,
    orbit_id: int,
    collection_id: int,
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
    organization_id: int,
    orbit_id: int,
    collection_id: int,
    model_artifact_id: int,
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
    response_model=list[ModelArtifact],
)
async def get_model_artifact(
    request: Request,
    organization_id: int,
    orbit_id: int,
    collection_id: int,
) -> list[ModelArtifact]:
    return await model_artifacts_handler.get_collection_model_artifact(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
    )


@model_artifacts_router.get(
    "/{model_artifact_id}/download-url", responses=endpoint_responses
)
async def get_model_artifact_download_url(
    request: Request,
    organization_id: int,
    orbit_id: int,
    collection_id: int,
    model_artifact_id: int,
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
    organization_id: int,
    orbit_id: int,
    collection_id: int,
    model_artifact_id: int,
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
    organization_id: int,
    orbit_id: int,
    collection_id: int,
    model_artifact_id: int,
) -> None:
    await model_artifacts_handler.confirm_deletion(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
        model_artifact_id,
    )
