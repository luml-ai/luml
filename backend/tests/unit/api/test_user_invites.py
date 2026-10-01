from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from luml.service import AppService

from tests.support.auth import CALLER_EMAIL
from tests.support.ids import INVITE_ID, USER_ID

ACCEPT_PATH = f"/v1/users/me/invitations/{INVITE_ID}/accept"


class TestUserInvites:
    @patch(
        "luml.api.user.user_invites.organization_handler.accept_invite",
        new_callable=AsyncMock,
    )
    def test_accept_invitation_returns_detail_response(
        self, mock_accept_invite: AsyncMock, app: AppService, client: TestClient
    ) -> None:
        response = client.post(ACCEPT_PATH)

        assert response.status_code == 200
        assert response.json() == {"detail": "Invitation accepted successfully"}
        mock_accept_invite.assert_awaited_once_with(INVITE_ID, USER_ID, CALLER_EMAIL)

        operation = app.openapi()["paths"][
            "/v1/users/me/invitations/{invite_id}/accept"
        ]["post"]
        response_schema = operation["responses"]["200"]["content"]["application/json"][
            "schema"
        ]
        assert response_schema == {"$ref": "#/components/schemas/DetailResponse"}

    @patch(
        "luml.api.user.user_invites.organization_handler.accept_invite",
        new_callable=AsyncMock,
    )
    def test_accept_invitation_does_not_report_success_on_failure(
        self, mock_accept_invite: AsyncMock, client: TestClient
    ) -> None:
        mock_accept_invite.side_effect = HTTPException(
            status_code=404, detail="Not found"
        )

        response = client.post(ACCEPT_PATH)

        assert response.status_code == 404
        assert response.json() == {"detail": "Not found"}
