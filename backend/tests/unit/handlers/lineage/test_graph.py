import pytest
from luml.handlers.lineage import LineageHandler
from luml.infra.exceptions import ArtifactNotFoundError, InsufficientPermissionsError
from luml.schemas.artifacts import ArtifactType
from luml.schemas.lineage import LineageVia
from luml.schemas.permissions import Action, Resource

from tests.support.ids import (
    ARTIFACT_ID,
    EDGE_ID,
    NODE_A_ID,
    NODE_B_ID,
    ORBIT_ID,
    ORGANIZATION_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.lineage.conftest import _artifact, _edge, _node


class TestLineageGraph:
    async def test_get_graph_returns_empty_graph_when_artifact_has_no_lineage_node(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        focal = _artifact(ARTIFACT_ID, "A")
        mocks.artifact_repository.get_artifacts_by_ids_in_orbit.return_value = [focal]

        result = await mocks.handler.get_graph(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, ARTIFACT_ID, 2
        )

        assert result.nodes == []
        assert result.edges == []
        assert result.focal_artifact_id == ARTIFACT_ID
        assert result.depth == 2
        assert result.truncated is False
        mocks.repository.traverse.assert_not_awaited()
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.ARTIFACT,
            Action.READ,
            ORBIT_ID,
        )

    async def test_get_graph_returns_live_artifact_data_and_deleted_node_copies(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        focal = _artifact(
            ARTIFACT_ID,
            "Live name",
            artifact_type=ArtifactType.EXPERIMENT,
            collection_name="Experiments",
        )
        focal_node = _node(
            NODE_A_ID,
            ARTIFACT_ID,
            "Stale name",
            artifact_type="model",
            collection_name="Old collection",
            x=10.0,
            y=20.0,
        )
        deleted_node = _node(
            NODE_B_ID,
            None,
            "Deleted dataset",
            artifact_type="dataset",
            collection_name="Datasets",
            x=-320.0,
            y=0.0,
        )
        edge = _edge(EDGE_ID, NODE_B_ID, NODE_A_ID, via=LineageVia.UI)
        mocks.artifact_repository.get_artifacts_by_ids_in_orbit.side_effect = [
            [focal],
            [focal],
        ]
        mocks.repository.get_node_by_artifact_id.return_value = focal_node
        mocks.repository.traverse.return_value = (
            [focal_node, deleted_node],
            [edge],
            True,
        )

        result = await mocks.handler.get_graph(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, ARTIFACT_ID, 5
        )

        assert result.depth == 5
        assert result.truncated is True
        assert result.edges == [edge.to_edge()]
        assert result.nodes[0].name == "Live name"
        assert result.nodes[0].type == "experiment"
        assert result.nodes[0].collection_name == "Experiments"
        assert (result.nodes[0].x, result.nodes[0].y) == (10.0, 20.0)
        assert result.nodes[0].data == focal
        assert result.nodes[0].is_deleted is False
        assert result.nodes[1].artifact_id is None
        assert result.nodes[1].name == "Deleted dataset"
        assert result.nodes[1].type == "dataset"
        assert result.nodes[1].collection_name == "Datasets"
        assert (result.nodes[1].x, result.nodes[1].y) == (-320.0, 0.0)
        assert result.nodes[1].data is None
        assert result.nodes[1].is_deleted is True
        mocks.repository.traverse.assert_awaited_once_with(ORBIT_ID, NODE_A_ID, 5)

    async def test_get_graph_rejects_a_nonexistent_or_foreign_focal_artifact(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        with pytest.raises(ArtifactNotFoundError, match="Artifact not found"):
            await mocks.handler.get_graph(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, ARTIFACT_ID, 2
            )

        mocks.repository.get_node_by_artifact_id.assert_not_awaited()
        mocks.repository.traverse.assert_not_awaited()

    async def test_get_graph_raises_before_repository_access_when_permission_denied(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        mocks.permissions_handler.check_permissions.side_effect = (
            InsufficientPermissionsError()
        )

        with pytest.raises(InsufficientPermissionsError):
            await mocks.handler.get_graph(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, ARTIFACT_ID, 2
            )

        mocks.orbit_repository.get_orbit_simple.assert_not_awaited()
        mocks.artifact_repository.get_artifacts_by_ids_in_orbit.assert_not_awaited()
