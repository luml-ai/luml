import asyncio
import uuid

import pytest
from luml.handlers.artifacts import ArtifactHandler
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.lineage import LineageRepository
from luml.schemas.artifacts import (
    ArtifactCreate,
    ArtifactListed,
)
from luml.schemas.lineage import LineageVia
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.builders import create_artifact
from tests.support.seeds import CollectionFixtureData


@pytest.fixture
def handler(engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch) -> ArtifactHandler:
    monkeypatch.setattr(
        ArtifactHandler, "_ArtifactHandler__repository", ArtifactRepository(engine)
    )
    monkeypatch.setattr(
        ArtifactHandler,
        "_ArtifactHandler__lineage_repository",
        LineageRepository(engine),
    )
    return ArtifactHandler()


async def _get_listed_artifacts(
    engine: AsyncEngine,
    orbit_id: uuid.UUID,
    artifact_ids: list[uuid.UUID],
) -> dict[uuid.UUID, ArtifactListed]:
    artifacts = await ArtifactRepository(engine).get_artifacts_by_ids_in_orbit(
        orbit_id, artifact_ids
    )
    return {artifact.id: artifact for artifact in artifacts}


class TestArtifactHandler:
    async def test_delete_artifact_removes_component_when_last_two_deleted_concurrently(
        self,
        handler: ArtifactHandler,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        artifact_repository = ArtifactRepository(engine)
        lineage_repository = LineageRepository(engine)
        orbit_id = seeded_collection.orbit.id
        artifacts = [
            await create_artifact(
                engine,
                new_artifact,
                seeded_collection.collection.id,
                name=name,
                status=new_artifact.status,
            )
            for name in ["last-1", "last-2"]
        ]
        listed = await _get_listed_artifacts(
            engine, orbit_id, [artifact.id for artifact in artifacts]
        )
        nodes = [
            await lineage_repository.get_or_create_node(orbit_id, listed[artifact.id])
            for artifact in artifacts
        ]
        await lineage_repository.create_edges(
            orbit_id, [(nodes[0].id, nodes[1].id)], "Test User", LineageVia.API
        )

        await asyncio.gather(
            handler._delete_artifact(orbit_id, artifacts[0].id),
            handler._delete_artifact(orbit_id, artifacts[1].id),
        )

        assert await artifact_repository.get_artifact(artifacts[0].id) is None
        assert await artifact_repository.get_artifact(artifacts[1].id) is None
        assert (
            await lineage_repository.get_nodes_by_ids(
                orbit_id, [node.id for node in nodes]
            )
            == []
        )
