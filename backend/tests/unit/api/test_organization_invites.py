from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from luml.schemas.organization import (
    CreateOrganizationInviteIn,
    OrganizationInvite,
    OrgRole,
)

from tests.support.ids import (
    INVITE_ID,
    ORGANIZATION_ID,
    OTHER_ORGANIZATION_ID,
    USER_ID,
)

INVITEE_EMAIL = "invitee@example.com"


class TestOrganizationInvites:
    @patch(
        "luml.handlers.organizations.OrganizationHandler.send_invite",
        new_callable=AsyncMock,
    )
    def test_create_invite_ignores_body_organization_id(
        self, mock_send_invite: AsyncMock, client: TestClient
    ) -> None:
        mock_send_invite.return_value = OrganizationInvite(
            id=INVITE_ID,
            email=INVITEE_EMAIL,
            role=OrgRole.MEMBER,
            organization_id=ORGANIZATION_ID,
            created_at=datetime.now(UTC),
        )

        response = client.post(
            f"/v1/organizations/{ORGANIZATION_ID}/invitations",
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
