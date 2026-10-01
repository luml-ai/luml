from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import UUID

import pytest
from luml.handlers.lineage import LineageHandler
from luml.models.lineage import LineageEdgeOrm, LineageNodeOrm
from luml.schemas.artifacts import (
    ArtifactListed,
    ArtifactStatus,
    ArtifactType,
    LumlArtifactManifest,
)
from luml.schemas.lineage import LineageBatchIn, LineageNodeRef, LineagePair, LineageVia

from tests.support.ids import (
    ARTIFACT_ID,
    COLLECTION_ID,
    NODE_A_ID,
    NODE_B_ID,
    ORBIT_ID,
)
from tests.support.mocks import CollaboratorMocks, mock_collaborators

ARTIFACT_B_ID = UUID("0199c337-09fb-72eb-a8c8-77e55d873463")
ARTIFACT_C_ID = UUID("0199c337-09fc-75de-8581-9fd795cb8ebf")
NODE_C_ID = UUID("0199c337-0a03-7f5a-bb17-2c9d4e8a1b63")
NEW_EDGE_A_ID = UUID("0199c337-0a06-7123-9ceb-2251e583cb88")
NEW_EDGE_B_ID = UUID("0199c337-0a07-7fef-962d-435a52af014e")
CREATED_AT = datetime(2026, 9, 3, tzinfo=UTC)
API_KEY_SCOPES = ["authenticated", "api_key"]
JWT_SCOPES = ["authenticated", "jwt"]


@pytest.fixture
def mocks() -> CollaboratorMocks[LineageHandler]:
    mocks = mock_collaborators(LineageHandler())
    mocks.user_repository.get_public_user_by_id.return_value = Mock(
        full_name="Lineage User", email="lineage@example.com"
    )
    mocks.artifact_repository.get_artifacts_by_ids_in_orbit.return_value = []
    mocks.repository.get_edges_by_ids.return_value = []
    mocks.repository.get_nodes_by_ids.return_value = []
    mocks.repository.get_edges_by_pairs.return_value = []
    mocks.repository.get_nodes_by_artifact_ids.return_value = []
    mocks.repository.get_node_by_artifact_id.return_value = None
    return mocks


def _artifact(
    artifact_id: UUID,
    name: str,
    *,
    artifact_type: ArtifactType = ArtifactType.MODEL,
    status: ArtifactStatus = ArtifactStatus.UPLOADED,
    collection_id: UUID = COLLECTION_ID,
    collection_name: str = "Models",
) -> ArtifactListed:
    return ArtifactListed.model_validate(
        {
            "id": artifact_id,
            "collection_id": collection_id,
            "collection": {"name": collection_name},
            "file_name": f"{name}.luml",
            "name": name,
            "description": None,
            "extra_values": {},
            "manifest": LumlArtifactManifest(
                artifact_type=artifact_type.value,
                variant="default",
                producer_name="tests",
                producer_version="1",
                producer_tags=[],
                payload={},
            ),
            "file_hash": f"hash-{name}",
            "file_index": {},
            "bucket_location": f"artifacts/{name}",
            "size": 1,
            "unique_identifier": f"uid-{name}",
            "tags": [],
            "status": status,
            "created_by_user": "Lineage User",
            "created_at": CREATED_AT,
            "updated_at": None,
            "type": artifact_type,
            "deployments": [],
        }
    )


def _node(
    node_id: UUID,
    artifact_id: UUID | None,
    name: str,
    *,
    artifact_type: str = "model",
    collection_name: str | None = "Models",
    x: float | None = None,
    y: float | None = None,
) -> LineageNodeOrm:
    return LineageNodeOrm(
        id=node_id,
        orbit_id=ORBIT_ID,
        artifact_id=artifact_id,
        name=name,
        type=artifact_type,
        collection_name=collection_name,
        x=x,
        y=y,
        created_at=CREATED_AT,
    )


def _edge(
    edge_id: UUID,
    source: UUID,
    target: UUID,
    *,
    via: LineageVia = LineageVia.API,
) -> LineageEdgeOrm:
    return LineageEdgeOrm(
        id=edge_id,
        orbit_id=ORBIT_ID,
        source_node_id=source,
        target_node_id=target,
        created_by_user="Lineage User",
        created_via=via.value,
        created_at=CREATED_AT,
    )


def _creation_changes(
    source_artifact_id: UUID = ARTIFACT_ID,
    target_artifact_id: UUID = ARTIFACT_B_ID,
) -> LineageBatchIn:
    return LineageBatchIn(
        create=[
            LineagePair(
                source=LineageNodeRef(artifact_id=source_artifact_id),
                target=LineageNodeRef(artifact_id=target_artifact_id),
            )
        ]
    )


def _configure_artifact_pair(
    mocks: CollaboratorMocks[LineageHandler],
) -> tuple[LineageNodeOrm, LineageNodeOrm]:
    artifact_a = _artifact(ARTIFACT_ID, "A")
    artifact_b = _artifact(ARTIFACT_B_ID, "B", status=ArtifactStatus.PENDING_UPLOAD)
    node_a = _node(NODE_A_ID, ARTIFACT_ID, "A")
    node_b = _node(NODE_B_ID, ARTIFACT_B_ID, "B")
    mocks.artifact_repository.get_artifacts_by_ids_in_orbit.return_value = [
        artifact_a,
        artifact_b,
    ]
    mocks.repository.get_or_create_node.side_effect = [node_a, node_b]
    return node_a, node_b
