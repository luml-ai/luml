import pytest
from luml.handlers.orbits import OrbitHandler
from luml.handlers.permissions import PermissionsHandler
from luml.handlers.relays import RelayHandler
from luml.repositories.orbits import OrbitRepository
from luml.repositories.relays import RelayRepository
from luml.repositories.users import UserRepository
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.seeds import OrganizationFixtureData


@pytest.fixture
def repository(engine: AsyncEngine) -> RelayRepository:
    return RelayRepository(engine)


@pytest.fixture
def relay_handler(
    seeded_organization: OrganizationFixtureData,
    monkeypatch: pytest.MonkeyPatch,
) -> RelayHandler:
    engine = seeded_organization.engine
    monkeypatch.setattr(
        RelayHandler, "_RelayHandler__relay_repo", RelayRepository(engine)
    )
    monkeypatch.setattr(
        PermissionsHandler,
        "_PermissionsHandler__user_repository",
        UserRepository(engine),
    )
    monkeypatch.setattr(
        PermissionsHandler,
        "_PermissionsHandler__orbits_repository",
        OrbitRepository(engine),
    )
    return RelayHandler()


@pytest.fixture
def orbit_handler(
    relay_handler: RelayHandler,
    seeded_organization: OrganizationFixtureData,
    monkeypatch: pytest.MonkeyPatch,
) -> OrbitHandler:
    engine = seeded_organization.engine
    for attribute, repository in (
        ("__orbits_repository", OrbitRepository(engine)),
        ("__user_repository", UserRepository(engine)),
        ("__relay_repository", RelayRepository(engine)),
    ):
        monkeypatch.setattr(OrbitHandler, f"_OrbitHandler{attribute}", repository)
    return OrbitHandler()
