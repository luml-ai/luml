from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from luml.api.orbits.orbits_members import orbit_members_router
from luml.models import AuthUser
from luml.schemas.orbit import OrbitMember, OrbitRole
from luml.schemas.user import UserOut
from starlette.authentication import AuthCredentials, AuthenticationBackend
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
ORBIT_ID = UUID("0199c337-0aa2-7b45-9d21-4f8e3c7a15d0")
MEMBER_ID = UUID("0199c419-b7c1-71d6-8382-5697010cee46")


class _SignedInBackend(AuthenticationBackend):
    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, AuthUser]:
        return AuthCredentials(["authenticated", "jwt"]), AuthUser(
            user_id=USER_ID, email="caller@example.com"
        )


@patch(
    "luml.api.orbits.orbits_members.OrbitHandler.create_orbit_member",
    new_callable=AsyncMock,
)
def test_add_member_returns_created_member(
    mock_create_orbit_member: AsyncMock,
) -> None:
    mock_create_orbit_member.return_value = OrbitMember(
        id=MEMBER_ID,
        orbit_id=ORBIT_ID,
        role=OrbitRole.MEMBER,
        user=UserOut(
            id=MEMBER_ID,
            email="member@example.com",
            full_name="Member",
            disabled=False,
        ),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    app = FastAPI()
    app.include_router(orbit_members_router)
    app.add_middleware(AuthenticationMiddleware, backend=_SignedInBackend())

    response = TestClient(app).post(
        f"/{ORGANIZATION_ID}/orbits/{ORBIT_ID}/members",
        json={"user_id": str(MEMBER_ID), "orbit_id": str(ORBIT_ID), "role": "member"},
    )

    assert response.status_code == 201
    assert response.json()["id"] == str(MEMBER_ID)
    mock_create_orbit_member.assert_awaited_once()
