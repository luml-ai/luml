import pytest
from luml.repositories.live_session_tokens import LiveSessionTokenRepository
from luml.repositories.live_sessions import LiveSessionRepository
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def repository(engine: AsyncEngine) -> LiveSessionRepository:
    return LiveSessionRepository(engine)


@pytest.fixture
def token_repository(engine: AsyncEngine) -> LiveSessionTokenRepository:
    return LiveSessionTokenRepository(engine)
