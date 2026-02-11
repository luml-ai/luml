from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

from luml.schemas.base import BaseOrmConfig


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
    type = "type"
    DESCRIPTION = "description"
    TOTAL_ARTIFACTS = "total_artifacts"


class CollectionCreate(BaseModel):
    orbit_id: UUID
    description: str
    name: str
    type: CollectionType
    tags: list[str] | None = None


class CollectionCreateIn(BaseModel):
    description: str
    name: str
    type: CollectionType
    tags: list[str] | None = None


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
    description: str | None = None
    name: str | None = None
    tags: list[str] | None = None


class CollectionsList(BaseModel):
    items: list[Collection]
    cursor: str | None


def is_artifact_type_allowed(
    collection_type: CollectionType, artifact_type: str
) -> bool:  # noqa: A002
    if collection_type == CollectionType.MIXED:
        return True
    return artifact_type in collection_type.value
