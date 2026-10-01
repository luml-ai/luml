import uuid

import pytest
from luml.constants import LINEAGE_MAX_NODES
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.collections import CollectionRepository
from luml.repositories.lineage import LineageRepository
from luml.repositories.orbits import OrbitRepository
from luml.schemas.artifacts import (
    Artifact,
    ArtifactCreate,
    ArtifactListed,
    ArtifactUpdate,
)
from luml.schemas.collections import CollectionCreate, CollectionType, CollectionUpdate
from luml.schemas.lineage import LineageNodeRef, LineageVia
from luml.schemas.orbit import OrbitCreateIn
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
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


async def _create_other_orbit_collection(
    data: CollectionFixtureData,
) -> tuple[uuid.UUID, uuid.UUID]:
    orbit = await OrbitRepository(data.engine).create_orbit(
        data.organization.id,
        OrbitCreateIn(
            name=f"other-{uuid.uuid4()}",
            bucket_secret_id=data.bucket_secret.id,
        ),
    )
    assert orbit is not None
    collection = await CollectionRepository(data.engine).create_collection(
        CollectionCreate(
            orbit_id=orbit.id,
            description="other",
            name="other",
            type=CollectionType.MODEL,
            tags=[],
        )
    )
    return orbit.id, collection.id


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"artifact_id": uuid.uuid4(), "node_id": uuid.uuid4()},
    ],
)
def test_lineage_node_reference_requires_exactly_one_id(
    values: dict[str, uuid.UUID],
) -> None:
    with pytest.raises(ValidationError):
        LineageNodeRef.model_validate(values)


@pytest.mark.asyncio
async def test_node_and_edge_lifecycle_and_constraints(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
) -> None:
    data = create_collection
    artifact_repo = ArtifactRepository(data.engine)
    lineage_repo = LineageRepository(data.engine)
    first = await _create_artifact(
        data.engine, test_artifact, data.collection.id, "first"
    )
    second = await _create_artifact(
        data.engine, test_artifact, data.collection.id, "second"
    )
    listed = await _get_listed_artifacts(
        data.engine, data.orbit.id, [first.id, second.id]
    )

    first_node = await lineage_repo.get_or_create_node(data.orbit.id, listed[first.id])
    same_first_node = await lineage_repo.get_or_create_node(
        data.orbit.id, listed[first.id]
    )
    second_node = await lineage_repo.get_or_create_node(
        data.orbit.id, listed[second.id]
    )
    assert same_first_node.id == first_node.id

    edges = await lineage_repo.create_edges(
        data.orbit.id,
        [(first_node.id, second_node.id)],
        "Test User",
        LineageVia.API,
    )
    edge = edges[0]
    assert edge.to_edge().source == first_node.id
    assert edge.to_edge().target == second_node.id
    assert edge.to_edge().created_via == LineageVia.API

    with pytest.raises(IntegrityError):
        await lineage_repo.create_edges(
            data.orbit.id,
            [(first_node.id, second_node.id)],
            "Test User",
            LineageVia.UI,
        )
    with pytest.raises(IntegrityError):
        await lineage_repo.create_edges(
            data.orbit.id,
            [(first_node.id, first_node.id)],
            "Test User",
            LineageVia.UI,
        )
    # The reverse direction is rejected by the database as well, so a lost
    # race between two requests cannot leave a two-node cycle behind.
    with pytest.raises(IntegrityError):
        await lineage_repo.create_edges(
            data.orbit.id,
            [(second_node.id, first_node.id)],
            "Test User",
            LineageVia.UI,
        )

    reverse_lookup = await lineage_repo.get_edges_by_pairs(
        data.orbit.id, [(second_node.id, first_node.id)]
    )
    assert [found.id for found in reverse_lookup] == [edge.id]

    await lineage_repo.update_positions(
        data.orbit.id,
        {
            first_node.id: (-320.0, 0.0),
            second_node.id: (0.0, 120.0),
        },
    )
    positioned = await lineage_repo.get_nodes_by_ids(
        data.orbit.id, [first_node.id, second_node.id]
    )
    coordinates = {node.id: (node.x, node.y) for node in positioned}
    assert coordinates == {
        first_node.id: (-320.0, 0.0),
        second_node.id: (0.0, 120.0),
    }

    await lineage_repo.delete_edges(data.orbit.id, [edge.id])
    await lineage_repo.delete_edgeless_nodes(data.orbit.id, node_ids=[first_node.id])
    assert [
        node.id
        for node in await lineage_repo.get_nodes_by_ids(
            data.orbit.id, [first_node.id, second_node.id]
        )
    ] == [second_node.id]
    await lineage_repo.delete_edgeless_nodes(data.orbit.id, node_ids=[])
    await lineage_repo.delete_edgeless_nodes(data.orbit.id)
    assert (
        await lineage_repo.get_nodes_by_ids(
            data.orbit.id, [first_node.id, second_node.id]
        )
        == []
    )

    replacement_first = await lineage_repo.get_or_create_node(
        data.orbit.id, listed[first.id]
    )
    replacement_second = await lineage_repo.get_or_create_node(
        data.orbit.id, listed[second.id]
    )
    replacement_edge = (
        await lineage_repo.create_edges(
            data.orbit.id,
            [(replacement_first.id, replacement_second.id)],
            "Test User",
            LineageVia.API,
        )
    )[0]
    assert replacement_first.id != first_node.id
    assert replacement_second.id != second_node.id
    assert replacement_edge.id != edge.id
    assert await artifact_repo.get_artifact(first.id) is not None


