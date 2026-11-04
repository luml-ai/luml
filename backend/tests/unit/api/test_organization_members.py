import pytest
from fastapi.testclient import TestClient

from tests.support.ids import MEMBER_ID, ORGANIZATION_ID


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
