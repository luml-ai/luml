import uuid

import pytest
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.tracks import TrackEntryRepository, TrackRepository
from luml.schemas.artifacts import ArtifactType
from luml.schemas.tracks import TrackCreate, TrackEntryCreate
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def repository(engine: AsyncEngine) -> ArtifactRepository:
    return ArtifactRepository(engine)


async def _add_artifact_to_track(
    engine: AsyncEngine,
    orbit_id: uuid.UUID,
    artifact_id: uuid.UUID,
    added_by: str,
    name: str = "track",
) -> uuid.UUID:
    track = await TrackRepository(engine).create_track(
        TrackCreate(orbit_id=orbit_id, name=name, artifact_type=ArtifactType.MODEL)
    )
    await TrackEntryRepository(engine).create_entry(
        TrackEntryCreate(track_id=track.id, artifact_id=artifact_id, added_by=added_by)
    )
    return track.id