@pytest.mark.asyncio
async def test_repository_operations_share_a_caller_transaction(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
) -> None:
    data = create_collection
    lineage_repo = LineageRepository(data.engine)
    first = await _create_artifact(
        data.engine, test_artifact, data.collection.id, "transaction-first"
    )
    second = await _create_artifact(
        data.engine, test_artifact, data.collection.id, "transaction-second"
    )
    listed = await _get_listed_artifacts(
        data.engine, data.orbit.id, [first.id, second.id]
    )

    async def write_then_fail() -> None:
        async with lineage_repo.transaction() as session:
            first_node = await lineage_repo.get_or_create_node(
                data.orbit.id, listed[first.id], session
            )
            second_node = await lineage_repo.get_or_create_node(
                data.orbit.id, listed[second.id], session
            )
            edges = await lineage_repo.create_edges(
                data.orbit.id,
                [(first_node.id, second_node.id)],
                "Test User",
                LineageVia.API,
                session,
            )
            await lineage_repo.update_positions(
                data.orbit.id, {first_node.id: (10.0, 20.0)}, session
            )
            assert await lineage_repo.get_edges_by_ids(
                data.orbit.id, [edges[0].id], session
            )
            raise RuntimeError("roll back lineage changes")

    with pytest.raises(RuntimeError, match="roll back lineage changes"):
        await write_then_fail()

    assert (
        await lineage_repo.get_nodes_by_artifact_ids(
            data.orbit.id, [first.id, second.id]
        )
        == []
    )


@pytest.mark.asyncio
async def test_repository_queries_and_writes_are_orbit_scoped(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
) -> None:
    data = create_collection
    other_orbit_id, other_collection_id = await _create_other_orbit_collection(data)
    current_artifacts = [
        await _create_artifact(
            data.engine, test_artifact, data.collection.id, f"current-{index}"
        )
        for index in range(2)
    ]
    other_artifacts = [
        await _create_artifact(
            data.engine, test_artifact, other_collection_id, f"other-{index}"
        )
        for index in range(2)
    ]
    all_ids = [artifact.id for artifact in [*current_artifacts, *other_artifacts]]
    artifact_repo = ArtifactRepository(data.engine)
    current_listed = await artifact_repo.get_artifacts_by_ids_in_orbit(
        data.orbit.id, all_ids
    )
    other_listed = await artifact_repo.get_artifacts_by_ids_in_orbit(
        other_orbit_id, all_ids
    )
    assert {artifact.id for artifact in current_listed} == {
        artifact.id for artifact in current_artifacts
    }
    assert {artifact.id for artifact in other_listed} == {
        artifact.id for artifact in other_artifacts
    }

    lineage_repo = LineageRepository(data.engine)
    current_nodes = [
        await lineage_repo.get_or_create_node(data.orbit.id, artifact)
        for artifact in current_listed
    ]
    other_nodes = [
        await lineage_repo.get_or_create_node(other_orbit_id, artifact)
        for artifact in other_listed
    ]
    current_edge = (
        await lineage_repo.create_edges(
            data.orbit.id,
            [(current_nodes[0].id, current_nodes[1].id)],
            "Test User",
            LineageVia.API,
        )
    )[0]
    other_edge = (
        await lineage_repo.create_edges(
            other_orbit_id,
            [(other_nodes[0].id, other_nodes[1].id)],
            "Test User",
            LineageVia.API,
        )
    )[0]

    found_nodes = await lineage_repo.get_nodes_by_ids(
        data.orbit.id, [current_nodes[0].id, other_nodes[0].id]
    )
    found_edges = await lineage_repo.get_edges_by_ids(
        data.orbit.id, [current_edge.id, other_edge.id]
    )
    assert [node.id for node in found_nodes] == [current_nodes[0].id]
    assert [edge.id for edge in found_edges] == [current_edge.id]

    await lineage_repo.update_positions(
        data.orbit.id, {other_nodes[0].id: (99.0, 99.0)}
    )
    unchanged_other_node = (
        await lineage_repo.get_nodes_by_ids(other_orbit_id, [other_nodes[0].id])
    )[0]
    assert unchanged_other_node.x is None
    assert unchanged_other_node.y is None

    await lineage_repo.delete_edges(data.orbit.id, [other_edge.id])
    assert await lineage_repo.get_edges_by_ids(other_orbit_id, [other_edge.id])


