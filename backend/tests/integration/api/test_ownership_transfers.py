from unittest.mock import AsyncMock

import pytest
from httpx2 import ASGITransport, AsyncClient
from luml.handlers.ownership_transfers import OwnershipTransferHandler
from luml.infra.security import JWTAuthenticationBackend
from luml.models import AuthUser
from luml.repositories.ownership_transfers import OwnershipTransferRepository
from luml.repositories.users import UserRepository
from luml.schemas.organization import OrgRole
from luml.service import AppService
from starlette.authentication import AuthCredentials

from tests.support.seeds import OrganizationWithMembersFixtureData


async def test_request_and_member_acceptance_end_to_end(
    seeded_organization_with_members: OrganizationWithMembersFixtureData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = seeded_organization_with_members
    recipient = data.members[1]
    auth = AsyncMock(
        return_value=(
            AuthCredentials(["authenticated", "jwt"]),
            AuthUser(user_id=data.user.id, email=data.user.email),
        )
    )
    monkeypatch.setattr(JWTAuthenticationBackend, "authenticate", auth)
    monkeypatch.setattr(
        OwnershipTransferHandler, "repository", OwnershipTransferRepository(data.engine)
    )
    email = AsyncMock()
    monkeypatch.setattr(OwnershipTransferHandler, "email_handler", email)
    async with AsyncClient(
        transport=ASGITransport(app=AppService()), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/v1/organizations/{data.organization.id}/ownership-transfers",
            json={"member_id": str(recipient.id)},
        )
        assert response.status_code == 200
        request_id = response.json()["id"]
        email.send_ownership_transfer_email.assert_awaited_once()
        users = UserRepository(data.engine)
        assert (
            await users.get_organization_member_role(data.organization.id, data.user.id)
            == OrgRole.OWNER
        )
        auth.return_value = (
            AuthCredentials(["authenticated", "jwt"]),
            AuthUser(user_id=recipient.user.id, email=recipient.user.email),
        )
        response = await client.get("/v1/users/me/invitations/ownership-transfers")
        assert [item["id"] for item in response.json()] == [request_id]
        response = await client.post(
            f"/v1/users/me/invitations/ownership-transfers/{data.organization.id}/{request_id}/accept"
        )
        assert response.status_code == 200
        assert (
            await users.get_organization_member_role(
                data.organization.id, recipient.user.id
            )
            == OrgRole.OWNER
        )
        assert email.send_ownership_transfer_email.await_count == 2
        auth.return_value = (
            AuthCredentials(["authenticated", "jwt"]),
            AuthUser(user_id=data.user.id, email=data.user.email),
        )
        response = await client.post(
            f"/v1/organizations/{data.organization.id}/ownership-transfer-notices/read"
        )
        assert [item["status"] for item in response.json()] == ["accepted"]
        response = await client.post(
            f"/v1/organizations/{data.organization.id}/ownership-transfer-notices/read"
        )
        assert response.json() == []
