from unittest.mock import Mock

import pytest
from luml.handlers.artifacts import ArtifactHandler
from luml.infra.exceptions import ApplicationError

from tests.support.ids import (
    ARTIFACT_ID,
    COLLECTION_ID,
    ORBIT_ID,
    ORGANIZATION_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks, mock_collaborators


@pytest.fixture
def mocks() -> CollaboratorMocks[ArtifactHandler]:
    collaborators = mock_collaborators(ArtifactHandler())
    collaborators.orbit_repository.get_orbit_simple.return_value = Mock(
        organization_id=ORGANIZATION_ID
    )
    collaborators.collection_repository.get_collection.return_value = Mock(
        orbit_id=ORBIT_ID
    )
    return collaborators


class TestArtifactGuards:
    async def test_artifact_deletion_checks_raises_conflict_when_artifact_is_tracked(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        mocks.repository.get_artifact_details.return_value = Mock(
            collection_id=COLLECTION_ID, deployments=None
        )
        mocks.track_entry_repository.has_entries_for_artifact.return_value = True

        with pytest.raises(
            ApplicationError, match="referenced by one or more tracks"
        ) as exc:
            await mocks.handler._artifact_deletion_checks(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
            )
        assert exc.value.status_code == 409

    async def test_artifact_deletion_checks_returns_artifact_when_it_has_no_entries(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        artifact_mock = Mock(collection_id=COLLECTION_ID, deployments=None)
        mocks.repository.get_artifact_details.return_value = artifact_mock
        mocks.track_entry_repository.has_entries_for_artifact.return_value = False

        result = await mocks.handler._artifact_deletion_checks(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
        )
        assert result == artifact_mock
