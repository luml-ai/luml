from fastapi import APIRouter, Depends, Request

from dataforce_studio.handlers import DeploymentHandler
from dataforce_studio.infra.dependencies import UserAuthentication
from dataforce_studio.infra.endpoint_responses import endpoint_responses
from dataforce_studio.schemas import (
    Deployment,
    DeploymentCreateIn,
    DeploymentDetailsUpdateIn,
    ShortUUID,
)

deployments_router = APIRouter(
    prefix="/{organization_id}/orbits/{orbit_id}/deployments",
    dependencies=[Depends(UserAuthentication(["jwt", "api_key"]))],
    tags=["deployments"],
)

handler = DeploymentHandler()


@deployments_router.post("", responses=endpoint_responses, response_model=Deployment)
async def create_deployment(
    request: Request,
    organization_id: ShortUUID,
    orbit_id: ShortUUID,
    data: DeploymentCreateIn,
) -> Deployment:
    return await handler.create_deployment(
        request.user.id, organization_id, orbit_id, data
    )


@deployments_router.get(
    "", responses=endpoint_responses, response_model=list[Deployment]
)
async def list_deployments(
    request: Request, organization_id: ShortUUID, orbit_id: ShortUUID
) -> list[Deployment]:
    return await handler.list_deployments(request.user.id, organization_id, orbit_id)


@deployments_router.get(
    "/{deployment_id}", responses=endpoint_responses, response_model=Deployment
)
async def get_deployment(
    request: Request,
    organization_id: ShortUUID,
    orbit_id: ShortUUID,
    deployment_id: ShortUUID,
) -> Deployment:
    return await handler.get_deployment(
        request.user.id, organization_id, orbit_id, deployment_id
    )


@deployments_router.patch(
    "/{deployment_id}", responses=endpoint_responses, response_model=Deployment
)
async def update_deployment_details(
    request: Request,
    organization_id: ShortUUID,
    orbit_id: ShortUUID,
    deployment_id: ShortUUID,
    data: DeploymentDetailsUpdateIn,
) -> Deployment:
    return await handler.update_deployment_details(
        request.user.id, organization_id, orbit_id, deployment_id, data
    )


@deployments_router.delete(
    "/{deployment_id}", responses=endpoint_responses, response_model=Deployment
)
async def delete_deployment(
    request: Request,
    organization_id: ShortUUID,
    orbit_id: ShortUUID,
    deployment_id: ShortUUID,
) -> Deployment:
    return await handler.request_deployment_deletion(
        request.user.id, organization_id, orbit_id, deployment_id
    )
