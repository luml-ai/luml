import asyncio
import uuid

import pytest
from luml.handlers.artifacts import ArtifactHandler
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.lineage import LineageRepository
from luml.schemas.artifacts import (
    Artifact,
    ArtifactCreate,
    ArtifactListed,
)
from luml.schemas.lineage import LineageVia
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import CollectionFixtureData


async def _create_artifact(
    engine: AsyncEngine,
    template: ArtifactCreate,
    collection_id: uuid.UUID,
    name: str,
) -> Artifact:
    artifact = template.model_copy(
        update={
            "collection_id": collection_id,
            "name": name,
            "unique_identifier": f"{name}-{uuid.uuid4()}",
        }
    )
    return await ArtifactRepository(engine).create_artifact(artifact)


async def _get_listed_artifacts(
    engine: AsyncEngine,
    orbit_id: uuid.UUID,
    artifact_ids: list[uuid.UUID],
) -> dict[uuid.UUID, ArtifactListed]:
    artifacts = await ArtifactRepository(engine).get_artifacts_by_ids_in_orbit(
        orbit_id, artifact_ids
    )
    return {artifact.id: artifact for artifact in artifacts}


@pytest.mark.asyncio
async def test_concurrent_deletion_of_the_last_live_artifacts_removes_the_component(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = create_collection
    artifact_repo = ArtifactRepository(data.engine)
    lineage_repo = LineageRepository(data.engine)
    monkeypatch.setattr(ArtifactHandler, "_ArtifactHandler__repository", artifact_repo)
    monkeypatch.setattr(
        ArtifactHandler, "_ArtifactHandler__lineage_repository", lineage_repo
    )
    artifacts = [
        await _create_artifact(data.engine, test_artifact, data.collection.id, name)
        for name in ["last-1", "last-2"]
    ]
    listed = await _get_listed_artifacts(
        data.engine, data.orbit.id, [artifact.id for artifact in artifacts]
    )
    nodes = [
        await lineage_repo.get_or_create_node(data.orbit.id, listed[artifact.id])
        for artifact in artifacts
    ]
    await lineage_repo.create_edges(
        data.orbit.id, [(nodes[0].id, nodes[1].id)], "Test User", LineageVia.API
    )
    handler = ArtifactHandler()

    # Run independently, each deletion could see the other artifact as still
    # live, skip the cleanup, and leave a component nobody can open.
    await asyncio.gather(
        handler._delete_artifact(data.orbit.id, artifacts[0].id),
        handler._delete_artifact(data.orbit.id, artifacts[1].id),
    )

    assert await artifact_repo.get_artifact(artifacts[0].id) is None
    assert await artifact_repo.get_artifact(artifacts[1].id) is None
    assert (
        await lineage_repo.get_nodes_by_ids(data.orbit.id, [node.id for node in nodes])
        == []
    )