@pytest.mark.asyncio
async def test_refresh_node_copy_and_artifact_reference_deletion(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
) -> None:
    data = create_collection
    artifact_repo = ArtifactRepository(data.engine)
    lineage_repo = LineageRepository(data.engine)
    first = await _create_artifact(
        data.engine, test_artifact, data.collection.id, "copy-first"
    )
    second = await _create_artifact(
        data.engine, test_artifact, data.collection.id, "copy-second"
    )
    listed = await _get_listed_artifacts(
        data.engine, data.orbit.id, [first.id, second.id]
    )
    first_node = await lineage_repo.get_or_create_node(data.orbit.id, listed[first.id])
    second_node = await lineage_repo.get_or_create_node(
        data.orbit.id, listed[second.id]
    )
    await lineage_repo.create_edges(
        data.orbit.id,
        [(first_node.id, second_node.id)],
        "Test User",
        LineageVia.API,
    )

    await artifact_repo.update_artifact(
        first.id,
        data.collection.id,
        ArtifactUpdate(id=first.id, name="renamed-artifact"),
    )
    await CollectionRepository(data.engine).update_collection(
        data.collection.id,
        data.orbit.id,
        CollectionUpdate(id=data.collection.id, name="renamed-collection"),
    )
    await lineage_repo.refresh_node_copy(first.id)
    await artifact_repo.delete_artifact(first.id)

    detached_node = (
        await lineage_repo.get_nodes_by_ids(data.orbit.id, [first_node.id])
    )[0]
    assert detached_node.artifact_id is None
    assert detached_node.name == "renamed-artifact"
    assert detached_node.collection_name == "renamed-collection"


@pytest.mark.asyncio
async def test_traversal_depth_and_cycle(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
) -> None:
    data = create_collection
    artifacts = [
        await _create_artifact(data.engine, test_artifact, data.collection.id, name)
        for name in ["dataset", "experiment", "model", "output"]
    ]
    listed = await _get_listed_artifacts(
        data.engine, data.orbit.id, [artifact.id for artifact in artifacts]
    )
    lineage_repo = LineageRepository(data.engine)
    nodes = [
        await lineage_repo.get_or_create_node(data.orbit.id, listed[artifact.id])
        for artifact in artifacts
    ]
    edges = await lineage_repo.create_edges(
        data.orbit.id,
        [
            (nodes[0].id, nodes[1].id),
            (nodes[1].id, nodes[2].id),
            (nodes[2].id, nodes[3].id),
        ],
        "Test User",
        LineageVia.API,
    )

    depth_one_nodes, depth_one_edges, truncated = await lineage_repo.traverse(
        data.orbit.id, nodes[2].id, 1
    )
    assert [node.id for node in depth_one_nodes] == [
        nodes[2].id,
        nodes[1].id,
        nodes[3].id,
    ]
    assert {edge.id for edge in depth_one_edges} == {edges[1].id, edges[2].id}
    assert truncated is False

    depth_two_nodes, depth_two_edges, truncated = await lineage_repo.traverse(
        data.orbit.id, nodes[2].id, 2
    )
    assert {node.id for node in depth_two_nodes} == {node.id for node in nodes}
    assert {edge.id for edge in depth_two_edges} == {edge.id for edge in edges}
    assert truncated is False

    whole_nodes, whole_edges, truncated = await lineage_repo.traverse(
        data.orbit.id, nodes[0].id, None
    )
    assert {node.id for node in whole_nodes} == {node.id for node in nodes}
    assert {edge.id for edge in whole_edges} == {edge.id for edge in edges}
    assert truncated is False

    cycle_edge = (
        await lineage_repo.create_edges(
            data.orbit.id,
            [(nodes[3].id, nodes[0].id)],
            "Test User",
            LineageVia.API,
        )
    )[0]
    cycle_nodes, cycle_edges, truncated = await lineage_repo.traverse(
        data.orbit.id, nodes[0].id, 5
    )
    assert len(cycle_nodes) == 4
    assert {edge.id for edge in cycle_edges} == {
        *(edge.id for edge in edges),
        cycle_edge.id,
    }
    assert truncated is False


