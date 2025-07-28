from enum import StrEnum
from typing import Optional
from pydantic import BaseModel, HttpUrl


class Organization(BaseModel):
    id: int
    name: str
    logo: Optional[HttpUrl] = None
    created_at: str
    updated_at: Optional[str] = None


class BucketSecret(BaseModel):
    id: int
    endpoint: str
    bucket_name: str
    secure: Optional[bool] = None
    region: Optional[str] = None
    cert_check: Optional[bool] = None
    organization_id: int
    created_at: str
    updated_at: Optional[str] = None


class Orbit(BaseModel):
    id: int
    name: str
    organization_id: int
    bucket_secret_id: int
    total_members: Optional[int] = None
    total_collections: Optional[int] = None
    created_at: str
    updated_at: Optional[str] = None


class CollectionType(StrEnum):
    MODEL = "model"
    DATASET = "dataset"


class Collection(BaseModel):
    id: int
    orbit_id: int
    description: str
    name: str
    collection_type: str
    tags: Optional[list[str]] = None
    total_models: int
    created_at: str
    updated_at: Optional[str] = None


class MLModel(BaseModel):
    id: int
    collection_id: int
    file_name: str
    model_name: Optional[str] = None
    description: Optional[str] = None
    metrics: dict
    manifest: dict
    file_hash: str
    file_index: dict[str, tuple[int, int]]
    bucket_location: str
    size: int
    unique_identifier: str
    tags: Optional[list[str]] = None
    status: str
    created_at: str
    updated_at: Optional[str] = None
