from fastapi import APIRouter

from lumlflow.handlers.luml import LumlHandler
from lumlflow.schemas.luml import (
    Artifact,
    Orbit,
    Organization,
    PaginatedCollections,
    UploadArtifactInput,
)

luml_router = APIRouter(prefix="/api/luml", tags=["luml"])

luml_handler = LumlHandler()


@luml_router.get("/organizations", response_model=list[Organization])
def get_luml_organizations() -> list[Organization]:
    return luml_handler.get_luml_organizations()


@luml_router.get("/orbits", response_model=list[Orbit])
def get_luml_orbits(organization_id: str) -> list[Orbit]:
    return luml_handler.get_luml_orbits(organization_id)


@luml_router.get("/collections", response_model=PaginatedCollections)
def get_luml_collections(
    organization_id: str,
    orbit_id: str,
    start_after: str | None = None,
    limit: int = 50,
    search: str | None = None,
) -> PaginatedCollections:
    return luml_handler.get_luml_collections(
        organization_id=organization_id,
        orbit_id=orbit_id,
        start_after=start_after,
        limit=limit,
        search=search,
    )


@luml_router.post("/artifact", response_model=Artifact, status_code=201)
def upload_artifact(artifact: UploadArtifactInput) -> Artifact:
    return luml_handler.upload_model_artifact(artifact)
