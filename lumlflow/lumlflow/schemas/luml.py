from pydantic import BaseModel

from lumlflow.schemas.base import BaseOrmConfig


class Organization(BaseModel):
    id: str
    name: str
    logo: str | None = None
    created_at: str
    updated_at: str | None = None


class Orbit(BaseModel):
    id: str
    name: str
    organization_id: str
    bucket_secret_id: str
    total_members: int | None = None
    total_collections: int | None = None
    created_at: str
    updated_at: str | None = None


class Collection(BaseModel):
    id: str
    orbit_id: str
    description: str
    name: str
    type: str
    tags: list[str] | None = None
    total_artifacts: int = 0
    created_at: str
    updated_at: str | None = None


class PaginatedCollections(BaseModel, BaseOrmConfig):
    items: list[Collection]
    cursor: str | None = None


class UploadArtifactInput(BaseModel):
    model_id: str
    organization_id: str
    orbit_id: str
    collection_id: str
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class Artifact(BaseModel):
    id: str
    collection_id: str
    file_name: str
    name: str
    description: str | None = None
    extra_values: dict
    manifest: dict
    file_hash: str
    file_index: dict[str, tuple[int, int]]
    bucket_location: str
    size: int
    unique_identifier: str
    tags: list[str] | None = None
    status: str
    type: str
    created_at: str
    updated_at: str | None = None