@pytest.mark.asyncio
async def test_traversal_node_limit_applies_to_every_level(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = create_collection
    monkeypatch.setattr("luml.repositories.lineage.LINEAGE_MAX_NODES", 4)
    names = [
        "focal",
        "near-1",
        "near-2",
        "near-3",
        "far-1",
        "far-2",
        "wide",
        "wide-1",
        "wide-2",
        "wide-3",
        "wide-4",
        "wide-5",
    ]
    artifacts = [
        await _create_artifact(data.engine, test_artifact, data.collection.id, name)
        for name in names
    ]
    listed = await _get_listed_artifacts(
        data.engine, data.orbit.id, [artifact.id for artifact in artifacts]
    )
    lineage_repo = LineageRepository(data.engine)
    nodes = [
        await lineage_repo.get_or_create_node(data.orbit.id, listed[artifact.id])
        for artifact in artifacts
    ]
    await lineage_repo.create_edges(
        data.orbit.id,
        [
            (nodes[0].id, nodes[1].id),
            (nodes[0].id, nodes[2].id),
            (nodes[0].id, nodes[3].id),
            (nodes[1].id, nodes[4].id),
            (nodes[2].id, nodes[5].id),
        ],
        "Test User",
        LineageVia.API,
    )
    # The wide node gets its neighbours one edge at a time, so their order of
    # discovery is fixed by the edge timestamps rather than by chance.
    for wide_neighbour in nodes[7:]:
        await lineage_repo.create_edges(
            data.orbit.id,
            [(nodes[6].id, wide_neighbour.id)],
            "Test User",
            LineageVia.API,
        )

    limited_nodes, limited_edges, truncated = await lineage_repo.traverse(
        data.orbit.id, nodes[0].id, 3
    )
    assert [node.id for node in limited_nodes] == [
        nodes[0].id,
        nodes[1].id,
        nodes[2].id,
        nodes[3].id,
    ]
    assert len(limited_edges) == 3
    assert truncated is True

    # A focal node with more direct neighbours than the cap allows is cut at
    # the cap like any other level: the earliest connections are kept.
    wide_nodes, wide_edges, truncated = await lineage_repo.traverse(
        data.orbit.id, nodes[6].id, 2
    )
    assert [node.id for node in wide_nodes] == [
        nodes[6].id,
        nodes[7].id,
        nodes[8].id,
        nodes[9].id,
    ]
    assert len(wide_edges) == 3
    assert truncated is True

    unbounded_nodes, _, truncated = await lineage_repo.traverse(
        data.orbit.id, nodes[0].id, None
    )
    assert [node.id for node in unbounded_nodes] == [node.id for node in nodes[:4]]
    assert truncated is True


@pytest.mark.asyncio
async def test_traversal_returns_at_most_the_node_cap_for_a_high_degree_focal_node(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
) -> None:
    data = create_collection
    lineage_repo = LineageRepository(data.engine)
    artifacts = [
        await _create_artifact(
            data.engine, test_artifact, data.collection.id, f"artifact-{index}"
        )
        for index in range(LINEAGE_MAX_NODES + 1)
    ]
    listed = await _get_listed_artifacts(
        data.engine, data.orbit.id, [artifact.id for artifact in artifacts]
    )
    nodes = [
        await lineage_repo.get_or_create_node(data.orbit.id, listed[artifact.id])
        for artifact in artifacts
    ]
    focal = nodes[0]
    await lineage_repo.create_edges(
        data.orbit.id,
        [(focal.id, neighbour.id) for neighbour in nodes[1:]],
        "Test User",
        LineageVia.API,
    )

    result_nodes, result_edges, truncated = await lineage_repo.traverse(
        data.orbit.id, focal.id, None
    )

    assert len(result_nodes) == LINEAGE_MAX_NODES
    assert result_nodes[0].id == focal.id
    assert len(result_edges) == LINEAGE_MAX_NODES - 1
    assert truncated is True


@pytest.mark.asyncio
async def test_unreachable_deleted_components_are_removed(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
) -> None:
    data = create_collection
    artifact_repo = ArtifactRepository(data.engine)
    lineage_repo = LineageRepository(data.engine)
    artifacts = [
        await _create_artifact(data.engine, test_artifact, data.collection.id, name)
        for name in ["live", "gone-1", "gone-2", "island-1", "island-2"]
    ]
    listed = await _get_listed_artifacts(
        data.engine, data.orbit.id, [artifact.id for artifact in artifacts]
    )
    nodes = [
        await lineage_repo.get_or_create_node(data.orbit.id, listed[artifact.id])
        for artifact in artifacts
    ]
    await lineage_repo.create_edges(
        data.orbit.id,
        [
            (nodes[0].id, nodes[1].id),
            (nodes[1].id, nodes[2].id),
            (nodes[3].id, nodes[4].id),
        ],
        "Test User",
        LineageVia.API,
    )
    for artifact in artifacts[1:]:
        await artifact_repo.delete_artifact(artifact.id)

    await lineage_repo.delete_unreachable_deleted_nodes(data.orbit.id)

    remaining = await lineage_repo.get_nodes_by_ids(
        data.orbit.id, [node.id for node in nodes]
    )
    # The chain hanging off the live artifact stays, the island is gone.
    assert {node.id for node in remaining} == {node.id for node in nodes[:3]}
    assert all(node.artifact_id is None for node in remaining[1:])

    await artifact_repo.delete_artifact(artifacts[0].id)
    await lineage_repo.delete_unreachable_deleted_nodes(data.orbit.id)
    assert (
        await lineage_repo.get_nodes_by_ids(data.orbit.id, [node.id for node in nodes])
        == []
    )


@pytest.mark.asyncio
async def test_get_node_by_artifact_id_is_orbit_scoped(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
) -> None:
    data = create_collection
    lineage_repo = LineageRepository(data.engine)
    artifact = await _create_artifact(
        data.engine, test_artifact, data.collection.id, "lookup"
    )
    listed = await _get_listed_artifacts(data.engine, data.orbit.id, [artifact.id])
    node = await lineage_repo.get_or_create_node(data.orbit.id, listed[artifact.id])
    other_orbit_id, _ = await _create_other_orbit_collection(data)

    found = await lineage_repo.get_node_by_artifact_id(data.orbit.id, artifact.id)

    assert found is not None
    assert found.id == node.id
    assert (
        await lineage_repo.get_node_by_artifact_id(other_orbit_id, artifact.id) is None
    )
    assert (
        await lineage_repo.get_node_by_artifact_id(data.orbit.id, uuid.uuid7()) is None
    )


@pytest.mark.asyncio
async def test_empty_lookups_and_writes_are_no_ops(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    lineage_repo = LineageRepository(data.engine)
    orbit_id = data.orbit.id

    assert await lineage_repo.get_nodes_by_ids(orbit_id, []) == []
    assert await lineage_repo.get_nodes_by_artifact_ids(orbit_id, []) == []
    assert (
        await lineage_repo.create_edges(orbit_id, [], "Test User", LineageVia.API) == []
    )
    assert await lineage_repo.get_edges_by_ids(orbit_id, []) == []
    assert await lineage_repo.get_edges_by_pairs(orbit_id, []) == []
    await lineage_repo.delete_edges(orbit_id, [])
    await lineage_repo.update_positions(orbit_id, {})


@pytest.mark.asyncio
async def test_refresh_node_copy_ignores_an_unknown_artifact(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection

    await LineageRepository(data.engine).refresh_node_copy(uuid.uuid7())


@pytest.mark.asyncio
async def test_traverse_rejects_a_non_positive_depth_and_an_unknown_focal_node(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
) -> None:
    data = create_collection
    lineage_repo = LineageRepository(data.engine)
    artifact = await _create_artifact(
        data.engine, test_artifact, data.collection.id, "focal"
    )
    listed = await _get_listed_artifacts(data.engine, data.orbit.id, [artifact.id])
    node = await lineage_repo.get_or_create_node(data.orbit.id, listed[artifact.id])
    other_orbit_id, _ = await _create_other_orbit_collection(data)

    with pytest.raises(ValueError, match="depth must be positive"):
        await lineage_repo.traverse(data.orbit.id, node.id, 0)

    assert await lineage_repo.traverse(data.orbit.id, uuid.uuid7(), None) == (
        [],
        [],
        False,
    )
    assert await lineage_repo.traverse(other_orbit_id, node.id, None) == (
        [],
        [],
        False,
    )
