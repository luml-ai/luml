from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import AliasPath, BaseModel, Field

from luml.schemas.artifacts import ArtifactType
from luml.schemas.base import BaseOrmConfig


class TrackSortBy(StrEnum):
    CREATED_AT = "created_at"
    NAME = "name"
    ARTIFACT_TYPE = "artifact_type"
    DESCRIPTION = "description"
    TOTAL_ENTRIES = "total_entries"


class StageCreateIn(BaseModel):
    name: str


class StageCreate(StageCreateIn):
    track_id: UUID


class Stage(BaseModel, BaseOrmConfig):
    id: UUID
    track_id: UUID
    name: str
    is_used: bool = False
    created_at: datetime
    updated_at: datetime | None = None


class StageUpdateIn(BaseModel):
    name: str | None = None


class StageUpdate(StageUpdateIn):
    id: UUID | None = None


class TrackCreateIn(BaseModel):
    name: str
    artifact_type: ArtifactType
    description: str | None = None
    tags: list[str] | None = None
    stages: list[str] = Field(default_factory=list)


class TrackCreate(TrackCreateIn):
    orbit_id: UUID


class Track(BaseModel, BaseOrmConfig):
    id: UUID
    orbit_id: UUID
    name: str
    artifact_type: str
    description: str | None = None
    tags: list[str] | None = None
    stages: list[Stage] = Field(default_factory=list)
    next_version: int
    total_entries: int
    created_at: datetime
    updated_at: datetime | None = None


class TrackUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class TrackUpdate(TrackUpdateIn):
    id: UUID | None = None


class TrackEntryCreate(BaseModel):
    track_id: UUID
    artifact_id: UUID
    added_by: UUID


class TrackEntryCreateIn(BaseModel):
    artifact_id: UUID


class TrackEntriesDeleteIn(BaseModel):
    entry_ids: list[UUID] = Field(min_length=1)


class TrackEntry(BaseModel, BaseOrmConfig):
    id: UUID
    track_id: UUID
    artifact_id: UUID
    version: int
    stage_id: UUID | None = None
    added_by: UUID
    created_at: datetime
    updated_at: datetime | None = None
    artifact_name: str | None = Field(
        default=None, validation_alias=AliasPath("artifact", "name")
    )
    artifact_description: str | None = Field(
        default=None, validation_alias=AliasPath("artifact", "description")
    )
    stage_name: str | None = Field(
        default=None, validation_alias=AliasPath("stage", "name")
    )


class TrackEntryUpdate(BaseModel):
    id: UUID | None = None
    stage_id: UUID | None = None


class TrackEntryUpdateIn(BaseModel):
    stage_id: UUID | None = None


class TrackEntriesList(BaseModel):
    items: list[TrackEntry]
    cursor: str | None


class TracksList(BaseModel):
    items: list[Track]
    cursor: str | None
