from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field

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


class UploadType(StrEnum):
    AUTO = "auto"
    MODEL = "model"
    EXPERIMENT = "experiment"


class ArtifactIn(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class UploadArtifactForm(BaseModel):
    upload_type: UploadType
    embed_experiment: bool = False
    experiment_id: str

    organization_id: str
    orbit_id: str
    collection_id: str

    artifact: ArtifactIn


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


class JobResponse(BaseModel):
    job_id: str


class ProgressEvent(BaseModel):
    type: Literal["progress"] = "progress"
    percent: int
    uploaded_bytes: int
    total_bytes: int


class CompleteEvent(BaseModel):
    type: Literal["complete"] = "complete"
    artifacts: list[Artifact]


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


class NotFoundEvent(BaseModel):
    type: Literal["not_found"] = "not_found"


ArtifactUploadEvent = Annotated[
    ProgressEvent | CompleteEvent | ErrorEvent | NotFoundEvent,
    Field(discriminator="type"),
]
