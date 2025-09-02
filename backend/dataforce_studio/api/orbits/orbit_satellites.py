from fastapi import APIRouter, Depends, Request

from dataforce_studio.handlers.satellites import SatelliteHandler
from dataforce_studio.infra.dependencies import UserAuthentication
from dataforce_studio.infra.endpoint_responses import endpoint_responses
from dataforce_studio.schemas.satellite import (
    Satellite,
    SatelliteCreateIn,
    SatelliteCreateOut,
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
    organization_id: int,
    orbit_id: int,
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
    organization_id: int,
    orbit_id: int,
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
    organization_id: int,
    orbit_id: int,
    satellite_id: int,
) -> Satellite:
    return await satellite_handler.get_satellite(
        request.user.id, organization_id, orbit_id, satellite_id
    )
