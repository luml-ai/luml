from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from luml.handlers.lineage import LineageHandler
from luml.infra.dependencies import UserAuthentication
from luml.infra.endpoint_responses import endpoint_responses
from luml.schemas.lineage import (
    LineageBatchIn,
    LineageBatchResult,
    LineageCreateIn,
    LineageEdge,
    LineageGraph,
)

lineage_router = APIRouter(
    prefix="/{organization_id}/orbits/{orbit_id}",
    dependencies=[Depends(UserAuthentication(["jwt", "api_key"]))],
    tags=["orbit-lineage"],
)

lineage_handler = LineageHandler()


@lineage_router.get(
    "/artifacts/{artifact_id}/lineage",
    responses=endpoint_responses,
    response_model=LineageGraph,
)
async def get_lineage(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    artifact_id: UUID,
    depth: Annotated[int | None, Query(ge=1)] = None,
) -> LineageGraph:
    return await lineage_handler.get_graph(
        request.user.id,
        organization_id,
        orbit_id,
        artifact_id,
        depth,
    )


@lineage_router.post(
    "/artifacts/{artifact_id}/lineage",
    responses=endpoint_responses,
    response_model=list[LineageEdge],
)
async def create_lineage(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    artifact_id: UUID,
    lineage: LineageCreateIn,
) -> list[LineageEdge]:
    return await lineage_handler.create_links(
        request.user.id,
        organization_id,
        orbit_id,
        artifact_id,
        lineage.target_artifact_ids,
        request.auth.scopes,
    )


@lineage_router.delete(
    "/artifacts/{artifact_id}/lineage/{edge_id}",
    responses=endpoint_responses,
    response_model=LineageEdge,
)
async def delete_lineage(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    artifact_id: UUID,
    edge_id: UUID,
) -> LineageEdge:
    return await lineage_handler.delete_link(
        request.user.id,
        organization_id,
        orbit_id,
        artifact_id,
        edge_id,
        request.auth.scopes,
    )


@lineage_router.post(
    "/lineage/batch",
    responses=endpoint_responses,
    response_model=LineageBatchResult,
)
async def apply_lineage_changes(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    changes: LineageBatchIn,
) -> LineageBatchResult:
    return await lineage_handler.apply_changes(
        request.user.id,
        organization_id,
        orbit_id,
        changes,
        request.auth.scopes,
    )
