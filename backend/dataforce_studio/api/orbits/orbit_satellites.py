from fastapi import APIRouter, Depends, Request, status

from dataforce_studio.handlers import SatelliteHandler
from dataforce_studio.infra.dependencies import UserAuthentication
from dataforce_studio.infra.endpoint_responses import endpoint_responses
from dataforce_studio.schemas import (
    APIKeyCreateOut,
    Satellite,
    SatelliteCreateIn,
    SatelliteCreateOut,
    SatelliteUpdateIn,
    ShortUUID,
)

organization_orbit_satellites_router = APIRouter(
    prefix="/{organization_id}/orbits/{orbit_id}/satellites",
    dependencies=[Depends(UserAuthentication(["jwt", "api_key"]))],
    tags=["satellites"],
)

satellite_handler = SatelliteHandler()


@organization_orbit_satellites_router.post(
    "", responses=endpoint_responses, response_model=SatelliteCreateOut
)
async def create_satellite(
    request: Request,
    organization_id: ShortUUID,
    orbit_id: ShortUUID,
    satellite: SatelliteCreateIn,
) -> SatelliteCreateOut:
    return await satellite_handler.create_satellite(
        request.user.id, organization_id, orbit_id, satellite
    )


@organization_orbit_satellites_router.get(
    "", responses=endpoint_responses, response_model=list[Satellite]
)
async def list_satellites(
    request: Request,
    organization_id: ShortUUID,
    orbit_id: ShortUUID,
    paired: bool | None = None,
) -> list[Satellite]:
    return await satellite_handler.list_satellites(
        request.user.id, organization_id, orbit_id, paired
    )


@organization_orbit_satellites_router.get(
    "/{satellite_id}", responses=endpoint_responses, response_model=Satellite
)
async def get_satellite(
    request: Request,
    organization_id: ShortUUID,
    orbit_id: ShortUUID,
    satellite_id: ShortUUID,
) -> Satellite:
    return await satellite_handler.get_satellite(
        request.user.id, organization_id, orbit_id, satellite_id
    )


@organization_orbit_satellites_router.patch(
    "/{satellite_id}", responses=endpoint_responses, response_model=Satellite
)
async def update_satellite(
    request: Request,
    organization_id: ShortUUID,
    orbit_id: ShortUUID,
    satellite_id: ShortUUID,
    satellite: SatelliteUpdateIn,
) -> Satellite:
    return await satellite_handler.update_satellite(
        request.user.id, organization_id, orbit_id, satellite_id, satellite
    )


@organization_orbit_satellites_router.post(
    "/{satellite_id}/api-key",
    responses=endpoint_responses,
    response_model=APIKeyCreateOut,
)
async def regenerate_satellite_api_key(
    request: Request,
    organization_id: ShortUUID,
    orbit_id: ShortUUID,
    satellite_id: ShortUUID,
) -> APIKeyCreateOut:
    api_key = await satellite_handler.regenerate_satellite_api_key(
        request.user.id, organization_id, orbit_id, satellite_id
    )
    return APIKeyCreateOut(key=api_key)


@organization_orbit_satellites_router.delete(
    "/{satellite_id}",
    responses=endpoint_responses,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_satellite(
    request: Request,
    organization_id: ShortUUID,
    orbit_id: ShortUUID,
    satellite_id: ShortUUID,
) -> None:
    return await satellite_handler.delete_satellite(
        organization_id, orbit_id, request.user.id, satellite_id
    )
