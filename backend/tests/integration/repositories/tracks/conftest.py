import uuid

import pytest
from luml.repositories.tracks import (
    TrackEntryRepository,
    TrackRepository,
    TrackStageRepository,
)
from luml.schemas.artifacts import (
    NDJSON,
    ArtifactCreate,
    ArtifactStatus,
    ArtifactType,
    Manifest,
)
from luml.schemas.general import PaginationParams, SortOrder
from luml.schemas.tracks import TrackCreate, TrackEntry, TrackEntryCreate
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.builders import create_artifact
from tests.support.seeds import CollectionFixtureData


@pytest.fixture
def repository(engine: AsyncEngine) -> TrackRepository:
    return TrackRepository(engine)


@pytest.fixture
def stage_repository(engine: AsyncEngine) -> TrackStageRepository:
    return TrackStageRepository(engine)


@pytest.fixture
def entry_repository(engine: AsyncEngine) -> TrackEntryRepository:
    return TrackEntryRepository(engine)


def _make_manifest() -> Manifest:
    return Manifest(
        variant="pipeline",
        description="",
        producer_name="test",
        producer_version="0.1.0",
        producer_tags=["test::v1"],
        inputs=[
            NDJSON(
                name="x",
                content_type="NDJSON",
                dtype="Array[float32]",
                shape=["batch", 1],
            ),
        ],
        outputs=[
            NDJSON(
                name="y",
                content_type="NDJSON",
                dtype="Array[string]",
                shape=["batch"],
            ),
        ],
        dynamic_attributes=[],
        env_vars=[],
    )


@pytest.fixture
def artifact_template() -> ArtifactCreate:
    return ArtifactCreate(
        collection_id=uuid.uuid4(),
        file_name="artifact.luml",
        name="artifact",
        extra_values={"accuracy": 0.9},
        manifest=_make_manifest(),
        file_hash=str(uuid.uuid4()),
        file_index={"model": (0, 100)},
        bucket_location="orbit/col/artifact.luml",
        size=100,
        unique_identifier=f"uid_{uuid.uuid4().hex[:8]}",
        tags=["test"],
        status=ArtifactStatus.UPLOADED,
        type=ArtifactType.MODEL,
        created_by_user="Test User",
    )


async def _seed_entries(
    data: CollectionFixtureData,
    specs: list[tuple[str, str | None]],
    artifact_template: ArtifactCreate,
) -> tuple[uuid.UUID, list[TrackEntry]]:
    repo = TrackRepository(data.engine)
    entry_repo = TrackEntryRepository(data.engine)

    track = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id,
            name=f"track-{uuid.uuid4().hex[:8]}",
            artifact_type=ArtifactType.MODEL,
        )
    )
    entries = []
    for name, description in specs:
        artifact = await create_artifact(
            data.engine,
            artifact_template,
            data.collection.id,
            name=name,
            description=description,
        )
        entries.append(
            await entry_repo.create_entry(
                TrackEntryCreate(
                    track_id=track.id,
                    artifact_id=artifact.id,
                    added_by=data.user.email,
                )
            )
        )
    return track.id, entries


async def _collect_pages(
    entry_repo: TrackEntryRepository,
    track_id: uuid.UUID,
    sort_by: str,
    order: SortOrder,
    limit: int,
) -> list[TrackEntry]:
    collected: list[TrackEntry] = []
    cursor = None
    max_pages = 100
    for _ in range(max_pages):
        page, cursor = await entry_repo.list_entries(
            track_id,
            PaginationParams(
                limit=limit,
                sort_by=sort_by,
                order=order,
                cursor=cursor,
                scope_id=track_id,
            ),
        )
        collected.extend(page)
        if cursor is None:
            break
    return collected
