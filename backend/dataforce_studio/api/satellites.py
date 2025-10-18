from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from dataforce_studio.handlers.deployments import DeploymentHandler
from dataforce_studio.handlers.model_artifacts import ModelArtifactHandler
from dataforce_studio.handlers.orbit_secrets import OrbitSecretHandler
from dataforce_studio.handlers.satellites import SatelliteHandler
from dataforce_studio.infra.dependencies import UserAuthentication
from dataforce_studio.infra.endpoint_responses import endpoint_responses
from dataforce_studio.schemas.deployment import (
    Deployment,
    DeploymentStatusUpdateIn,
    DeploymentUpdateIn,
    InferenceAccessIn,
    InferenceAccessOut,
)
from dataforce_studio.schemas.model_artifacts import SatelliteModelArtifactResponse
from dataforce_studio.schemas.orbit_secret import OrbitSecret
from dataforce_studio.schemas.satellite import (
    Satellite,
    SatellitePairIn,
    SatelliteQueueTask,
    SatelliteTaskStatus,
    SatelliteTaskUpdateIn,
)

satellite_worker_router = APIRouter(
    prefix="/satellites",
    dependencies=[Depends(UserAuthentication(["satellite"]))],
    tags=["satellites"],
)

satellite_handler = SatelliteHandler()
deployment_handler = DeploymentHandler()
orbit_secret_handler = OrbitSecretHandler()
model_artifacts_handler = ModelArtifactHandler()


@satellite_worker_router.post(
    "/pair", responses=endpoint_responses, response_model=Satellite
)
async def pair_satellite(request: Request, data: SatellitePairIn) -> Satellite:
    return await satellite_handler.pair_satellite(
        request.user.id,
        str(data.base_url),
        data.capabilities,
    )


@satellite_worker_router.get(
    "/secrets", responses=endpoint_responses, response_model=list[OrbitSecret]
)
async def list_orbit_secrets(request: Request) -> list[OrbitSecret]:
    return await orbit_secret_handler.get_worker_orbit_secrets(request.user.orbit_id)


@satellite_worker_router.get(
    "/secrets/{secret_id}",
    responses=endpoint_responses,
    response_model=OrbitSecret,
)
async def get_orbit_secret(request: Request, secret_id: UUID) -> OrbitSecret:
    return await orbit_secret_handler.get_worker_orbit_secret(
        request.user.orbit_id,
        secret_id,
    )


@satellite_worker_router.get(
    "/tasks",
    responses=endpoint_responses,
    response_model=list[SatelliteQueueTask],
)
async def list_tasks(
    request: Request, status: SatelliteTaskStatus | None = None
) -> list[SatelliteQueueTask]:
    await satellite_handler.touch_last_seen(request.user.id)
    return await satellite_handler.list_tasks(request.user.id, status)


@satellite_worker_router.post(
    "/tasks/{task_id}/status",
    responses=endpoint_responses,
    response_model=SatelliteQueueTask,
)
async def update_task_status(
    request: Request, task_id: UUID, data: SatelliteTaskUpdateIn
) -> SatelliteQueueTask:
    await satellite_handler.touch_last_seen(request.user.id)
    return await satellite_handler.update_task_status(
        request.user.id,
        task_id,
        data.status,
        data.result,
    )


@satellite_worker_router.get(
    "/deployments",
    responses=endpoint_responses,
    response_model=list[Deployment],
)
async def list_deployments(request: Request) -> list[Deployment]:
    await satellite_handler.touch_last_seen(request.user.id)
    return await deployment_handler.list_worker_deployments(request.user.id)


@satellite_worker_router.get(
    "/deployments/{deployment_id}",
    responses=endpoint_responses,
    response_model=Deployment,
)
async def get_deployment(request: Request, deployment_id: UUID) -> Deployment:
    await satellite_handler.touch_last_seen(request.user.id)
    return await deployment_handler.get_worker_deployment(
        request.user.id, deployment_id
    )


@satellite_worker_router.patch(
    "/deployments/{deployment_id}",
    responses=endpoint_responses,
    response_model=Deployment,
)
async def update_deployment(
    request: Request, deployment_id: UUID, data: DeploymentUpdateIn
) -> Deployment:
    await satellite_handler.touch_last_seen(request.user.id)
    return await deployment_handler.update_worker_deployment(
        request.user.id,
        deployment_id,
        data.inference_url,
    )


@satellite_worker_router.patch(
    "/deployments/{deployment_id}/status",
    responses=endpoint_responses,
    response_model=Deployment,
)
async def update_deployment_status(
    request: Request, deployment_id: UUID, data: DeploymentStatusUpdateIn
) -> Deployment:
    await satellite_handler.touch_last_seen(request.user.id)
    return await deployment_handler.update_worker_deployment_status(
        request.user.id, deployment_id, data.status
    )


@satellite_worker_router.get(
    "/deployments/{deployment_id}",
    responses=endpoint_responses,
    response_model=Deployment,
)
async def get_satellite_deployment(request: Request, deployment_id: UUID) -> Deployment:
    await satellite_handler.touch_last_seen(request.user.id)
    return await deployment_handler.get_worker_deployment(
        request.user.id,
        deployment_id,
    )


@satellite_worker_router.delete(
    "/deployments/{deployment_id}",
    responses=endpoint_responses,
    response_model=Deployment,
)
async def delete_deployment(request: Request, deployment_id: UUID) -> Deployment:
    await satellite_handler.touch_last_seen(request.user.id)
    return await deployment_handler.delete_worker_deployment(
        request.user.id,
        deployment_id,
    )


@satellite_worker_router.post(
    "/deployments/inference-access",
    responses=endpoint_responses,
    response_model=InferenceAccessOut,
)
async def authorize_inference_access(
    request: Request, data: InferenceAccessIn
) -> InferenceAccessOut:
    await satellite_handler.touch_last_seen(request.user.id)
    authorized = await deployment_handler.verify_user_inference_access(
        request.user.orbit_id, data.api_key
    )
    return InferenceAccessOut(authorized=authorized)


@satellite_worker_router.get(
    "/model_artifacts/{model_artifact_id}/download-url",
    responses=endpoint_responses,
)
async def get_model_artifact_download_url(
    request: Request, model_artifact_id: UUID
) -> dict[str, Any]:
    await satellite_handler.touch_last_seen(request.user.id)
    url = await model_artifacts_handler.request_satellite_download_url(
        request.user.orbit_id, model_artifact_id
    )
    return {"url": url}


@satellite_worker_router.get(
    "/model_artifacts/{model_artifact_id}",
    responses=endpoint_responses,
)
async def get_model_artifact(
    request: Request, model_artifact_id: UUID
) -> SatelliteModelArtifactResponse:
    await satellite_handler.touch_last_seen(request.user.id)
    return await model_artifacts_handler.get_satellite_model_artifact(
        request.user.orbit_id, model_artifact_id
    )
