import pytest
from luml.handlers.organizations import OrganizationHandler

from tests.support.mocks import CollaboratorMocks, mock_collaborators


@pytest.fixture
def mocks() -> CollaboratorMocks[OrganizationHandler]:
    return mock_collaborators(OrganizationHandler())
