from fastapi import APIRouter, Depends, Request, status

from dataforce_studio.handlers.collections import CollectionHandler
from dataforce_studio.infra.dependencies import UserAuthentication
from dataforce_studio.infra.endpoint_responses import endpoint_responses
from dataforce_studio.schemas.ml_models import (
    Collection,
    CollectionCreateIn,
    CollectionUpdateIn,
)

collections_router = APIRouter(
    prefix="/{organization_id}/orbits/{orbit_id}/collections",
    dependencies=[Depends(UserAuthentication(["jwt", "api_key"]))],
    tags=["orbit-collections"],
)

collection_handler = CollectionHandler()


@collections_router.post(
    "",
    responses=endpoint_responses,
    response_model=Collection,
)
async def create_collection(
    request: Request,
    organization_id: int,
    orbit_id: int,
    collection: CollectionCreateIn,
) -> Collection:
    return await collection_handler.create_collection(
        request.user.id, organization_id, orbit_id, collection
    )


@collections_router.get(
    "",
    responses=endpoint_responses,
    response_model=list[Collection],
)
async def get_orbit_collections(
    request: Request, organization_id: int, orbit_id: int
) -> list[Collection]:
    return await collection_handler.get_orbit_collections(
        request.user.id, organization_id, orbit_id
    )


@collections_router.patch(
    "/{collection_id}",
    responses=endpoint_responses,
    response_model=Collection,
)
async def update_collection(
    request: Request,
    organization_id: int,
    orbit_id: int,
    collection_id: int,
    collection: CollectionUpdateIn,
) -> Collection:
    return await collection_handler.update_collection(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
        collection,
    )


@collections_router.delete(
    "/{collection_id}",
    responses=endpoint_responses,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_collection(
    request: Request, organization_id: int, orbit_id: int, collection_id: int
) -> None:
    await collection_handler.delete_collection(
        request.user.id, organization_id, orbit_id, collection_id
    )
