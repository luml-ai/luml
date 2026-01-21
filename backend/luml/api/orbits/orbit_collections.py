from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from luml.handlers.collections import CollectionHandler
from luml.infra.dependencies import UserAuthentication
from luml.infra.endpoint_responses import endpoint_responses
from luml.schemas.general import SortOrder
from luml.schemas.model_artifacts import (
    Collection,
    CollectionCreateIn,
    CollectionDetails,
    CollectionsList,
    CollectionSortBy,
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
    organization_id: UUID,
    orbit_id: UUID,
    collection: CollectionCreateIn,
) -> Collection:
    return await collection_handler.create_collection(
        request.user.id, organization_id, orbit_id, collection
    )


@collections_router.get(
    "",
    responses=endpoint_responses,
    response_model=CollectionsList,
)
async def get_orbit_collections(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    cursor: str | None = None,
    limit: Annotated[int, Query(gt=0, le=100)] = 50,
    sort_by: Annotated[CollectionSortBy, Query()] = CollectionSortBy.CREATED_AT,
    order: Annotated[SortOrder, Query()] = SortOrder.DESC,
    search: str | None = None,
) -> CollectionsList:
    return await collection_handler.get_orbit_collections(
        request.user.id,
        organization_id,
        orbit_id,
        cursor,
        limit,
        sort_by,
        order,
        search,
    )


@collections_router.get(
    "/{collection_id}",
    responses=endpoint_responses,
    response_model=CollectionDetails,
)
async def get_collection_details(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    collection_id: UUID,
) -> CollectionDetails:
    return await collection_handler.get_collection_details(
        request.user.id,
        organization_id,
        orbit_id,
        collection_id,
    )


@collections_router.patch(
    "/{collection_id}",
    responses=endpoint_responses,
    response_model=Collection,
)
async def update_collection(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    collection_id: UUID,
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
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    collection_id: UUID,
) -> None:
    await collection_handler.delete_collection(
        request.user.id, organization_id, orbit_id, collection_id
    )
