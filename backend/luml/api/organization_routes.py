from fastapi import APIRouter

from luml.api.orbits.orbit_collections import collections_router
from luml.api.orbits.orbit_deployments import deployments_router
from luml.api.orbits.orbit_model_artifacts import model_artifacts_router
from luml.api.orbits.orbit_satellites import (
    organization_orbit_satellites_router,
)
from luml.api.orbits.orbit_secrets import orbit_secrets_router
from luml.api.orbits.orbits import organization_orbits_router
from luml.api.orbits.orbits_members import orbit_members_router
from luml.api.organization.organization_bucket_secrets import (
    bucket_secrets_router,
)
from luml.api.organization.organization_invites import invites_router
from luml.api.organization.organization_members import members_router

organization_all_routers = APIRouter(
    prefix="/organizations",
)

organization_all_routers.include_router(invites_router)
organization_all_routers.include_router(members_router)
organization_all_routers.include_router(organization_orbits_router)
organization_all_routers.include_router(orbit_members_router)
organization_all_routers.include_router(bucket_secrets_router)
organization_all_routers.include_router(collections_router)
organization_all_routers.include_router(model_artifacts_router)
organization_all_routers.include_router(organization_orbit_satellites_router)
organization_all_routers.include_router(orbit_secrets_router)
organization_all_routers.include_router(deployments_router)
