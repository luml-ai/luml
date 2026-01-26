from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from luml.constants import MAX_FILE_SIZE_BYTES
from luml.schemas.base import BaseOrmConfig
from luml.schemas.collections import Collection
from luml.schemas.deployment import Deployment
from luml.schemas.storage import AzureUploadDetails, S3UploadDetails

ArtifactNamesField = Annotated[
    str,
    Field(
        pattern=r"^[^:\"*\`~#%;'^]+\.[^\s:\"*\`~#%;'^]+$",
        description="Must be in the format '<filename>.<extension>'. "
        "Whitespace is forbidden in the extension."
        "filename mustn't contain characters: \" * ` ~ # % ; ' ^ ",
    ),
]


class ArtifactStatus(StrEnum):
    PENDING_UPLOAD = "pending_upload"
    UPLOADED = "uploaded"
    PENDING_DELETION = "pending_deletion"
    UPLOAD_FAILED = "upload_failed"
    DELETION_FAILED = "deletion_failed"


class ArtifactSortBy(StrEnum):
    CREATED_AT = "created_at"
    name = "name"
    SIZE = "size"
    DESCRIPTION = "description"
    STATUS = "status"


class ArtifactType(StrEnum):
    MODEL = "model"
    EXPERIMENT = "experiment"
    DATASET = "dataset"


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


class ArtifactCreate(BaseModel):
    collection_id: UUID
    file_name: str
    name: str | None = None
    description: str | None = None
    extra_values: dict[str, Any]
    manifest: Manifest
    file_hash: str
    file_index: dict[str, tuple[int, int]]
    bucket_location: str
    size: int
    unique_identifier: str
    tags: list[str] | None = None
    status: ArtifactStatus = ArtifactStatus.PENDING_UPLOAD
    created_by_user: str | None = None
    type: ArtifactType

    @field_validator("size")
    @classmethod
    def validate_model_size(cls, value: int) -> int:
        if value > MAX_FILE_SIZE_BYTES:
            raise ValueError("Artifact cant be bigger than 5TB")
        return value


class ArtifactIn(BaseModel):
    file_name: ArtifactNamesField
    name: str | None = None
    description: str | None = None
    extra_values: dict[str, Any]
    manifest: Manifest
    file_hash: str
    file_index: dict[str, tuple[int, int]]
    size: int
    tags: list[str] | None = None
    type: ArtifactType

    @field_validator("size")
    @classmethod
    def validate_model_size(cls, value: int) -> int:
        if value > MAX_FILE_SIZE_BYTES:
            raise ValueError("Artifact cant be bigger than 5TB")
        return value


class ArtifactUpdate(BaseModel):
    id: UUID
    file_name: str | None = None
    name: str | None = None
    description: str | None = None
    status: ArtifactStatus | None = None
    tags: list[str] | None = None


class ArtifactUpdateIn(BaseModel):
    file_name: ArtifactNamesField | None = None
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    status: (
        Literal[
            ArtifactStatus.UPLOADED,
            ArtifactStatus.UPLOAD_FAILED,
            ArtifactStatus.DELETION_FAILED,
        ]
        | None
    ) = None


class Artifact(BaseModel, BaseOrmConfig):
    id: UUID
    collection_id: UUID
    file_name: str
    name: str | None = None
    description: str | None = None
    extra_values: dict[str, Any]
    manifest: Manifest
    file_hash: str
    file_index: dict[str, tuple[int, int]]
    bucket_location: str
    size: int
    unique_identifier: str
    tags: list[str] | None = None
    status: ArtifactStatus
    type: ArtifactType
    created_by_user: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    @field_validator("size")
    @classmethod
    def validate_model_size(cls, value: int) -> int:
        if value > MAX_FILE_SIZE_BYTES:
            raise ValueError("Artifact cant be bigger than 5TB")
        return value


class ArtifactDetails(Artifact):
    deployments: list[Deployment] | None = None
    collection: Collection


class CreateArtifactResponse(BaseModel):
    artifact: Artifact
    upload_details: S3UploadDetails | AzureUploadDetails


class SatelliteArtifactResponse(BaseModel):
    artifact: Artifact
    url: str


class ArtifactsList(BaseModel):
    items: list[Artifact]
    cursor: str | None
