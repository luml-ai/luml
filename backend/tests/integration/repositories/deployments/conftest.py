import pytest
from luml.repositories.deployments import DeploymentRepository
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def repository(engine: AsyncEngine) -> DeploymentRepository:
    return DeploymentRepository(engine)
