from enum import StrEnum

from pydantic import BaseModel


class Organization(BaseModel):
    id: int
    name: str
    logo: str | None = None
    created_at: str
    updated_at: str | None = None


class BucketSecret(BaseModel):
    id: int
    endpoint: str
    bucket_name: str
    secure: bool | None = None
    region: str | None = None
    cert_check: bool | None = None
    organization_id: int
    created_at: str
    updated_at: str | None = None


class Orbit(BaseModel):
    id: int
    name: str
    organization_id: int
    bucket_secret_id: int
    total_members: int | None = None
    total_collections: int | None = None
    created_at: str
    updated_at: str | None = None


class CollectionType(StrEnum):
    MODEL = "model"
    DATASET = "dataset"


class ModelArtifactStatus(StrEnum):
    PENDING_UPLOAD = "pending_upload"
    UPLOADED = "uploaded"
    UPLOAD_FAILED = "upload_failed"
    DELETION_FAILED = "deletion_failed"


class Collection(BaseModel):
    id: int
    orbit_id: int
    description: str
    name: str
    collection_type: str
    tags: list[str] | None = None
    total_models: int
    created_at: str
    updated_at: str | None = None


class ModelArtifact(BaseModel):
    id: int
    collection_id: int
    file_name: str
    model_name: str | None = None
    description: str | None = None
    metrics: dict
    manifest: dict
    file_hash: str
    file_index: dict[str, tuple[int, int]]
    bucket_location: str
    size: int
    unique_identifier: str
    tags: list[str] | None = None
    status: str
    created_at: str
    updated_at: str | None = None


class ModelDetails(BaseModel):
    file_name: str
    metrics: dict
    manifest: dict
    file_hash: str
    file_index: dict[str, tuple[int, int]]
    size: int
