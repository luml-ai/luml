from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from luml.constants import LINEAGE_MAX_BATCH_ITEMS
from luml.schemas.artifacts import ArtifactListed
from luml.schemas.base import BaseOrmConfig

LineageNodePair = tuple[UUID, UUID]
LineageCoordinates = tuple[float, float]


class LineageVia(StrEnum):
    UI = "ui"
    API = "api"


class LineageNodeRef(BaseModel):
    artifact_id: UUID | None = None
    node_id: UUID | None = None

    @model_validator(mode="after")
    def validate_single_reference(self) -> Self:
        if (self.artifact_id is None) == (self.node_id is None):
            raise ValueError("Exactly one lineage node reference must be set")
        return self


class LineagePosition(BaseModel):
    ref: LineageNodeRef
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)


class LineagePair(BaseModel):
    source: LineageNodeRef
    target: LineageNodeRef


class LineageCreateIn(BaseModel):
    target_artifact_ids: list[UUID] = Field(
        min_length=1, max_length=LINEAGE_MAX_BATCH_ITEMS
    )


class LineageBatchIn(BaseModel):
    create: list[LineagePair] = Field(
        default_factory=list, max_length=LINEAGE_MAX_BATCH_ITEMS
    )
    delete: list[UUID] = Field(default_factory=list, max_length=LINEAGE_MAX_BATCH_ITEMS)
    positions: list[LineagePosition] = Field(
        default_factory=list, max_length=LINEAGE_MAX_BATCH_ITEMS
    )


class LineageEdge(BaseModel, BaseOrmConfig):
    id: UUID
    source: UUID
    target: UUID
    created_by_user: str
    created_via: LineageVia
    created_at: datetime


class LineageNode(BaseModel):
    id: UUID
    artifact_id: UUID | None
    type: str
    name: str
    collection_name: str | None
    x: float | None
    y: float | None
    is_deleted: bool
    data: ArtifactListed | None


class LineageGraph(BaseModel):
    nodes: list[LineageNode]
    edges: list[LineageEdge]
    focal_artifact_id: UUID
    depth: int | None
    truncated: bool


class LineageBatchResult(BaseModel):
    created: list[LineageEdge]
    deleted: list[LineageEdge]
