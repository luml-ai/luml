from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from luml.api.organization.organization_invites import invites_router
from luml.models import AuthUser
from luml.schemas.organization import (
    CreateOrganizationInviteIn,
    OrganizationInvite,
    OrgRole,
)
from starlette.authentication import AuthCredentials, AuthenticationBackend
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
OTHER_ORGANIZATION_ID = UUID("0199c43e-8b7b-7ae8-a84b-3ec65bb63a17")
INVITE_ID = UUID("0199c416-6117-7a3d-a91c-9b4037837882")
INVITEE_EMAIL = "invitee@example.com"


class _SignedInBackend(AuthenticationBackend):
    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, AuthUser]:
        return AuthCredentials(["authenticated", "jwt"]), AuthUser(
            user_id=USER_ID, email="caller@example.com"
        )


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(invites_router)
    app.add_middleware(AuthenticationMiddleware, backend=_SignedInBackend())
    return TestClient(app)


class TestOrganizationInvites:
    @patch(
        "luml.handlers.organizations.OrganizationHandler.send_invite",
        new_callable=AsyncMock,
    )
    def test_create_invite_ignores_body_organization_id(
        self, mock_send_invite: AsyncMock
    ) -> None:
        mock_send_invite.return_value = OrganizationInvite(
            id=INVITE_ID,
            email=INVITEE_EMAIL,
            role=OrgRole.MEMBER,
            organization_id=ORGANIZATION_ID,
            created_at=datetime.now(UTC),
        )

        response = _client().post(
            f"/{ORGANIZATION_ID}/invitations",
            json={
                "email": INVITEE_EMAIL,
                "role": "member",
                "organization_id": str(OTHER_ORGANIZATION_ID),
            },
        )

        assert response.status_code == 200
        mock_send_invite.assert_awaited_once_with(
            USER_ID,
            ORGANIZATION_ID,
            CreateOrganizationInviteIn(email=INVITEE_EMAIL, role=OrgRole.MEMBER),
        )
