from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from luml.schemas.orbit import OrbitMember, OrbitRole, UpdateOrbitMember
from luml.schemas.user import UserOut

from tests.support.ids import MEMBER_ID, ORBIT_ID, ORGANIZATION_ID, USER_ID


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

    @patch(
        "luml.api.orbits.orbits_members.OrbitHandler.update_orbit_member",
        new_callable=AsyncMock,
    )
    def test_update_member_passes_path_id_when_body_id_differs(
        self, mock_update_orbit_member: AsyncMock, client: TestClient
    ) -> None:
        mock_update_orbit_member.return_value = OrbitMember(
            id=MEMBER_ID,
            orbit_id=ORBIT_ID,
            role=OrbitRole.ADMIN,
            user=UserOut(id=MEMBER_ID, email="member@example.com", disabled=False),
            created_at=datetime.now(UTC),
        )

        response = client.patch(
            f"/v1/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}/members/{MEMBER_ID}",
            json={"id": str(USER_ID), "role": "admin"},
        )

        assert response.status_code == 200
        assert response.json()["id"] == str(MEMBER_ID)
        mock_update_orbit_member.assert_awaited_once_with(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            MEMBER_ID,
            UpdateOrbitMember(id=USER_ID, role=OrbitRole.ADMIN),
        )

    @pytest.mark.parametrize("method", ["patch", "delete"])
    @patch(
        "luml.api.orbits.orbits_members.OrbitHandler.update_orbit_member",
        new_callable=AsyncMock,
    )
    @patch(
        "luml.api.orbits.orbits_members.OrbitHandler.delete_orbit_member",
        new_callable=AsyncMock,
    )
    def test_mutation_rejects_invalid_path_id(
        self,
        mock_delete: AsyncMock,
        mock_update: AsyncMock,
        client: TestClient,
        method: str,
    ) -> None:
        response = client.request(
            method,
            f"/v1/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}/members/invalid",
            json={"id": str(MEMBER_ID), "role": "admin"} if method == "patch" else None,
        )

        assert response.status_code == 422
        mock_update.assert_not_awaited()
        mock_delete.assert_not_awaited()
