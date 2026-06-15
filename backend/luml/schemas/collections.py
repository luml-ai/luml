from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from luml.schemas.base import BaseOrmConfig

TagList = Annotated[list[Annotated[str, Field(max_length=64)]], Field(max_length=50)]


class CollectionType(StrEnum):
    MODEL = "model"
    DATASET = "dataset"
    EXPERIMENT = "experiment"
    MODEL_DATASET = "model_dataset"
    DATASET_EXPERIMENT = "dataset_experiment"
    MODEL_EXPERIMENT = "model_experiment"
    MIXED = "mixed"


class CollectionTypeFilter(StrEnum):
    MODEL = "model"
    DATASET = "dataset"
    EXPERIMENT = "experiment"
    MIXED = "mixed"


class CollectionSortBy(StrEnum):
    CREATED_AT = "created_at"
    NAME = "name"
    TYPE = "type"
    DESCRIPTION = "description"
    TOTAL_ARTIFACTS = "total_artifacts"


class CollectionCreate(BaseModel):
    orbit_id: UUID
    description: str
    name: str
    type: CollectionType
    tags: list[str] | None = None


class CollectionCreateIn(BaseModel):
    description: str = Field(max_length=1000)
    name: str = Field(max_length=100)
    type: CollectionType
    tags: TagList | None = None


class Collection(BaseModel, BaseOrmConfig):
    id: UUID
    orbit_id: UUID
    description: str
    name: str
    type: CollectionType
    tags: list[str] | None = None
    total_artifacts: int
    created_at: datetime
    updated_at: datetime | None = None


class CollectionDetails(Collection):
    artifacts_tags: list[str] = []
    artifacts_extra_values: list[str] = []


class CollectionUpdate(BaseModel):
    id: UUID | None = None
    description: str | None = None
    name: str | None = None
    tags: list[str] | None = None


class CollectionUpdateIn(BaseModel):
    description: str | None = Field(default=None, max_length=1000)
    name: str | None = Field(default=None, max_length=100)
    tags: TagList | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str | None) -> str | None:
        if v is not None and len(v) < 1:
            raise ValueError("name must not be empty")
        return v


class CollectionsList(BaseModel):
    items: list[Collection]
    cursor: str | None


def is_artifact_type_allowed(
    collection_type: CollectionType, artifact_type: str
) -> bool:  # noqa: A002
    if collection_type == CollectionType.MIXED:
        return True
    return artifact_type in collection_type.value
