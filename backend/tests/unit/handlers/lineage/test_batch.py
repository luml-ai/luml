from unittest.mock import Mock
from uuid import UUID

import pytest
from luml.handlers.lineage import LineageHandler
from luml.infra.exceptions import (
    ApplicationError,
    ArtifactNotFoundError,
    NotFoundError,
    OrbitNotFoundError,
)
from luml.schemas.artifacts import ArtifactStatus
from luml.schemas.lineage import (
    LineageBatchIn,
    LineageNodeRef,
    LineagePair,
    LineagePosition,
    LineageVia,
)
from luml.schemas.permissions import Action, Resource
from sqlalchemy.exc import IntegrityError

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

MISSING_ID = UUID("0199c337-0a04-7755-b82e-8f38a1128ca1")
SECOND_EDGE_ID = UUID("0199c337-0a08-729d-a574-8909b52627b9")


class TestLineageBatch:
    async def test_apply_changes_orders_operations_and_collapses_duplicate_pairs(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        artifact_a = _artifact(ARTIFACT_ID, "A")
        artifact_b = _artifact(ARTIFACT_B_ID, "B", status=ArtifactStatus.PENDING_UPLOAD)
        artifact_c = _artifact(ARTIFACT_C_ID, "C")
        node_a = _node(NODE_A_ID, ARTIFACT_ID, "A")
        node_b = _node(NODE_B_ID, ARTIFACT_B_ID, "B")
        node_c = _node(NODE_C_ID, ARTIFACT_C_ID, "C")
        deleted_edge = _edge(EDGE_ID, NODE_B_ID, NODE_C_ID)
        created_edges = [
            _edge(NEW_EDGE_A_ID, NODE_A_ID, NODE_B_ID),
            _edge(NEW_EDGE_B_ID, NODE_B_ID, NODE_C_ID),
        ]

        mocks.artifact_repository.get_artifacts_by_ids_in_orbit.return_value = [
            artifact_a,
            artifact_b,
            artifact_c,
        ]
        mocks.repository.get_edges_by_ids.return_value = [deleted_edge]
        mocks.repository.get_nodes_by_ids.side_effect = [[], [node_a]]
        mocks.repository.get_or_create_node.side_effect = [node_a, node_b, node_c]
        mocks.repository.create_edges.return_value = created_edges
        mocks.repository.get_nodes_by_artifact_ids.return_value = [node_c]

        operation_order = Mock()
        operation_order.attach_mock(mocks.repository.delete_edges, "delete")
        operation_order.attach_mock(mocks.repository.create_edges, "create")
        operation_order.attach_mock(mocks.repository.update_positions, "position")
        operation_order.attach_mock(mocks.repository.delete_edgeless_nodes, "cleanup")

        pair_a_b = LineagePair(
            source=LineageNodeRef(artifact_id=ARTIFACT_ID),
            target=LineageNodeRef(artifact_id=ARTIFACT_B_ID),
        )
        changes = LineageBatchIn(
            delete=[EDGE_ID],
            create=[
                pair_a_b,
                pair_a_b,
                LineagePair(
                    source=LineageNodeRef(artifact_id=ARTIFACT_B_ID),
                    target=LineageNodeRef(artifact_id=ARTIFACT_C_ID),
                ),
            ],
            positions=[
                LineagePosition(ref=LineageNodeRef(node_id=NODE_A_ID), x=10.0, y=20.0),
                LineagePosition(
                    ref=LineageNodeRef(artifact_id=ARTIFACT_C_ID), x=30.0, y=40.0
                ),
                LineagePosition(ref=LineageNodeRef(node_id=MISSING_ID), x=50.0, y=60.0),
            ],
        )

        result = await mocks.handler.apply_changes(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            changes,
            API_KEY_SCOPES,
        )

        assert [edge.id for edge in result.deleted] == [EDGE_ID]
        assert [edge.id for edge in result.created] == [NEW_EDGE_A_ID, NEW_EDGE_B_ID]
        mocks.repository.create_edges.assert_awaited_once_with(
            ORBIT_ID,
            [(NODE_A_ID, NODE_B_ID), (NODE_B_ID, NODE_C_ID)],
            "Lineage User",
            LineageVia.API,
            mocks.session,
        )
        mocks.repository.update_positions.assert_awaited_once_with(
            ORBIT_ID,
            {NODE_A_ID: (10.0, 20.0), NODE_C_ID: (30.0, 40.0)},
            mocks.session,
        )
        assert [item[0] for item in operation_order.mock_calls] == [
            "delete",
            "create",
            "position",
            "cleanup",
        ]
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.ARTIFACT,
            Action.UPDATE,
            ORBIT_ID,
        )

    async def test_apply_changes_replaces_a_node_and_keeps_its_position(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        replacement = _artifact(ARTIFACT_C_ID, "B prime")
        source_node = _node(NODE_A_ID, ARTIFACT_ID, "A")
        replacement_node = _node(NODE_C_ID, ARTIFACT_C_ID, "B prime")
        deleted_edge = _edge(EDGE_ID, NODE_A_ID, NODE_B_ID)
        created_edge = _edge(NEW_EDGE_A_ID, NODE_A_ID, NODE_C_ID)
        mocks.repository.get_edges_by_ids.return_value = [deleted_edge]
        mocks.artifact_repository.get_artifacts_by_ids_in_orbit.return_value = [
            replacement
        ]
        mocks.repository.get_nodes_by_ids.side_effect = [[source_node], []]
        mocks.repository.get_or_create_node.return_value = replacement_node
        mocks.repository.create_edges.return_value = [created_edge]
        mocks.repository.get_nodes_by_artifact_ids.return_value = [replacement_node]
        changes = LineageBatchIn(
            delete=[EDGE_ID],
            create=[
                LineagePair(
                    source=LineageNodeRef(node_id=NODE_A_ID),
                    target=LineageNodeRef(artifact_id=ARTIFACT_C_ID),
                )
            ],
            positions=[
                LineagePosition(
                    ref=LineageNodeRef(artifact_id=ARTIFACT_C_ID),
                    x=300.0,
                    y=100.0,
                )
            ],
        )

        result = await mocks.handler.apply_changes(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            changes,
            JWT_SCOPES,
        )

        assert result.deleted == [deleted_edge.to_edge()]
        assert result.created == [created_edge.to_edge()]
        mocks.repository.update_positions.assert_awaited_once_with(
            ORBIT_ID,
            {NODE_C_ID: (300.0, 100.0)},
            mocks.session,
        )
        mocks.repository.delete_edgeless_nodes.assert_awaited_once_with(
            ORBIT_ID, mocks.session, [NODE_A_ID, NODE_B_ID]
        )

    async def test_apply_changes_replaces_a_deleted_node_with_all_of_its_connections(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        node_a = _node(NODE_A_ID, ARTIFACT_ID, "A")
        node_b = _node(NODE_B_ID, ARTIFACT_B_ID, "B")
        replacement = _artifact(ARTIFACT_C_ID, "A prime")
        replacement_node = _node(NODE_C_ID, ARTIFACT_C_ID, "A prime")
        deleted_edges = [
            _edge(EDGE_ID, MISSING_ID, NODE_B_ID),
            _edge(SECOND_EDGE_ID, NODE_A_ID, MISSING_ID),
        ]
        created_edges = [
            _edge(NEW_EDGE_A_ID, NODE_C_ID, NODE_B_ID),
            _edge(NEW_EDGE_B_ID, NODE_A_ID, NODE_C_ID),
        ]
        mocks.repository.get_edges_by_ids.return_value = deleted_edges
        mocks.artifact_repository.get_artifacts_by_ids_in_orbit.return_value = [
            replacement
        ]
        mocks.repository.get_nodes_by_ids.side_effect = [[node_b, node_a], []]
        mocks.repository.get_or_create_node.return_value = replacement_node
        mocks.repository.create_edges.return_value = created_edges
        mocks.repository.get_nodes_by_artifact_ids.return_value = [replacement_node]
        changes = LineageBatchIn(
            delete=[edge.id for edge in deleted_edges],
            create=[
                LineagePair(
                    source=LineageNodeRef(artifact_id=ARTIFACT_C_ID),
                    target=LineageNodeRef(node_id=NODE_B_ID),
                ),
                LineagePair(
                    source=LineageNodeRef(node_id=NODE_A_ID),
                    target=LineageNodeRef(artifact_id=ARTIFACT_C_ID),
                ),
            ],
            positions=[
                LineagePosition(
                    ref=LineageNodeRef(artifact_id=ARTIFACT_C_ID),
                    x=300.0,
                    y=100.0,
                )
            ],
        )

        result = await mocks.handler.apply_changes(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            changes,
            JWT_SCOPES,
        )

        assert result.deleted == [edge.to_edge() for edge in deleted_edges]
        assert result.created == [edge.to_edge() for edge in created_edges]
        mocks.repository.create_edges.assert_awaited_once_with(
            ORBIT_ID,
            [(NODE_C_ID, NODE_B_ID), (NODE_A_ID, NODE_C_ID)],
            "Lineage User",
            LineageVia.UI,
            mocks.session,
        )
        mocks.repository.update_positions.assert_awaited_once_with(
            ORBIT_ID,
            {NODE_C_ID: (300.0, 100.0)},
            mocks.session,
        )
        mocks.repository.delete_edgeless_nodes.assert_awaited_once_with(
            ORBIT_ID, mocks.session, [MISSING_ID, NODE_B_ID, NODE_A_ID]
        )

    async def test_apply_changes_recreates_a_deleted_pair_with_a_new_edge(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        node_a = _node(NODE_A_ID, ARTIFACT_ID, "A")
        node_b = _node(NODE_B_ID, ARTIFACT_B_ID, "B")
        deleted_edge = _edge(EDGE_ID, NODE_A_ID, NODE_B_ID)
        created_edge = _edge(NEW_EDGE_A_ID, NODE_A_ID, NODE_B_ID)
        mocks.repository.get_edges_by_ids.return_value = [deleted_edge]
        mocks.repository.get_nodes_by_ids.return_value = [node_a, node_b]
        mocks.repository.create_edges.return_value = [created_edge]
        changes = LineageBatchIn(
            delete=[EDGE_ID],
            create=[
                LineagePair(
                    source=LineageNodeRef(node_id=NODE_A_ID),
                    target=LineageNodeRef(node_id=NODE_B_ID),
                )
            ],
        )

        result = await mocks.handler.apply_changes(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            changes,
            API_KEY_SCOPES,
        )

        assert result.deleted == [deleted_edge.to_edge()]
        assert result.created == [created_edge.to_edge()]
        assert result.created[0].id != result.deleted[0].id
        mocks.repository.delete_edges.assert_awaited_once_with(
            ORBIT_ID, [EDGE_ID], mocks.session
        )
        mocks.repository.get_edges_by_pairs.assert_awaited_once_with(
            ORBIT_ID, [(NODE_A_ID, NODE_B_ID)], mocks.session
        )
        mocks.repository.create_edges.assert_awaited_once_with(
            ORBIT_ID,
            [(NODE_A_ID, NODE_B_ID)],
            "Lineage User",
            LineageVia.API,
            mocks.session,
        )

    async def test_apply_changes_rejects_a_loop_and_rolls_back(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        artifact = _artifact(ARTIFACT_ID, "A")
        node = _node(NODE_A_ID, ARTIFACT_ID, "A")
        existing = _edge(EDGE_ID, NODE_B_ID, NODE_C_ID)
        mocks.repository.get_edges_by_ids.return_value = [existing]
        mocks.artifact_repository.get_artifacts_by_ids_in_orbit.return_value = [
            artifact
        ]
        mocks.repository.get_or_create_node.return_value = node
        changes = LineageBatchIn(
            delete=[EDGE_ID],
            create=[
                LineagePair(
                    source=LineageNodeRef(artifact_id=ARTIFACT_ID),
                    target=LineageNodeRef(artifact_id=ARTIFACT_ID),
                )
            ],
        )

        with pytest.raises(
            ApplicationError, match="Artifact cannot be linked to itself"
        ) as error:
            await mocks.handler.apply_changes(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                changes,
                API_KEY_SCOPES,
            )

        assert error.value.status_code == 400
        assert mocks.transaction_errors == [error.value]
        mocks.repository.delete_edges.assert_awaited_once()
        mocks.repository.create_edges.assert_not_awaited()
        mocks.repository.delete_edgeless_nodes.assert_not_awaited()

    @pytest.mark.parametrize(
        ("existing_source", "existing_target", "message"),
        [
            (NODE_A_ID, NODE_B_ID, "Lineage connection already exists"),
            (NODE_B_ID, NODE_A_ID, "Reverse lineage connection already exists"),
        ],
    )
    async def test_apply_changes_rejects_existing_pair_in_either_direction(
        self,
        mocks: CollaboratorMocks[LineageHandler],
        existing_source: UUID,
        existing_target: UUID,
        message: str,
    ) -> None:
        _configure_artifact_pair(mocks)
        mocks.repository.get_edges_by_pairs.return_value = [
            _edge(EDGE_ID, existing_source, existing_target)
        ]

        with pytest.raises(ApplicationError, match=message) as error:
            await mocks.handler.apply_changes(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                _creation_changes(),
                JWT_SCOPES,
            )

        assert error.value.status_code == 409
        mocks.repository.create_edges.assert_not_awaited()

    async def test_apply_changes_rejects_reverse_pairs_in_the_same_batch(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        _configure_artifact_pair(mocks)
        changes = LineageBatchIn(
            create=[
                *_creation_changes().create,
                LineagePair(
                    source=LineageNodeRef(artifact_id=ARTIFACT_B_ID),
                    target=LineageNodeRef(artifact_id=ARTIFACT_ID),
                ),
            ]
        )

        with pytest.raises(
            ApplicationError, match="Reverse lineage connection already exists"
        ) as error:
            await mocks.handler.apply_changes(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                changes,
                API_KEY_SCOPES,
            )

        assert error.value.status_code == 409
        mocks.repository.get_edges_by_pairs.assert_not_awaited()
        mocks.repository.create_edges.assert_not_awaited()

    async def test_apply_changes_rejects_artifact_outside_the_orbit(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        mocks.artifact_repository.get_artifacts_by_ids_in_orbit.return_value = [
            _artifact(ARTIFACT_ID, "A")
        ]

        with pytest.raises(ArtifactNotFoundError, match="Artifact not found"):
            await mocks.handler.apply_changes(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                _creation_changes(),
                API_KEY_SCOPES,
            )

        mocks.repository.get_or_create_node.assert_not_awaited()
        mocks.repository.create_edges.assert_not_awaited()

    async def test_apply_changes_rejects_node_outside_the_orbit(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        mocks.artifact_repository.get_artifacts_by_ids_in_orbit.return_value = [
            _artifact(ARTIFACT_ID, "A")
        ]
        changes = LineageBatchIn(
            create=[
                LineagePair(
                    source=LineageNodeRef(artifact_id=ARTIFACT_ID),
                    target=LineageNodeRef(node_id=NODE_B_ID),
                )
            ]
        )

        with pytest.raises(NotFoundError, match="Lineage node not found"):
            await mocks.handler.apply_changes(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                changes,
                API_KEY_SCOPES,
            )

        mocks.repository.get_nodes_by_ids.assert_awaited_once_with(
            ORBIT_ID, [NODE_B_ID], mocks.session
        )
        mocks.repository.get_or_create_node.assert_not_awaited()
        mocks.repository.create_edges.assert_not_awaited()

    async def test_apply_changes_connects_to_a_deleted_artifact_node(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        artifact = _artifact(ARTIFACT_ID, "A")
        live_node = _node(NODE_A_ID, ARTIFACT_ID, "A")
        deleted_node = _node(NODE_B_ID, None, "Deleted source")
        edge = _edge(NEW_EDGE_A_ID, NODE_A_ID, NODE_B_ID)
        mocks.artifact_repository.get_artifacts_by_ids_in_orbit.return_value = [
            artifact
        ]
        mocks.repository.get_nodes_by_ids.return_value = [deleted_node]
        mocks.repository.get_or_create_node.return_value = live_node
        mocks.repository.create_edges.return_value = [edge]
        changes = LineageBatchIn(
            create=[
                LineagePair(
                    source=LineageNodeRef(artifact_id=ARTIFACT_ID),
                    target=LineageNodeRef(node_id=NODE_B_ID),
                )
            ]
        )

        result = await mocks.handler.apply_changes(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            changes,
            API_KEY_SCOPES,
        )

        assert result.created == [edge.to_edge()]

    async def test_apply_changes_rejects_an_edge_outside_the_orbit(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        with pytest.raises(NotFoundError, match="Lineage connection not found"):
            await mocks.handler.apply_changes(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                LineageBatchIn(delete=[EDGE_ID]),
                API_KEY_SCOPES,
            )

        mocks.repository.delete_edges.assert_not_awaited()
        mocks.repository.delete_edgeless_nodes.assert_not_awaited()

    async def test_apply_changes_returns_empty_result_when_batch_is_empty(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        result = await mocks.handler.apply_changes(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            LineageBatchIn(),
            JWT_SCOPES,
        )

        assert result.created == []
        assert result.deleted == []
        mocks.user_repository.get_public_user_by_id.assert_not_awaited()
        mocks.artifact_repository.get_artifacts_by_ids_in_orbit.assert_not_awaited()
        mocks.repository.delete_edgeless_nodes.assert_not_awaited()

    async def test_apply_changes_raises_when_orbit_is_outside_the_organization(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        mocks.orbit_repository.get_orbit_simple.return_value = None

        with pytest.raises(OrbitNotFoundError, match="Orbit not found"):
            await mocks.handler.apply_changes(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                LineageBatchIn(),
                API_KEY_SCOPES,
            )

        mocks.repository.delete_edgeless_nodes.assert_not_awaited()

    async def test_apply_changes_raises_conflict_when_edge_was_created_concurrently(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        _configure_artifact_pair(mocks)
        mocks.repository.create_edges.side_effect = IntegrityError(
            "INSERT INTO lineage_edges", {}, Exception("duplicate key")
        )

        with pytest.raises(ApplicationError) as error:
            await mocks.handler.apply_changes(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, _creation_changes(), JWT_SCOPES
            )

        assert error.value.status_code == 409
        assert error.value.message == "Lineage connection already exists"
        assert mocks.transaction_errors == [error.value]
        mocks.repository.update_positions.assert_not_awaited()
        mocks.repository.delete_edgeless_nodes.assert_not_awaited()

    async def test_apply_changes_raises_not_found_when_creating_user_is_unknown(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        _configure_artifact_pair(mocks)
        mocks.user_repository.get_public_user_by_id.return_value = None

        with pytest.raises(NotFoundError, match="User not found"):
            await mocks.handler.apply_changes(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, _creation_changes(), API_KEY_SCOPES
            )

        mocks.user_repository.get_public_user_by_id.assert_awaited_once_with(USER_ID)
        mocks.repository.create_edges.assert_not_awaited()

    def test_resolve_node_reference_raises_when_reference_has_no_identifier(
        self,
    ) -> None:
        unvalidated_ref = LineageNodeRef.model_construct()

        with pytest.raises(RuntimeError, match="has no identifier"):
            LineageHandler._resolve_node_reference(unvalidated_ref, {}, {})

    async def test_resolve_positions_skips_a_reference_without_identifier(
        self, mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        mocks.repository.get_nodes_by_ids.return_value = [
            _node(NODE_A_ID, ARTIFACT_ID, "A")
        ]
        positions = [
            LineagePosition.model_construct(
                ref=LineageNodeRef.model_construct(), x=1.0, y=2.0
            ),
            LineagePosition(ref=LineageNodeRef(node_id=NODE_A_ID), x=3.0, y=4.0),
        ]

        resolved = await mocks.handler._resolve_positions(
            ORBIT_ID, positions, mocks.session
        )

        assert resolved == {NODE_A_ID: (3.0, 4.0)}
        mocks.repository.get_nodes_by_artifact_ids.assert_awaited_once_with(
            ORBIT_ID, [], mocks.session
        )
        mocks.repository.get_nodes_by_ids.assert_awaited_once_with(
            ORBIT_ID, [NODE_A_ID], mocks.session
        )
