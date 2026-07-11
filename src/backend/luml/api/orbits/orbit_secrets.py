from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from luml.handlers.orbit_secrets import OrbitSecretHandler
from luml.infra.dependencies import UserAuthentication
from luml.infra.endpoint_responses import endpoint_responses
from luml.schemas.orbit_secret import (
    OrbitSecretCreateIn,
    OrbitSecretOut,
    OrbitSecretUpdate,
)

orbit_secrets_router = APIRouter(
    prefix="/{organization_id}/orbits/{orbit_id}/secrets",
    dependencies=[Depends(UserAuthentication(["jwt", "api_key"]))],
    tags=["orbit-secrets"],
)

orbit_secret_handler = OrbitSecretHandler()


@orbit_secrets_router.post(
    "", responses=endpoint_responses, response_model=OrbitSecretOut
)
async def create_orbit_secret(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    secret: OrbitSecretCreateIn,
) -> OrbitSecretOut:
    return await orbit_secret_handler.create_orbit_secret(
        request.user.id, organization_id, orbit_id, secret
    )


@orbit_secrets_router.get(
    "", responses=endpoint_responses, response_model=list[OrbitSecretOut]
)
async def list_orbit_secrets(
    request: Request, organization_id: UUID, orbit_id: UUID
) -> list[OrbitSecretOut]:
    return await orbit_secret_handler.get_orbit_secrets(
        request.user.id, organization_id, orbit_id
    )


@orbit_secrets_router.get(
    "/{secret_id}", responses=endpoint_responses, response_model=OrbitSecretOut
)
async def get_orbit_secret(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    secret_id: UUID,
) -> OrbitSecretOut:
    return await orbit_secret_handler.get_orbit_secret(
        request.user.id, organization_id, orbit_id, secret_id
    )


@orbit_secrets_router.patch(
    "/{secret_id}", responses=endpoint_responses, response_model=OrbitSecretOut
)
async def update_orbit_secret(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    secret_id: UUID,
    secret: OrbitSecretUpdate,
) -> OrbitSecretOut:
    return await orbit_secret_handler.update_orbit_secret(
        request.user.id, organization_id, orbit_id, secret_id, secret
    )


@orbit_secrets_router.delete(
    "/{secret_id}", responses=endpoint_responses, status_code=status.HTTP_204_NO_CONTENT
)
async def delete_orbit_secret(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    secret_id: UUID,
) -> None:
    await orbit_secret_handler.delete_orbit_secret(
        request.user.id, organization_id, orbit_id, secret_id
    )
