from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

from luml.schemas.artifacts import ArtifactType
from luml.schemas.base import BaseOrmConfig


class TrackSortBy(StrEnum):
    CREATED_AT = "created_at"
    NAME = "name"
    ARTIFACT_TYPE = "artifact_type"
    DESCRIPTION = "description"
    TOTAL_ENTRIES = "total_entries"


class TrackStageCreate(BaseModel):
    track_id: UUID
    name: str


class TrackStageCreateIn(BaseModel):
    name: str


class TrackStage(BaseModel, BaseOrmConfig):
    id: UUID
    track_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime | None = None


class TrackStageUpdate(BaseModel):
    id: UUID | None = None
    name: str | None = None


class TrackStageUpdateIn(BaseModel):
    name: str | None = None


class TrackCreate(BaseModel):
    orbit_id: UUID
    name: str
    artifact_type: ArtifactType
    description: str | None = None
    tags: list[str] | None = None
    created_by: UUID


class TrackCreateIn(BaseModel):
    name: str
    artifact_type: ArtifactType
    description: str | None = None
    tags: list[str] | None = None


class Track(BaseModel, BaseOrmConfig):
    id: UUID
    orbit_id: UUID
    name: str
    artifact_type: str
    description: str | None = None
    tags: list[str] | None = None
    created_by: UUID
    next_version: int
    total_entries: int
    created_at: datetime
    updated_at: datetime | None = None


class TrackUpdate(BaseModel):
    id: UUID | None = None
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class TrackUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class TrackEntryCreate(BaseModel):
    track_id: UUID
    artifact_id: UUID
    added_by: UUID


class TrackEntryCreateIn(BaseModel):
    artifact_id: UUID


class TrackEntry(BaseModel, BaseOrmConfig):
    id: UUID
    track_id: UUID
    artifact_id: UUID
    version: int
    stage_id: UUID | None = None
    added_by: UUID
    created_at: datetime
    updated_at: datetime | None = None


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
