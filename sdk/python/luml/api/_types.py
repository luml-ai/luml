from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from luml.api.resources._listed_resource import PaginatedList


def is_uuid(value: str | None) -> bool:
    if value is None:
        return False
    try:
        UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


class Organization(BaseModel):
    id: str
    name: str
    logo: str | None = None
    created_at: str
    updated_at: str | None = None


class BucketType(StrEnum):
    S3 = "s3"
    AZURE = "azure"


class S3BucketSecret(BaseModel):
    id: str
    type: Literal[BucketType.S3] = BucketType.S3
    endpoint: str
    bucket_name: str
    secure: bool | None = None
    region: str
    cert_check: bool | None = None
    organization_id: str
    created_at: str
    updated_at: str | None = None


class AzureBucketSecret(BaseModel):
    id: str
    type: Literal[BucketType.AZURE] = BucketType.AZURE
    endpoint: str
    bucket_name: str
    organization_id: str
    created_at: str
    updated_at: str | None = None


BucketSecret = S3BucketSecret | AzureBucketSecret


def model_validate_bucket_secret(bucket: dict) -> S3BucketSecret | AzureBucketSecret:
    if bucket.get("type") == BucketType.S3:
        return S3BucketSecret.model_validate(bucket)
    return AzureBucketSecret.model_validate(bucket)


class Orbit(BaseModel):
    id: str
    name: str
    organization_id: str
    bucket_secret_id: str
    total_members: int | None = None
    total_collections: int | None = None
    created_at: str
    updated_at: str | None = None


class CollectionType(StrEnum):
    """
    Options: "model", "dataset".
    """

    MODEL = "model"
    DATASET = "dataset"


class ModelArtifactStatus(StrEnum):
    PENDING_UPLOAD = "pending_upload"
    UPLOADED = "uploaded"
    UPLOAD_FAILED = "upload_failed"
    DELETION_FAILED = "deletion_failed"


class ModelArtifactSortBy(StrEnum):
    """
    Options: "created_at", "model_name", "description", "size", "status", "metrics"
    """

    CREATED_AT = "created_at"
    MODEL_NAME = "model_name"
    SIZE = "size"
    DESCRIPTION = "description"
    STATUS = "status"
    METRICS = "metrics"


class SortOrder(StrEnum):
    """
    Options: "asc", "desc"
    """

    ASC = "asc"
    DESC = "desc"


class CollectionSortBy(StrEnum):
    """
    Options: "created_at", "name", "description", "collection_type", "total_models"
    """

    CREATED_AT = "created_at"
    NAME = "name"
    COLLECTION_TYPE = "collection_type"
    DESCRIPTION = "description"
    TOTAL_MODELS = "total_models"


class Collection(BaseModel):
    id: str
    orbit_id: str
    description: str
    name: str
    collection_type: str
    tags: list[str] | None = None
    total_models: int
    created_at: str
    updated_at: str | None = None


class CollectionDetails(Collection):
    models_tags: list[str] | None = None
    models_metrics: list[str] | None = None


class CollectionsList(PaginatedList[Collection]):
    pass


class ModelArtifact(BaseModel):
    id: str
    collection_id: str
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


class ModelArtifactsList(PaginatedList[ModelArtifact]):
    pass


class ModelDetails(BaseModel):
    file_name: str
    metrics: dict
    manifest: dict
    file_hash: str
    file_index: dict[str, tuple[int, int]]
    size: int


class MultipartUploadInfo(BaseModel):
    upload_id: str
    parts_count: int
    part_size: int


class PartDetails(BaseModel):
    part_number: int
    url: str
    start_byte: int
    end_byte: int
    part_size: int


class UploadDetails(BaseModel):
    type: BucketType
    url: str | None = None
    multipart: bool = False
    bucket_location: str
    bucket_secret_id: str


class MultiPartUploadDetails(BaseModel):
    type: BucketType
    upload_id: str | None = None
    parts: list[PartDetails]
    complete_url: str


class BucketMultipartUpload(BaseModel):
    bucket_id: str
    bucket_location: str
    size: int
    upload_id: str


class CreatedModel(BaseModel):
    upload_details: UploadDetails
    model: ModelArtifact
