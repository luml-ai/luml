from fastapi import APIRouter, Depends, Request

from dataforce_studio.handlers.deployments import DeploymentHandler
from dataforce_studio.infra.dependencies import UserAuthentication
from dataforce_studio.infra.endpoint_responses import endpoint_responses
from dataforce_studio.schemas.deployment import Deployment, DeploymentCreateIn

deployments_router = APIRouter(
    prefix="/{organization_id}/orbits/{orbit_id}/deployments",
    dependencies=[Depends(UserAuthentication(["jwt", "api_key"]))],
    tags=["deployments"],
)

handler = DeploymentHandler()


@deployments_router.post("", responses=endpoint_responses, response_model=Deployment)
async def create_deployment(
    request: Request,
    organization_id: int,
    orbit_id: int,
    data: DeploymentCreateIn,
) -> Deployment:
    return await handler.create_deployment(
        request.user.id, organization_id, orbit_id, data
    )


@deployments_router.get(
    "", responses=endpoint_responses, response_model=list[Deployment]
)
async def list_deployments(
    request: Request, organization_id: int, orbit_id: int
) -> list[Deployment]:
    return await handler.list_deployments(request.user.id, organization_id, orbit_id)


@deployments_router.get(
    "/{deployment_id}", responses=endpoint_responses, response_model=Deployment
)
async def get_deployment(
    request: Request, organization_id: int, orbit_id: int, deployment_id: int
) -> Deployment:
    return await handler.get_deployment(
        request.user.id, organization_id, orbit_id, deployment_id
    )
