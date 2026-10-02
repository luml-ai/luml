from datetime import datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid7

import pytest
from luml.handlers.artifacts import ArtifactHandler
from luml.schemas.artifacts import (
    Artifact,
    ArtifactCreateIn,
    ArtifactListed,
    ArtifactStatus,
    ArtifactType,
    Manifest,
)
from luml.schemas.general import PaginationParams

from tests.support.ids import ARTIFACT_ID
from tests.support.mocks import CollaboratorMocks, mock_collaborators


@pytest.fixture
def mocks() -> CollaboratorMocks[ArtifactHandler]:
    return mock_collaborators(ArtifactHandler())


def _make_listed(manifest: Manifest, **overrides: object) -> ArtifactListed:
    base: dict[str, object] = {
        "id": uuid7(),
        "collection_id": uuid7(),
        "collection": {"name": "col"},
        "file_name": "f.pkl",
        "name": "artifact",
        "extra_values": {},
        "manifest": manifest,
        "file_hash": "h",
        "file_index": {},
        "bucket_location": "loc",
        "size": 1,
        "unique_identifier": str(uuid7()),
        "tags": None,
        "status": ArtifactStatus.UPLOADED,
        "created_at": datetime.now(),
        "updated_at": None,
        "type": ArtifactType.MODEL,
        "deployments": [],
    }
    base.update(overrides)
    return ArtifactListed.model_validate(base)


def _pagination_arg(mock: AsyncMock) -> PaginationParams:
    assert mock.await_args is not None
    pagination = mock.await_args.kwargs["pagination"]
    assert isinstance(pagination, PaginationParams)
    return pagination


def _artifact_create_input(
    manifest: Manifest, lineage_inputs: list[UUID] | None = None
) -> ArtifactCreateIn:
    return ArtifactCreateIn(
        extra_values={},
        manifest=manifest,
        file_hash="hash",
        file_index={},
        size=1,
        file_name="model.luml",
        name="model",
        tags=["tag"],
        lineage_inputs=lineage_inputs,
    )


def _pending_artifact(
    manifest: Manifest, artifact_id: UUID, collection_id: UUID
) -> Artifact:
    return Artifact(
        id=artifact_id,
        collection_id=collection_id,
        file_name="model.luml",
        name="model",
        extra_values={},
        manifest=manifest,
        file_hash="hash",
        file_index={},
        bucket_location="artifact/location",
        size=1,
        unique_identifier="uid",
        tags=["tag"],
        status=ArtifactStatus.PENDING_UPLOAD,
        created_at=datetime.now(),
        updated_at=None,
        created_by_user="Artifact User",
        type=ArtifactType.MODEL,
    )


def _make_artifact(manifest: Manifest, collection_id: UUID) -> Artifact:
    return Artifact(
        id=ARTIFACT_ID,
        collection_id=collection_id,
        file_name="foreign.luml",
        name="foreign",
        extra_values={},
        manifest=manifest,
        file_hash="hash",
        file_index={},
        bucket_location="foreign/loc",
        size=1,
        unique_identifier="uid",
        tags=None,
        status=ArtifactStatus.UPLOADED,
        created_at=datetime.now(),
        updated_at=None,
        type=ArtifactType.MODEL,
    )
