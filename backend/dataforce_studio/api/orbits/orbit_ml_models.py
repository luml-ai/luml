from fastapi import APIRouter, Depends, Request, status

from dataforce_studio.handlers.ml_models import MLModelHandler
from dataforce_studio.infra.dependencies import UserAuthentication
from dataforce_studio.infra.endpoint_responses import endpoint_responses
from dataforce_studio.schemas.ml_models import (
    CreateMLModelResponse,
    MLModel,
    MLModelIn,
    MLModelUpdateIn,
)

ml_models_router = APIRouter(
    prefix="/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/ml-models",
    dependencies=[Depends(UserAuthentication(["jwt", "api_key"]))],
    tags=["orbit-ml-models"],
)

ml_model_handler = MLModelHandler()


@ml_models_router.post(
    "", responses=endpoint_responses, response_model=CreateMLModelResponse
)
async def create_ml_model(
    request: Request,
    organization_id: int,
    orbit_id: int,
    collection_id: int,
    model: MLModelIn,
) -> dict:
    created_model, url = await ml_model_handler.create_ml_model(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
        model,
    )
    return {"model": created_model, "url": url}


@ml_models_router.patch(
    "/{model_id}",
    responses=endpoint_responses,
    response_model=MLModel,
)
async def update_ml_model(
    request: Request,
    organization_id: int,
    orbit_id: int,
    collection_id: int,
    model_id: int,
    model: MLModelUpdateIn,
) -> MLModel:
    return await ml_model_handler.update_model(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
        model_id,
        model,
    )


@ml_models_router.get(
    "",
    responses=endpoint_responses,
    response_model=list[MLModel],
)
async def get_ml_models(
    request: Request,
    organization_id: int,
    orbit_id: int,
    collection_id: int,
) -> list[MLModel]:
    return await ml_model_handler.get_collection_models(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
    )


@ml_models_router.get("/{model_id}/download-url", responses=endpoint_responses)
async def get_ml_model_download_url(
    request: Request,
    organization_id: int,
    orbit_id: int,
    collection_id: int,
    model_id: int,
) -> dict:
    url = await ml_model_handler.request_download_url(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
        model_id,
    )
    return {"url": url}


@ml_models_router.get("/{model_id}/delete-url", responses=endpoint_responses)
async def get_ml_model_delete_url(
    request: Request,
    organization_id: int,
    orbit_id: int,
    collection_id: int,
    model_id: int,
) -> dict:
    url = await ml_model_handler.request_delete_url(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
        model_id,
    )
    return {"url": url}


@ml_models_router.delete(
    "/{model_id}",
    responses=endpoint_responses,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def confirm_ml_model_delete(
    request: Request,
    organization_id: int,
    orbit_id: int,
    collection_id: int,
    model_id: int,
) -> None:
    await ml_model_handler.confirm_deletion(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
        model_id,
    )
