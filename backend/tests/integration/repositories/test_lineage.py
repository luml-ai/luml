import uuid

import pytest
from luml.constants import LINEAGE_MAX_NODES
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.collections import CollectionRepository
from luml.repositories.lineage import LineageRepository
from luml.repositories.orbits import OrbitRepository
from luml.schemas.artifacts import (
    ArtifactCreate,
    ArtifactListed,
    ArtifactUpdate,
)
from luml.schemas.collections import CollectionUpdate
from luml.schemas.lineage import LineageNodeRef, LineageVia
from luml.schemas.orbit import OrbitCreateIn
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.builders import (
    create_artifact,
    create_collection as build_collection,
)
from tests.support.seeds import CollectionFixtureData


@pytest.fixture
def repository(engine: AsyncEngine) -> LineageRepository:
    return LineageRepository(engine)


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
    collection = await build_collection(data.engine, orbit.id, "other")
    return orbit.id, collection.id


class TestLineageRepository:
    @pytest.mark.parametrize(
        "values",
        [
            {},
            {"artifact_id": uuid.uuid4(), "node_id": uuid.uuid4()},
        ],
    )
    def test_validate_lineage_node_ref_rejects_zero_or_two_ids(
        self,
        values: dict[str, uuid.UUID],
    ) -> None:
        with pytest.raises(ValidationError):
            LineageNodeRef.model_validate(values)

    async def test_node_and_edge_lifecycle_rejects_duplicate_self_and_reverse_edges(
        self,
        repository: LineageRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        artifact_repository = ArtifactRepository(engine)
        first = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="first",
            status=new_artifact.status,
        )
        second = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="second",
            status=new_artifact.status,
        )
        listed = await _get_listed_artifacts(
            engine, seeded_collection.orbit.id, [first.id, second.id]
        )

        first_node = await repository.get_or_create_node(
            seeded_collection.orbit.id, listed[first.id]
        )
        same_first_node = await repository.get_or_create_node(
            seeded_collection.orbit.id, listed[first.id]
        )
        second_node = await repository.get_or_create_node(
            seeded_collection.orbit.id, listed[second.id]
        )
        assert same_first_node.id == first_node.id

        edges = await repository.create_edges(
            seeded_collection.orbit.id,
            [(first_node.id, second_node.id)],
            "Test User",
            LineageVia.API,
        )
        edge = edges[0]
        assert edge.to_edge().source == first_node.id
        assert edge.to_edge().target == second_node.id
        assert edge.to_edge().created_via == LineageVia.API

        with pytest.raises(IntegrityError):
            await repository.create_edges(
                seeded_collection.orbit.id,
                [(first_node.id, second_node.id)],
                "Test User",
                LineageVia.UI,
            )
        with pytest.raises(IntegrityError):
            await repository.create_edges(
                seeded_collection.orbit.id,
                [(first_node.id, first_node.id)],
                "Test User",
                LineageVia.UI,
            )
        with pytest.raises(IntegrityError):
            await repository.create_edges(
                seeded_collection.orbit.id,
                [(second_node.id, first_node.id)],
                "Test User",
                LineageVia.UI,
            )

        reverse_lookup = await repository.get_edges_by_pairs(
            seeded_collection.orbit.id, [(second_node.id, first_node.id)]
        )
        assert [found.id for found in reverse_lookup] == [edge.id]

        await repository.update_positions(
            seeded_collection.orbit.id,
            {
                first_node.id: (-320.0, 0.0),
                second_node.id: (0.0, 120.0),
            },
        )
        positioned = await repository.get_nodes_by_ids(
            seeded_collection.orbit.id, [first_node.id, second_node.id]
        )
        coordinates = {node.id: (node.x, node.y) for node in positioned}
        assert coordinates == {
            first_node.id: (-320.0, 0.0),
            second_node.id: (0.0, 120.0),
        }

        await repository.delete_edges(seeded_collection.orbit.id, [edge.id])
        await repository.delete_edgeless_nodes(
            seeded_collection.orbit.id, node_ids=[first_node.id]
        )
        assert [
            node.id
            for node in await repository.get_nodes_by_ids(
                seeded_collection.orbit.id, [first_node.id, second_node.id]
            )
        ] == [second_node.id]
        await repository.delete_edgeless_nodes(seeded_collection.orbit.id, node_ids=[])
        await repository.delete_edgeless_nodes(seeded_collection.orbit.id)
        assert (
            await repository.get_nodes_by_ids(
                seeded_collection.orbit.id, [first_node.id, second_node.id]
            )
            == []
        )

        replacement_first = await repository.get_or_create_node(
            seeded_collection.orbit.id, listed[first.id]
        )
        replacement_second = await repository.get_or_create_node(
            seeded_collection.orbit.id, listed[second.id]
        )
        replacement_edge = (
            await repository.create_edges(
                seeded_collection.orbit.id,
                [(replacement_first.id, replacement_second.id)],
                "Test User",
                LineageVia.API,
            )
        )[0]
        assert replacement_first.id != first_node.id
        assert replacement_second.id != second_node.id
        assert replacement_edge.id != edge.id
        assert await artifact_repository.get_artifact(first.id) is not None

    async def test_lineage_writes_roll_back_with_caller_transaction(
        self,
        repository: LineageRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        first = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="transaction-first",
            status=new_artifact.status,
        )
        second = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="transaction-second",
            status=new_artifact.status,
        )
        listed = await _get_listed_artifacts(
            engine, seeded_collection.orbit.id, [first.id, second.id]
        )

        async def write_then_fail() -> None:
            async with repository.transaction() as session:
                first_node = await repository.get_or_create_node(
                    seeded_collection.orbit.id, listed[first.id], session
                )
                second_node = await repository.get_or_create_node(
                    seeded_collection.orbit.id, listed[second.id], session
                )
                edges = await repository.create_edges(
                    seeded_collection.orbit.id,
                    [(first_node.id, second_node.id)],
                    "Test User",
                    LineageVia.API,
                    session,
                )
                await repository.update_positions(
                    seeded_collection.orbit.id, {first_node.id: (10.0, 20.0)}, session
                )
                assert await repository.get_edges_by_ids(
                    seeded_collection.orbit.id, [edges[0].id], session
                )
                raise RuntimeError("roll back lineage changes")

        with pytest.raises(RuntimeError, match="roll back lineage changes"):
            await write_then_fail()

        assert (
            await repository.get_nodes_by_artifact_ids(
                seeded_collection.orbit.id, [first.id, second.id]
            )
            == []
        )

    async def test_lineage_queries_and_writes_are_scoped_to_orbit(
        self,
        repository: LineageRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        other_orbit_id, other_collection_id = await _create_other_orbit_collection(
            seeded_collection
        )
        current_artifacts = [
            await create_artifact(
                engine,
                new_artifact,
                seeded_collection.collection.id,
                name=f"current-{index}",
                status=new_artifact.status,
            )
            for index in range(2)
        ]
        other_artifacts = [
            await create_artifact(
                engine,
                new_artifact,
                other_collection_id,
                name=f"other-{index}",
                status=new_artifact.status,
            )
            for index in range(2)
        ]
        all_ids = [artifact.id for artifact in [*current_artifacts, *other_artifacts]]
        artifact_repository = ArtifactRepository(engine)
        current_listed = await artifact_repository.get_artifacts_by_ids_in_orbit(
            seeded_collection.orbit.id, all_ids
        )
        other_listed = await artifact_repository.get_artifacts_by_ids_in_orbit(
            other_orbit_id, all_ids
        )
        assert {artifact.id for artifact in current_listed} == {
            artifact.id for artifact in current_artifacts
        }
        assert {artifact.id for artifact in other_listed} == {
            artifact.id for artifact in other_artifacts
        }

        current_nodes = [
            await repository.get_or_create_node(seeded_collection.orbit.id, artifact)
            for artifact in current_listed
        ]
        other_nodes = [
            await repository.get_or_create_node(other_orbit_id, artifact)
            for artifact in other_listed
        ]
        current_edge = (
            await repository.create_edges(
                seeded_collection.orbit.id,
                [(current_nodes[0].id, current_nodes[1].id)],
                "Test User",
                LineageVia.API,
            )
        )[0]
        other_edge = (
            await repository.create_edges(
                other_orbit_id,
                [(other_nodes[0].id, other_nodes[1].id)],
                "Test User",
                LineageVia.API,
            )
        )[0]

        found_nodes = await repository.get_nodes_by_ids(
            seeded_collection.orbit.id, [current_nodes[0].id, other_nodes[0].id]
        )
        found_edges = await repository.get_edges_by_ids(
            seeded_collection.orbit.id, [current_edge.id, other_edge.id]
        )
        assert [node.id for node in found_nodes] == [current_nodes[0].id]
        assert [edge.id for edge in found_edges] == [current_edge.id]

        await repository.update_positions(
            seeded_collection.orbit.id, {other_nodes[0].id: (99.0, 99.0)}
        )
        unchanged_other_node = (
            await repository.get_nodes_by_ids(other_orbit_id, [other_nodes[0].id])
        )[0]
        assert unchanged_other_node.x is None
        assert unchanged_other_node.y is None

        await repository.delete_edges(seeded_collection.orbit.id, [other_edge.id])
        assert await repository.get_edges_by_ids(other_orbit_id, [other_edge.id])

    async def test_refresh_node_copy_keeps_renamed_snapshot_after_artifact_deletion(
        self,
        repository: LineageRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        artifact_repository = ArtifactRepository(engine)
        first = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="copy-first",
            status=new_artifact.status,
        )
        second = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="copy-second",
            status=new_artifact.status,
        )
        listed = await _get_listed_artifacts(
            engine, seeded_collection.orbit.id, [first.id, second.id]
        )
        first_node = await repository.get_or_create_node(
            seeded_collection.orbit.id, listed[first.id]
        )
        second_node = await repository.get_or_create_node(
            seeded_collection.orbit.id, listed[second.id]
        )
        await repository.create_edges(
            seeded_collection.orbit.id,
            [(first_node.id, second_node.id)],
            "Test User",
            LineageVia.API,
        )

        await artifact_repository.update_artifact(
            first.id,
            seeded_collection.collection.id,
            ArtifactUpdate(id=first.id, name="renamed-artifact"),
        )
        await CollectionRepository(engine).update_collection(
            seeded_collection.collection.id,
            seeded_collection.orbit.id,
            CollectionUpdate(
                id=seeded_collection.collection.id, name="renamed-collection"
            ),
        )
        await repository.refresh_node_copy(first.id)
        await artifact_repository.delete_artifact(first.id)

        detached_node = (
            await repository.get_nodes_by_ids(
                seeded_collection.orbit.id, [first_node.id]
            )
        )[0]
        assert detached_node.artifact_id is None
        assert detached_node.name == "renamed-artifact"
        assert detached_node.collection_name == "renamed-collection"

    async def test_traverse_respects_depth_and_terminates_on_cycle(
        self,
        repository: LineageRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        artifacts = [
            await create_artifact(
                engine,
                new_artifact,
                seeded_collection.collection.id,
                name=name,
                status=new_artifact.status,
            )
            for name in ["dataset", "experiment", "model", "output"]
        ]
        listed = await _get_listed_artifacts(
            engine, seeded_collection.orbit.id, [artifact.id for artifact in artifacts]
        )
        nodes = [
            await repository.get_or_create_node(
                seeded_collection.orbit.id, listed[artifact.id]
            )
            for artifact in artifacts
        ]
        edges = await repository.create_edges(
            seeded_collection.orbit.id,
            [
                (nodes[0].id, nodes[1].id),
                (nodes[1].id, nodes[2].id),
                (nodes[2].id, nodes[3].id),
            ],
            "Test User",
            LineageVia.API,
        )

        depth_one_nodes, depth_one_edges, truncated = await repository.traverse(
            seeded_collection.orbit.id, nodes[2].id, 1
        )
        assert [node.id for node in depth_one_nodes] == [
            nodes[2].id,
            nodes[1].id,
            nodes[3].id,
        ]
        assert {edge.id for edge in depth_one_edges} == {edges[1].id, edges[2].id}
        assert truncated is False

        depth_two_nodes, depth_two_edges, truncated = await repository.traverse(
            seeded_collection.orbit.id, nodes[2].id, 2
        )
        assert {node.id for node in depth_two_nodes} == {node.id for node in nodes}
        assert {edge.id for edge in depth_two_edges} == {edge.id for edge in edges}
        assert truncated is False

        whole_nodes, whole_edges, truncated = await repository.traverse(
            seeded_collection.orbit.id, nodes[0].id, None
        )
        assert {node.id for node in whole_nodes} == {node.id for node in nodes}
        assert {edge.id for edge in whole_edges} == {edge.id for edge in edges}
        assert truncated is False

        cycle_edge = (
            await repository.create_edges(
                seeded_collection.orbit.id,
                [(nodes[3].id, nodes[0].id)],
                "Test User",
                LineageVia.API,
            )
        )[0]
        cycle_nodes, cycle_edges, truncated = await repository.traverse(
            seeded_collection.orbit.id, nodes[0].id, 5
        )
        assert len(cycle_nodes) == 4
        assert {edge.id for edge in cycle_edges} == {
            *(edge.id for edge in edges),
            cycle_edge.id,
        }
        assert truncated is False

    async def test_traverse_caps_nodes_at_every_level_keeping_earliest_connections(
        self,
        repository: LineageRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
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
            await create_artifact(
                engine,
                new_artifact,
                seeded_collection.collection.id,
                name=name,
                status=new_artifact.status,
            )
            for name in names
        ]
        listed = await _get_listed_artifacts(
            engine, seeded_collection.orbit.id, [artifact.id for artifact in artifacts]
        )
        nodes = [
            await repository.get_or_create_node(
                seeded_collection.orbit.id, listed[artifact.id]
            )
            for artifact in artifacts
        ]
        await repository.create_edges(
            seeded_collection.orbit.id,
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
        for wide_neighbour in nodes[7:]:
            await repository.create_edges(
                seeded_collection.orbit.id,
                [(nodes[6].id, wide_neighbour.id)],
                "Test User",
                LineageVia.API,
            )

        limited_nodes, limited_edges, truncated = await repository.traverse(
            seeded_collection.orbit.id, nodes[0].id, 3
        )
        assert [node.id for node in limited_nodes] == [
            nodes[0].id,
            nodes[1].id,
            nodes[2].id,
            nodes[3].id,
        ]
        assert len(limited_edges) == 3
        assert truncated is True

        wide_nodes, wide_edges, truncated = await repository.traverse(
            seeded_collection.orbit.id, nodes[6].id, 2
        )
        assert [node.id for node in wide_nodes] == [
            nodes[6].id,
            nodes[7].id,
            nodes[8].id,
            nodes[9].id,
        ]
        assert len(wide_edges) == 3
        assert truncated is True

        unbounded_nodes, _, truncated = await repository.traverse(
            seeded_collection.orbit.id, nodes[0].id, None
        )
        assert [node.id for node in unbounded_nodes] == [node.id for node in nodes[:4]]
        assert truncated is True

    async def test_traverse_returns_node_cap_when_focal_node_has_more_neighbours(
        self,
        repository: LineageRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        artifacts = [
            await create_artifact(
                engine,
                new_artifact,
                seeded_collection.collection.id,
                name=f"artifact-{index}",
                status=new_artifact.status,
            )
            for index in range(LINEAGE_MAX_NODES + 1)
        ]
        listed = await _get_listed_artifacts(
            engine, seeded_collection.orbit.id, [artifact.id for artifact in artifacts]
        )
        nodes = [
            await repository.get_or_create_node(
                seeded_collection.orbit.id, listed[artifact.id]
            )
            for artifact in artifacts
        ]
        focal = nodes[0]
        await repository.create_edges(
            seeded_collection.orbit.id,
            [(focal.id, neighbour.id) for neighbour in nodes[1:]],
            "Test User",
            LineageVia.API,
        )

        result_nodes, result_edges, truncated = await repository.traverse(
            seeded_collection.orbit.id, focal.id, None
        )

        assert len(result_nodes) == LINEAGE_MAX_NODES
        assert result_nodes[0].id == focal.id
        assert len(result_edges) == LINEAGE_MAX_NODES - 1
        assert truncated is True

    async def test_delete_unreachable_deleted_nodes_keeps_chain_of_live_artifact(
        self,
        repository: LineageRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        artifact_repository = ArtifactRepository(engine)
        artifacts = [
            await create_artifact(
                engine,
                new_artifact,
                seeded_collection.collection.id,
                name=name,
                status=new_artifact.status,
            )
            for name in ["live", "gone-1", "gone-2", "island-1", "island-2"]
        ]
        listed = await _get_listed_artifacts(
            engine, seeded_collection.orbit.id, [artifact.id for artifact in artifacts]
        )
        nodes = [
            await repository.get_or_create_node(
                seeded_collection.orbit.id, listed[artifact.id]
            )
            for artifact in artifacts
        ]
        await repository.create_edges(
            seeded_collection.orbit.id,
            [
                (nodes[0].id, nodes[1].id),
                (nodes[1].id, nodes[2].id),
                (nodes[3].id, nodes[4].id),
            ],
            "Test User",
            LineageVia.API,
        )
        for artifact in artifacts[1:]:
            await artifact_repository.delete_artifact(artifact.id)

        await repository.delete_unreachable_deleted_nodes(seeded_collection.orbit.id)

        remaining = await repository.get_nodes_by_ids(
            seeded_collection.orbit.id, [node.id for node in nodes]
        )
        assert {node.id for node in remaining} == {node.id for node in nodes[:3]}
        assert all(node.artifact_id is None for node in remaining[1:])

        await artifact_repository.delete_artifact(artifacts[0].id)
        await repository.delete_unreachable_deleted_nodes(seeded_collection.orbit.id)
        assert (
            await repository.get_nodes_by_ids(
                seeded_collection.orbit.id, [node.id for node in nodes]
            )
            == []
        )

    async def test_get_node_by_artifact_id_returns_none_outside_orbit(
        self,
        repository: LineageRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        artifact = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="lookup",
            status=new_artifact.status,
        )
        listed = await _get_listed_artifacts(
            engine, seeded_collection.orbit.id, [artifact.id]
        )
        node = await repository.get_or_create_node(
            seeded_collection.orbit.id, listed[artifact.id]
        )
        other_orbit_id, _ = await _create_other_orbit_collection(seeded_collection)

        found = await repository.get_node_by_artifact_id(
            seeded_collection.orbit.id, artifact.id
        )

        assert found is not None
        assert found.id == node.id
        assert (
            await repository.get_node_by_artifact_id(other_orbit_id, artifact.id)
            is None
        )
        assert (
            await repository.get_node_by_artifact_id(
                seeded_collection.orbit.id, uuid.uuid7()
            )
            is None
        )

    async def test_empty_lookups_return_empty_and_empty_writes_do_not_raise(
        self,
        repository: LineageRepository,
        seeded_collection: CollectionFixtureData,
    ) -> None:
        orbit_id = seeded_collection.orbit.id

        assert await repository.get_nodes_by_ids(orbit_id, []) == []
        assert await repository.get_nodes_by_artifact_ids(orbit_id, []) == []
        assert (
            await repository.create_edges(orbit_id, [], "Test User", LineageVia.API)
            == []
        )
        assert await repository.get_edges_by_ids(orbit_id, []) == []
        assert await repository.get_edges_by_pairs(orbit_id, []) == []
        await repository.delete_edges(orbit_id, [])
        await repository.update_positions(orbit_id, {})

    async def test_refresh_node_copy_with_unknown_artifact_does_not_raise(
        self, repository: LineageRepository
    ) -> None:
        await repository.refresh_node_copy(uuid.uuid7())

    async def test_traverse_rejects_non_positive_depth_and_unknown_focal_node(
        self,
        repository: LineageRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        artifact = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="focal",
            status=new_artifact.status,
        )
        listed = await _get_listed_artifacts(
            engine, seeded_collection.orbit.id, [artifact.id]
        )
        node = await repository.get_or_create_node(
            seeded_collection.orbit.id, listed[artifact.id]
        )
        other_orbit_id, _ = await _create_other_orbit_collection(seeded_collection)

        with pytest.raises(ValueError, match="depth must be positive"):
            await repository.traverse(seeded_collection.orbit.id, node.id, 0)

        assert await repository.traverse(
            seeded_collection.orbit.id, uuid.uuid7(), None
        ) == (
            [],
            [],
            False,
        )
        assert await repository.traverse(other_orbit_id, node.id, None) == (
            [],
            [],
            False,
        )
