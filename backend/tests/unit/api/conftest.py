from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from luml.infra.security import JWTAuthenticationBackend
from luml.service import AppService

from tests.support.auth import SIGNED_IN_USER, Principal


@pytest.fixture(scope="session")
def app() -> AppService:
    return AppService()


@pytest.fixture
def principal(request: pytest.FixtureRequest) -> Principal:
    return getattr(request, "param", SIGNED_IN_USER)


@pytest.fixture
def client(app: AppService, principal: Principal) -> Iterator[TestClient]:
    with (
        patch.object(
            JWTAuthenticationBackend,
            "authenticate",
            new=AsyncMock(return_value=principal),
        ),
        TestClient(app) as test_client,
    ):
        yield test_client
