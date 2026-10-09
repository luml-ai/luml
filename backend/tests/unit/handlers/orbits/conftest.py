import datetime
from collections.abc import Callable, Coroutine
from typing import Any
from unittest.mock import Mock
from uuid import UUID, uuid7

import pytest
from luml.handlers.orbits import OrbitHandler
from luml.schemas.orbit import Orbit, OrbitDetails, OrbitMember, OrbitRole
from luml.schemas.user import UserOut

from tests.support.ids import OTHER_ORBIT_ID, OTHER_ORGANIZATION_ID
from tests.support.mocks import CollaboratorMocks, mock_collaborators

FOREIGN_BUCKET_SECRET_ID = UUID("0199c337-0aa3-7e57-b8f0-9a1c6d2e4f83")


@pytest.fixture
def mocks() -> CollaboratorMocks[OrbitHandler]:
    return mock_collaborators(OrbitHandler())


@pytest.fixture
def orbit() -> Orbit:
    return Orbit(
        id=uuid7(),
        name="test",
        organization_id=uuid7(),
        bucket_secret_id=uuid7(),
        total_members=1,
        role=None,
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )


@pytest.fixture
def orbit_member() -> OrbitMember:
    return OrbitMember(
        id=uuid7(),
        orbit_id=uuid7(),
        role=OrbitRole.MEMBER,
        user=UserOut(
            id=uuid7(),
            email=f"email_{uuid7()}@example.org",
            full_name="Kathy Hall",
            disabled=False,
            photo=None,
        ),
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )


@pytest.fixture
def orbit_details(orbit_member: OrbitMember) -> OrbitDetails:
    return OrbitDetails(
        id=uuid7(),
        name="test",
        organization_id=uuid7(),
        bucket_secret_id=uuid7(),
        members=[orbit_member],
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )


def _scoped_bucket_secret(
    stored: Mock,
) -> Callable[..., Coroutine[Any, Any, Mock | None]]:
    async def scoped_get(
        secret_id: UUID, organization_id: UUID | None = None
    ) -> Mock | None:
        if secret_id != stored.id:
            return None
        if organization_id is not None and stored.organization_id != organization_id:
            return None
        return stored

    return scoped_get


def _owner_orbits() -> dict[UUID, Orbit]:
    return {
        OTHER_ORBIT_ID: Orbit(
            id=OTHER_ORBIT_ID,
            name="owner-orbit",
            organization_id=OTHER_ORGANIZATION_ID,
            bucket_secret_id=FOREIGN_BUCKET_SECRET_ID,
            total_members=1,
            role=None,
            created_at=datetime.datetime.now(),
            updated_at=None,
        )
    }
