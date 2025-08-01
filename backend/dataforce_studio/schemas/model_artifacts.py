from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from dataforce_studio.schemas.base import BaseOrmConfig


class CollectionType(StrEnum):
    MODEL = "model"
    DATASET = "dataset"


class CollectionCreate(BaseModel):
    orbit_id: int
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
    id: int
    orbit_id: int
    description: str
    name: str
    collection_type: CollectionType
    tags: list[str] | None = None
    total_models: int
    created_at: datetime
    updated_at: datetime | None = None


class CollectionUpdate(BaseModel):
    id: int | None = None
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
        pattern=r"^[^\s<>:\"/\\|?*{}\[\]`~#%;'^)+!(]+$",
        description="mustn't contain whitespace or characters: "
        "< > : \" / \\ | ? * { } [ ] ` ~ # % ; ' ^ ) + ! (",
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
    collection_id: int
    file_name: str
    model_name: str | None = None
    description: str | None = None
    metrics: dict
    manifest: Manifest
    file_hash: str
    file_index: dict[str, tuple[int, int]]
    bucket_location: str
    size: int
    unique_identifier: str
    tags: list[str] | None = None
    status: ModelArtifactStatus = ModelArtifactStatus.PENDING_UPLOAD


class ModelArtifactIn(BaseModel):
    file_name: ModelArtifactNamesField
    model_name: str | None = None
    description: str | None = None
    metrics: dict
    manifest: Manifest
    file_hash: str
    file_index: dict[str, tuple[int, int]]
    size: int
    tags: list[str] | None = None


class ModelArtifactUpdate(BaseModel):
    id: int
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
    id: int
    collection_id: int
    file_name: str
    model_name: str | None = None
    description: str | None = None
    metrics: dict
    manifest: Manifest
    file_hash: str
    file_index: dict[str, tuple[int, int]]
    bucket_location: str
    size: int
    unique_identifier: str
    tags: list[str] | None = None
    status: ModelArtifactStatus
    created_at: datetime
    updated_at: datetime | None = None


class CreateModelArtifactResponse(BaseModel):
    model: ModelArtifact
    url: str
