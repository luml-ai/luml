from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from luml.api.organization.organization_members import members_router
from luml.models import AuthUser
from luml.schemas.organization import (
    OrganizationMember,
    OrganizationMemberCreateIn,
    OrgRole,
)
from luml.schemas.user import UserOut
from starlette.authentication import AuthCredentials, AuthenticationBackend
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
OTHER_ORGANIZATION_ID = UUID("0199c43e-8b7b-7ae8-a84b-3ec65bb63a17")
NEW_MEMBER_USER_ID = UUID("0199c419-b7c1-71d6-8382-5697010cee46")


class _SignedInBackend(AuthenticationBackend):
    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, AuthUser]:
        return AuthCredentials(["authenticated", "jwt"]), AuthUser(
            user_id=USER_ID, email="caller@example.com"
        )


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(members_router)
    app.add_middleware(AuthenticationMiddleware, backend=_SignedInBackend())
    return TestClient(app)


class TestOrganizationMembers:
    @patch(
        "luml.handlers.organizations.OrganizationHandler.add_organization_member",
        new_callable=AsyncMock,
    )
    def test_add_member_ignores_body_organization_id(
        self, mock_add_organization_member: AsyncMock
    ) -> None:
        mock_add_organization_member.return_value = OrganizationMember(
            id=UUID("0199c337-09f3-753e-9def-b27745e69be6"),
            organization_id=ORGANIZATION_ID,
            role=OrgRole.MEMBER,
            user=UserOut(
                id=NEW_MEMBER_USER_ID,
                email="member@example.com",
                full_name="Member",
                disabled=False,
            ),
            created_at=datetime.now(UTC),
        )

        response = _client().post(
            f"/{ORGANIZATION_ID}/members",
            json={
                "user_id": str(NEW_MEMBER_USER_ID),
                "organization_id": str(OTHER_ORGANIZATION_ID),
                "role": "member",
            },
        )

        assert response.status_code == 200
        mock_add_organization_member.assert_awaited_once_with(
            USER_ID,
            ORGANIZATION_ID,
            OrganizationMemberCreateIn(user_id=NEW_MEMBER_USER_ID, role=OrgRole.MEMBER),
        )
