from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from luml.handlers.deployments import DeploymentHandler
from luml.infra.dependencies import UserAuthentication
from luml.infra.endpoint_responses import endpoint_responses
from luml.schemas.deployment import (
    Deployment,
    DeploymentCreateIn,
    DeploymentDetailsUpdateIn,
)
from luml.schemas.satellite import SatelliteQueueTask

deployments_router = APIRouter(
    prefix="/{organization_id}/orbits/{orbit_id}/deployments",
    dependencies=[Depends(UserAuthentication(["jwt", "api_key"]))],
    tags=["deployments"],
)

handler = DeploymentHandler()


@deployments_router.post("", responses=endpoint_responses, response_model=Deployment)
async def create_deployment(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    data: DeploymentCreateIn,
) -> Deployment:
    return await handler.create_deployment(
        request.user.id, organization_id, orbit_id, data
    )


@deployments_router.get(
    "", responses=endpoint_responses, response_model=list[Deployment]
)
async def list_deployments(
    request: Request, organization_id: UUID, orbit_id: UUID
) -> list[Deployment]:
    return await handler.list_deployments(request.user.id, organization_id, orbit_id)


@deployments_router.get(
    "/{deployment_id}", responses=endpoint_responses, response_model=Deployment
)
async def get_deployment(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    deployment_id: UUID,
) -> Deployment:
    return await handler.get_deployment(
        request.user.id, organization_id, orbit_id, deployment_id
    )


@deployments_router.patch(
    "/{deployment_id}", responses=endpoint_responses, response_model=Deployment
)
async def update_deployment_details(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    deployment_id: UUID,
    data: DeploymentDetailsUpdateIn,
) -> Deployment:
    return await handler.update_deployment_details(
        request.user.id, organization_id, orbit_id, deployment_id, data
    )


@deployments_router.delete(
    "/{deployment_id}",
    responses=endpoint_responses,
    response_model=SatelliteQueueTask,
)
async def request_deployment_deletion(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    deployment_id: UUID,
) -> SatelliteQueueTask:
    """ "Deployment delete" - old name."""
    return await handler.request_deployment_deletion(
        request.user.id,
        organization_id,
        orbit_id,
        deployment_id,
    )


@deployments_router.delete(
    "/{deployment_id}/force",
    responses=endpoint_responses,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def force_deployment_delete(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    deployment_id: UUID,
) -> None:
    return await handler.force_delete_deployment(
        request.user.id,
        organization_id,
        orbit_id,
        deployment_id,
    )
