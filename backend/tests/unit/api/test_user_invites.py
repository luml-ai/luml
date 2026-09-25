from unittest.mock import AsyncMock, patch
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from luml.api.user.user_invites import user_invites_router
from luml.models import AuthUser
from starlette.authentication import AuthCredentials, AuthenticationBackend
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
INVITE_ID = UUID("0199c416-6117-7a3d-a91c-9b4037837882")
USER_EMAIL = "invitee@example.com"


class _SignedInBackend(AuthenticationBackend):
    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, AuthUser]:
        return AuthCredentials(["authenticated", "jwt"]), AuthUser(
            user_id=USER_ID, email=USER_EMAIL
        )


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(user_invites_router)
    app.add_middleware(AuthenticationMiddleware, backend=_SignedInBackend())
    return app


@patch(
    "luml.api.user.user_invites.organization_handler.accept_invite",
    new_callable=AsyncMock,
)
def test_accept_invitation_returns_detail_response(
    mock_accept_invite: AsyncMock,
) -> None:
    app = _app()
    response = TestClient(app).post(f"/invitations/{INVITE_ID}/accept")

    assert response.status_code == 200
    assert response.json() == {"detail": "Invitation accepted successfully"}
    mock_accept_invite.assert_awaited_once_with(INVITE_ID, USER_ID, USER_EMAIL)

    operation = app.openapi()["paths"]["/invitations/{invite_id}/accept"]["post"]
    response_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert response_schema == {"$ref": "#/components/schemas/DetailResponse"}


@patch(
    "luml.api.user.user_invites.organization_handler.accept_invite",
    new_callable=AsyncMock,
)
def test_accept_invitation_does_not_report_success_on_failure(
    mock_accept_invite: AsyncMock,
) -> None:
    mock_accept_invite.side_effect = HTTPException(status_code=404, detail="Not found")

    response = TestClient(_app()).post(f"/invitations/{INVITE_ID}/accept")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}
