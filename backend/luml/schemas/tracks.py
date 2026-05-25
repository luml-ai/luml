from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from luml.schemas.artifacts import ArtifactType
from luml.schemas.base import BaseOrmConfig


class TrackCreate(BaseModel):
    name: str
    artifact_type: ArtifactType
    description: str | None = None
    tags: list[str] = []


class Track(BaseModel, BaseOrmConfig):
    id: UUID
    orbit_id: UUID
    name: str
    artifact_type: ArtifactType
    description: str | None
    tags: list[str]
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    total_entries: int


class TrackUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class TracksList(BaseModel):
    items: list[Track]
    cursor: str | None


class TrackArtifactCreate(BaseModel):
    artifact_id: UUID


class TrackArtifactStage(BaseModel, BaseOrmConfig):
    id: UUID
    name: str


class TrackArtifact(BaseModel, BaseOrmConfig):
    id: UUID
    track_id: UUID
    artifact_id: UUID
    version: int
    stage: TrackArtifactStage | None
    created_at: datetime
    added_by: UUID


class TrackArtifactUpdate(BaseModel):
    stage_id: UUID | None


class TrackStageConflict(BaseModel):
    stage_name: str
    held_by_version: int


class TrackArtifactUpdateResponse(BaseModel, BaseOrmConfig):
    entry: TrackArtifact


class TrackEntriesList(BaseModel):
    items: list[TrackArtifact]
    cursor: str | None


class TrackStageCreate(BaseModel):
    name: str


class TrackStage(BaseModel, BaseOrmConfig):
    id: UUID
    track_id: UUID
    name: str
    created_at: datetime


class TrackStageUpdate(BaseModel):
    name: str | None = None


class TrackStagesList(BaseModel):
    items: list[TrackStage]
    cursor: str | None
