from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

from fastapi.testclient import TestClient
from luml.schemas.organization import (
    OrganizationMember,
    OrganizationMemberCreateIn,
    OrgRole,
)
from luml.schemas.user import UserOut

from tests.support.ids import (
    MEMBER_ID,
    ORGANIZATION_ID,
    OTHER_ORGANIZATION_ID,
    USER_ID,
)


class TestOrganizationMembers:
    @patch(
        "luml.handlers.organizations.OrganizationHandler.add_organization_member",
        new_callable=AsyncMock,
    )
    def test_add_member_ignores_body_organization_id(
        self, mock_add_organization_member: AsyncMock, client: TestClient
    ) -> None:
        mock_add_organization_member.return_value = OrganizationMember(
            id=UUID("0199c337-09f3-753e-9def-b27745e69be6"),
            organization_id=ORGANIZATION_ID,
            role=OrgRole.MEMBER,
            user=UserOut(
                id=MEMBER_ID,
                email="member@example.com",
                full_name="Member",
                disabled=False,
            ),
            created_at=datetime.now(UTC),
        )

        response = client.post(
            f"/v1/organizations/{ORGANIZATION_ID}/members",
            json={
                "user_id": str(MEMBER_ID),
                "organization_id": str(OTHER_ORGANIZATION_ID),
                "role": "member",
            },
        )

        assert response.status_code == 200
        mock_add_organization_member.assert_awaited_once_with(
            USER_ID,
            ORGANIZATION_ID,
            OrganizationMemberCreateIn(user_id=MEMBER_ID, role=OrgRole.MEMBER),
        )
