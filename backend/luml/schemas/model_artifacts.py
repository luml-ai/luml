from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from luml.constants import MAX_FILE_SIZE_BYTES
from luml.schemas.base import BaseOrmConfig
from luml.schemas.deployment import Deployment
from luml.schemas.storage import AzureUploadDetails, S3UploadDetails


class CollectionType(StrEnum):
    MODEL = "model"
    DATASET = "dataset"


class CollectionCreate(BaseModel):
    orbit_id: UUID
    description: str
    name: str
    collection_type: CollectionType
    tags: list[str] | None = None


class CollectionCreateIn(BaseModel):
    description: str
    name: str
    collection_type: CollectionType
    tags: list[str] | None = None


class Collection(BaseModel, BaseOrmConfig):
    id: UUID
    orbit_id: UUID
    description: str
    name: str
    collection_type: CollectionType
    tags: list[str] | None = None
    total_models: int
    created_at: datetime
    updated_at: datetime | None = None


class CollectionUpdate(BaseModel):
    id: UUID | None = None
    description: str | None = None
    name: str | None = None
    tags: list[str] | None = None


class CollectionUpdateIn(BaseModel):
    description: str | None = None
    name: str | None = None
    tags: list[str] | None = None


ModelArtifactNamesField = Annotated[
    str,
    Field(
        pattern=r"^[^:\"*\`~#%;'^]+\.[^\s:\"*\`~#%;'^]+$",
        description="Must be in the format '<filename>.<extension>'. "
        "Whitespace is forbidden in the extension."
        "filename mustn't contain characters: \" * ` ~ # % ; ' ^ ",
    ),
]


class ModelArtifactStatus(StrEnum):
    PENDING_UPLOAD = "pending_upload"
    UPLOADED = "uploaded"
    PENDING_DELETION = "pending_deletion"
    UPLOAD_FAILED = "upload_failed"
    DELETION_FAILED = "deletion_failed"


class ModelIO(BaseModel):
    name: str
    content_type: str
    dtype: str
    tags: list[str] | None = None


class JSON(ModelIO):
    content_type: Literal["JSON"]


class NDJSON(ModelIO):
    content_type: Literal["NDJSON"]
    dtype: str = Field(
        ...,  # required field
        pattern=r"^(Array\[.+\]|NDContainer\[.+\])$",
        description="Must be in format 'Array[...]' or 'NDContainer[...]'",
    )
    shape: list[str | int]


class Var(BaseModel):
    name: str
    description: str
    tags: list[str] | None = None


class Manifest(BaseModel):
    variant: str

    name: str | None = None
    version: str | None = None
    description: str | None = None

    producer_name: str
    producer_version: str
    producer_tags: list[str]

    inputs: list[NDJSON | JSON]
    outputs: list[NDJSON | JSON]

    dynamic_attributes: list[Var]
    env_vars: list[Var]


class ModelArtifactCreate(BaseModel):
    collection_id: UUID
    file_name: str
    model_name: str | None = None
    description: str | None = None
    metrics: dict[str, Any]
    manifest: Manifest
    file_hash: str
    file_index: dict[str, tuple[int, int]]
    bucket_location: str
    size: int
    unique_identifier: str
    tags: list[str] | None = None
    status: ModelArtifactStatus = ModelArtifactStatus.PENDING_UPLOAD
    created_by_user: str | None = None

    @field_validator("size")
    @classmethod
    def validate_model_size(cls, value: int) -> int:
        if value > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"Model cant be bigger than 5TB - {MAX_FILE_SIZE_BYTES} bytes"
            )
        return value


class ModelArtifactIn(BaseModel):
    file_name: ModelArtifactNamesField
    model_name: str | None = None
    description: str | None = None
    metrics: dict[str, Any]
    manifest: Manifest
    file_hash: str
    file_index: dict[str, tuple[int, int]]
    size: int
    tags: list[str] | None = None

    @field_validator("size")
    @classmethod
    def validate_model_size(cls, value: int) -> int:
        if value > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"Model cant be bigger than 5TB - {MAX_FILE_SIZE_BYTES} bytes"
            )
        return value


class ModelArtifactUpdate(BaseModel):
    id: UUID
    file_name: str | None = None
    model_name: str | None = None
    description: str | None = None
    status: ModelArtifactStatus | None = None
    tags: list[str] | None = None


class ModelArtifactUpdateIn(BaseModel):
    file_name: ModelArtifactNamesField | None = None
    model_name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    status: (
        Literal[
            ModelArtifactStatus.UPLOADED,
            ModelArtifactStatus.UPLOAD_FAILED,
            ModelArtifactStatus.DELETION_FAILED,
        ]
        | None
    ) = None


class ModelArtifact(BaseModel, BaseOrmConfig):
    id: UUID
    collection_id: UUID
    file_name: str
    model_name: str | None = None
    description: str | None = None
    metrics: dict[str, Any]
    manifest: Manifest
    file_hash: str
    file_index: dict[str, tuple[int, int]]
    bucket_location: str
    size: int
    unique_identifier: str
    tags: list[str] | None = None
    status: ModelArtifactStatus
    created_by_user: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    @field_validator("size")
    @classmethod
    def validate_model_size(cls, value: int) -> int:
        if value > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"Model cant be bigger than 5TB - {MAX_FILE_SIZE_BYTES} bytes"
            )
        return value


class ModelArtifactDetails(ModelArtifact):
    deployments: list[Deployment] | None = None
    collection: Collection


class CreateModelArtifactResponse(BaseModel):
    model: ModelArtifact
    upload_details: S3UploadDetails | AzureUploadDetails


class SatelliteModelArtifactResponse(BaseModel):
    model: ModelArtifact
    url: str
