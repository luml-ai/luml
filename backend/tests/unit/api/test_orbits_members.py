from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

from fastapi.testclient import TestClient
from luml.schemas.orbit import OrbitMember, OrbitRole
from luml.schemas.user import UserOut

from tests.support.ids import MEMBER_ID, ORGANIZATION_ID

ORBIT_ID = UUID("0199c337-0aa2-7b45-9d21-4f8e3c7a15d0")


class TestOrbitsMembers:
    @patch(
        "luml.api.orbits.orbits_members.OrbitHandler.create_orbit_member",
        new_callable=AsyncMock,
    )
    def test_add_member_returns_created_member(
        self, mock_create_orbit_member: AsyncMock, client: TestClient
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

        response = client.post(
            f"/v1/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}/members",
            json={
                "user_id": str(MEMBER_ID),
                "orbit_id": str(ORBIT_ID),
                "role": "member",
            },
        )

        assert response.status_code == 201
        assert response.json()["id"] == str(MEMBER_ID)
        mock_create_orbit_member.assert_awaited_once()
