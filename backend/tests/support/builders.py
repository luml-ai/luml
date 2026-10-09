from uuid import UUID, uuid4

from luml.models import OrganizationOrm
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.collections import CollectionRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.users import UserRepository
from luml.schemas.artifacts import (
    Artifact,
    ArtifactCreate,
    ArtifactStatus,
    ArtifactType,
)
from luml.schemas.collections import Collection, CollectionCreate, CollectionType
from luml.schemas.orbit import OrbitCreateIn, OrbitDetails
from luml.schemas.organization import OrganizationCreateIn
from sqlalchemy.ext.asyncio import AsyncEngine


async def create_artifact(
    engine: AsyncEngine,
    template: ArtifactCreate,
    collection_id: UUID,
    *,
    name: str | None,
    status: ArtifactStatus = ArtifactStatus.UPLOADED,
    artifact_type: ArtifactType = ArtifactType.MODEL,
    extra_values: dict[str, object] | None = None,
    description: str | None = None,
    unique_identifier: str | None = None,
) -> Artifact:
    data = template.model_copy()
    data.collection_id = collection_id
    data.name = name
    data.status = status
    data.type = artifact_type
    data.description = description
    data.unique_identifier = (
        unique_identifier if unique_identifier is not None else str(uuid4())
    )
    data.bucket_location = f"objects/{uuid4()}"
    if extra_values is not None:
        data.extra_values = extra_values
    return await ArtifactRepository(engine).create_artifact(data)


async def create_sibling_orbit(
    engine: AsyncEngine, organization_id: UUID, bucket_secret_id: UUID
) -> OrbitDetails:
    orbit = await OrbitRepository(engine).create_orbit(
        organization_id,
        OrbitCreateIn(name="sibling orbit", bucket_secret_id=bucket_secret_id),
    )
    assert orbit is not None
    return orbit


async def create_sibling_organization(
    engine: AsyncEngine, user_id: UUID
) -> OrganizationOrm:
    return await UserRepository(engine).create_organization(
        user_id, OrganizationCreateIn(name="sibling org")
    )


async def create_collection(
    engine: AsyncEngine,
    orbit_id: UUID,
    name: str,
    type: CollectionType = CollectionType.MODEL,  # noqa: A002
) -> Collection:
    return await CollectionRepository(engine).create_collection(
        CollectionCreate(
            orbit_id=orbit_id, name=name, description=name, type=type, tags=[]
        )
    )
