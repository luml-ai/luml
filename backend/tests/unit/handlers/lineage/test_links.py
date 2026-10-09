from collections.abc import Awaitable
from uuid import UUID

import pytest
from luml.handlers.lineage import LineageHandler
from luml.infra.exceptions import (
    ArtifactNotFoundError,
    InsufficientPermissionsError,
    NotFoundError,
)
from luml.schemas.artifacts import ArtifactStatus, ArtifactType
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
from tests.unit.handlers.lineage.conftest import (
    API_KEY_SCOPES,
    ARTIFACT_B_ID,
    ARTIFACT_C_ID,
    JWT_SCOPES,
    NEW_EDGE_A_ID,
    NEW_EDGE_B_ID,
    NODE_C_ID,
    _artifact,
    _configure_artifact_pair,
    _creation_changes,
    _edge,
    _node,
)

EXPERIMENT_COLLECTION_ID = UUID("0199c337-09f5-7815-a7bd-403c946747f1")
MODEL_COLLECTION_ID = UUID("0199c337-09f6-766a-bbd5-c457d65e2050")


class TestLineageLinks:
    async def test_create_links_builds_a_chain_across_collections(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        dataset = _artifact(
            ARTIFACT_ID,
            "Dataset",
            artifact_type=ArtifactType.DATASET,
            collection_name="Datasets",
        )
        experiment = _artifact(
            ARTIFACT_B_ID,
            "Experiment",
            artifact_type=ArtifactType.EXPERIMENT,
            status=ArtifactStatus.PENDING_UPLOAD,
            collection_id=EXPERIMENT_COLLECTION_ID,
            collection_name="Experiments",
        )
        model = _artifact(
            ARTIFACT_C_ID,
            "Model",
            collection_id=MODEL_COLLECTION_ID,
            collection_name="Models",
        )
        dataset_node = _node(
            NODE_A_ID,
            ARTIFACT_ID,
            "Dataset",
            artifact_type="dataset",
            collection_name="Datasets",
        )
        experiment_node = _node(
            NODE_B_ID,
            ARTIFACT_B_ID,
            "Experiment",
            artifact_type="experiment",
            collection_name="Experiments",
        )
        model_node = _node(NODE_C_ID, ARTIFACT_C_ID, "Model")
        dataset_edge = _edge(NEW_EDGE_A_ID, NODE_A_ID, NODE_B_ID)
        experiment_edge = _edge(NEW_EDGE_B_ID, NODE_B_ID, NODE_C_ID)
        mocks.artifact_repository.get_artifacts_by_ids_in_orbit.side_effect = [
            [dataset, experiment],
            [experiment, model],
            [model],
            [model, experiment, dataset],
        ]
        mocks.repository.get_or_create_node.side_effect = [
            dataset_node,
            experiment_node,
            experiment_node,
            model_node,
        ]
        mocks.repository.create_edges.side_effect = [[dataset_edge], [experiment_edge]]

        first = await mocks.handler.create_links(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            ARTIFACT_ID,
            [ARTIFACT_B_ID],
            API_KEY_SCOPES,
        )
        second = await mocks.handler.create_links(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            ARTIFACT_B_ID,
            [ARTIFACT_C_ID],
            API_KEY_SCOPES,
        )

        mocks.repository.get_node_by_artifact_id.return_value = model_node
        mocks.repository.traverse.return_value = (
            [model_node, experiment_node, dataset_node],
            [dataset_edge, experiment_edge],
            False,
        )
        graph = await mocks.handler.get_graph(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, ARTIFACT_C_ID, 2
        )

        assert first == [dataset_edge.to_edge()]
        assert second == [experiment_edge.to_edge()]
        assert len(graph.nodes) == 3
        assert len(graph.edges) == 2
        assert {node.collection_name for node in graph.nodes} == {
            "Datasets",
            "Experiments",
            "Models",
        }
        assert all(edge.created_by_user == "Lineage User" for edge in graph.edges)
        assert all(edge.created_via == LineageVia.API for edge in graph.edges)
        assert mocks.repository.create_edges.await_args_list[0].args[1] == [
            (NODE_A_ID, NODE_B_ID)
        ]
        assert mocks.repository.create_edges.await_args_list[1].args[1] == [
            (NODE_B_ID, NODE_C_ID)
        ]

    async def test_create_links_collapses_duplicate_targets(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        artifacts = [
            _artifact(ARTIFACT_ID, "A"),
            _artifact(
                ARTIFACT_B_ID,
                "B",
                status=ArtifactStatus.PENDING_UPLOAD,
            ),
            _artifact(ARTIFACT_C_ID, "C"),
        ]
        nodes = [
            _node(NODE_A_ID, ARTIFACT_ID, "A"),
            _node(NODE_B_ID, ARTIFACT_B_ID, "B"),
            _node(NODE_C_ID, ARTIFACT_C_ID, "C"),
        ]
        created = [
            _edge(NEW_EDGE_A_ID, NODE_A_ID, NODE_B_ID),
            _edge(NEW_EDGE_B_ID, NODE_A_ID, NODE_C_ID),
        ]
        mocks.artifact_repository.get_artifacts_by_ids_in_orbit.return_value = artifacts
        mocks.repository.get_or_create_node.side_effect = nodes
        mocks.repository.create_edges.return_value = created

        result = await mocks.handler.create_links(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            ARTIFACT_ID,
            [ARTIFACT_B_ID, ARTIFACT_C_ID, ARTIFACT_B_ID],
            API_KEY_SCOPES,
        )

        assert result == [edge.to_edge() for edge in created]
        mocks.repository.create_edges.assert_awaited_once_with(
            ORBIT_ID,
            [(NODE_A_ID, NODE_B_ID), (NODE_A_ID, NODE_C_ID)],
            "Lineage User",
            LineageVia.API,
            mocks.session,
        )

    async def test_create_links_skips_access_check_when_check_access_is_false(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        node_a, node_b = _configure_artifact_pair(mocks)
        edge = _edge(NEW_EDGE_A_ID, node_a.id, node_b.id)
        mocks.repository.create_edges.return_value = [edge]

        result = await mocks.handler.create_links(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            ARTIFACT_ID,
            [ARTIFACT_B_ID],
            API_KEY_SCOPES,
            check_access=False,
        )

        assert result == [edge.to_edge()]
        mocks.permissions_handler.check_permissions.assert_not_awaited()
        mocks.orbit_repository.get_orbit_simple.assert_not_awaited()

    @pytest.mark.parametrize(
        ("artifact_id", "node_id", "name"),
        [
            (ARTIFACT_ID, NODE_A_ID, "A"),
            (ARTIFACT_B_ID, NODE_B_ID, "B"),
        ],
    )
    async def test_delete_link_deletes_edge_when_artifact_is_either_edge_end(
        self,
        mocks: CollaboratorMocks[LineageHandler],
        artifact_id: UUID,
        node_id: UUID,
        name: str,
    ) -> None:
        artifact = _artifact(artifact_id, name)
        node = _node(node_id, artifact_id, name)
        edge = _edge(EDGE_ID, NODE_A_ID, NODE_B_ID)
        mocks.artifact_repository.get_artifacts_by_ids_in_orbit.return_value = [
            artifact
        ]
        mocks.repository.get_node_by_artifact_id.return_value = node
        mocks.repository.get_edges_by_ids.side_effect = [[edge], [edge]]

        result = await mocks.handler.delete_link(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            artifact_id,
            EDGE_ID,
            JWT_SCOPES,
        )

        assert result == edge.to_edge()
        mocks.repository.delete_edges.assert_awaited_once_with(
            ORBIT_ID, [EDGE_ID], mocks.session
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once()

    async def test_delete_link_rejects_an_artifact_outside_the_orbit(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        with pytest.raises(ArtifactNotFoundError, match="Artifact not found"):
            await mocks.handler.delete_link(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                ARTIFACT_ID,
                EDGE_ID,
                JWT_SCOPES,
            )

        mocks.repository.get_node_by_artifact_id.assert_not_awaited()
        mocks.repository.delete_edges.assert_not_awaited()

    @pytest.mark.parametrize("edge_in_orbit", [True, False])
    async def test_delete_link_rejects_a_foreign_or_non_owned_edge(
        self, mocks: CollaboratorMocks[LineageHandler], edge_in_orbit: bool
    ) -> None:
        artifact_c = _artifact(ARTIFACT_C_ID, "C")
        node_c = _node(NODE_C_ID, ARTIFACT_C_ID, "C")
        edge = _edge(EDGE_ID, NODE_A_ID, NODE_B_ID)
        mocks.artifact_repository.get_artifacts_by_ids_in_orbit.return_value = [
            artifact_c
        ]
        mocks.repository.get_node_by_artifact_id.return_value = node_c
        mocks.repository.get_edges_by_ids.return_value = [edge] if edge_in_orbit else []

        with pytest.raises(NotFoundError, match="Lineage connection not found"):
            await mocks.handler.delete_link(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                ARTIFACT_C_ID,
                EDGE_ID,
                JWT_SCOPES,
            )

        mocks.repository.delete_edges.assert_not_awaited()

    @pytest.mark.parametrize("operation", ["batch", "single-create", "single-delete"])
    async def test_write_operations_raise_before_repository_access_when_denied(
        self, mocks: CollaboratorMocks[LineageHandler], operation: str
    ) -> None:
        mocks.permissions_handler.check_permissions.side_effect = (
            InsufficientPermissionsError()
        )

        operation_call: Awaitable[object]
        if operation == "batch":
            operation_call = mocks.handler.apply_changes(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                _creation_changes(),
                API_KEY_SCOPES,
            )
        elif operation == "single-create":
            operation_call = mocks.handler.create_links(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                ARTIFACT_ID,
                [ARTIFACT_B_ID],
                API_KEY_SCOPES,
            )
        else:
            operation_call = mocks.handler.delete_link(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                ARTIFACT_ID,
                EDGE_ID,
                JWT_SCOPES,
            )

        with pytest.raises(InsufficientPermissionsError):
            await operation_call

        mocks.orbit_repository.get_orbit_simple.assert_not_awaited()
        mocks.artifact_repository.get_artifacts_by_ids_in_orbit.assert_not_awaited()
        mocks.repository.create_edges.assert_not_awaited()
        mocks.repository.delete_edges.assert_not_awaited()
        mocks.repository.delete_edgeless_nodes.assert_not_awaited()

    async def test_link_inputs_records_every_input_in_one_transaction(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        artifacts = {
            ARTIFACT_ID: _artifact(ARTIFACT_ID, "dataset"),
            ARTIFACT_B_ID: _artifact(ARTIFACT_B_ID, "experiment"),
            ARTIFACT_C_ID: _artifact(ARTIFACT_C_ID, "model"),
        }
        nodes = {
            ARTIFACT_ID: _node(NODE_A_ID, ARTIFACT_ID, "dataset"),
            ARTIFACT_B_ID: _node(NODE_B_ID, ARTIFACT_B_ID, "experiment"),
            ARTIFACT_C_ID: _node(NODE_C_ID, ARTIFACT_C_ID, "model"),
        }
        mocks.artifact_repository.get_artifacts_by_ids_in_orbit.return_value = list(
            artifacts.values()
        )
        mocks.repository.get_or_create_node.side_effect = (
            lambda orbit_id, artifact, session: nodes[artifact.id]
        )
        created = [
            _edge(NEW_EDGE_A_ID, NODE_A_ID, NODE_C_ID),
            _edge(NEW_EDGE_B_ID, NODE_B_ID, NODE_C_ID),
        ]
        mocks.repository.create_edges.return_value = created

        result = await mocks.handler.link_inputs(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            ARTIFACT_C_ID,
            [ARTIFACT_ID, ARTIFACT_B_ID, ARTIFACT_ID],
            API_KEY_SCOPES,
            check_access=False,
        )

        assert result == [edge.to_edge() for edge in created]
        mocks.permissions_handler.check_permissions.assert_not_awaited()
        mocks.repository.create_edges.assert_awaited_once_with(
            ORBIT_ID,
            [(NODE_A_ID, NODE_C_ID), (NODE_B_ID, NODE_C_ID)],
            "Lineage User",
            LineageVia.API,
            mocks.session,
        )
        mocks.repository.delete_edgeless_nodes.assert_not_awaited()

    async def test_link_inputs_returns_empty_without_access_check_when_no_inputs(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        result = await mocks.handler.link_inputs(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, ARTIFACT_C_ID, [], API_KEY_SCOPES
        )

        assert result == []
        mocks.permissions_handler.check_permissions.assert_not_awaited()
        mocks.repository.create_edges.assert_not_awaited()

    async def test_link_inputs_checks_access_when_check_access_is_not_given(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        _configure_artifact_pair(mocks)
        created = [_edge(NEW_EDGE_A_ID, NODE_A_ID, NODE_B_ID)]
        mocks.repository.create_edges.return_value = created

        result = await mocks.handler.link_inputs(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            ARTIFACT_B_ID,
            [ARTIFACT_ID],
            API_KEY_SCOPES,
        )

        assert result == [edge.to_edge() for edge in created]
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.UPDATE, ORBIT_ID
        )
        mocks.orbit_repository.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.repository.create_edges.assert_awaited_once_with(
            ORBIT_ID,
            [(NODE_A_ID, NODE_B_ID)],
            "Lineage User",
            LineageVia.API,
            mocks.session,
        )
