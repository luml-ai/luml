import pytest
from luml.handlers.satellites import SatelliteHandler

from tests.support.mocks import CollaboratorMocks, mock_collaborators


@pytest.fixture
def mocks() -> CollaboratorMocks[SatelliteHandler]:
    return mock_collaborators(SatelliteHandler())
