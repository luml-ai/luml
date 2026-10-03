from datetime import datetime

import pytest
from luml.handlers.collections import CollectionHandler
from luml.schemas.collections import Collection, CollectionType

from tests.support.ids import COLLECTION_ID, OTHER_ORBIT_ID
from tests.support.mocks import CollaboratorMocks, mock_collaborators


@pytest.fixture
def mocks() -> CollaboratorMocks[CollectionHandler]:
    return mock_collaborators(CollectionHandler())


def _foreign_collection() -> Collection:
    return Collection(
        id=COLLECTION_ID,
        orbit_id=OTHER_ORBIT_ID,
        description="owner description",
        name="owner-collection",
        type=CollectionType.MODEL,
        tags=["owner"],
        total_artifacts=0,
        created_at=datetime(2026, 1, 1),
        updated_at=None,
    )
