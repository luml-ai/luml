from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from luml.schemas.organization import OrganizationMember, OrgRole
from luml.schemas.user import UserOut

from tests.support.ids import MEMBER_ID, ORGANIZATION_ID, USER_ID


class TestOrganizationMembers:
    @pytest.mark.parametrize("role", ["member", "admin"])
    def test_direct_membership_creation_is_not_allowed(
        self, client: TestClient, role: str
    ) -> None:
        response = client.post(
            f"/v1/organizations/{ORGANIZATION_ID}/members",
            json={"user_id": str(MEMBER_ID), "role": role},
        )

        assert response.status_code == 405

    def test_direct_membership_creation_is_not_in_openapi(
        self, client: TestClient
    ) -> None:
        schema = client.get("/openapi.json").json()

        assert (
            "post" not in schema["paths"]["/v1/organizations/{organization_id}/members"]
        )

    @patch(
        "luml.api.organization.organization_members.OrganizationHandler.transfer_organization_ownership",
        new_callable=AsyncMock,
    )
    def test_transfer_ownership_returns_new_owner(
        self, mock_transfer: AsyncMock, client: TestClient
    ) -> None:
        mock_transfer.return_value = OrganizationMember(
            id=MEMBER_ID,
            organization_id=ORGANIZATION_ID,
            role=OrgRole.OWNER,
            user=UserOut(id=MEMBER_ID, email="member@example.com", disabled=False),
            created_at=datetime.now(UTC),
        )

        response = client.post(
            f"/v1/organizations/{ORGANIZATION_ID}/members/{MEMBER_ID}/transfer-ownership"
        )

        assert response.status_code == 200
        assert response.json()["role"] == "owner"
        mock_transfer.assert_awaited_once_with(USER_ID, ORGANIZATION_ID, MEMBER_ID)
