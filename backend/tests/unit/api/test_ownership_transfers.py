from unittest.mock import AsyncMock
from uuid import uuid7

import pytest
from fastapi.testclient import TestClient
from luml.api.organization.organization import transfer_handler as organization_handler
from luml.api.user.user_invites import transfer_handler as invitation_handler

from tests.support.ids import ORGANIZATION_ID, USER_ID


def test_pending_and_received_routes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pending = AsyncMock(return_value=None)
    received = AsyncMock(return_value=[])
    monkeypatch.setattr(organization_handler.repository, "pending", pending)
    monkeypatch.setattr(invitation_handler.repository, "list_received", received)
    response = client.get(
        f"/v1/organizations/{ORGANIZATION_ID}/ownership-transfers/pending"
    )
    assert response.status_code == 200
    assert response.json() is None
    assert client.get("/v1/users/me/invitations/ownership-transfers").json() == []
    pending.assert_awaited_once_with(ORGANIZATION_ID, USER_ID)
    received.assert_awaited_once_with(USER_ID)


@pytest.mark.parametrize("action", ["accept", "decline"])
def test_recipient_actions_require_no_settings_access(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    from luml.infra.exceptions import ApplicationError

    resolve = AsyncMock(side_effect=ApplicationError("no longer pending", 409))
    monkeypatch.setattr(invitation_handler, "resolve", resolve)
    request_id = uuid7()
    response = client.post(
        f"/v1/users/me/invitations/ownership-transfers/{ORGANIZATION_ID}/{request_id}/{action}"
    )
    assert response.status_code == 409
    resolve.assert_awaited_once_with(
        ORGANIZATION_ID,
        request_id,
        USER_ID,
        "accepted" if action == "accept" else "declined",
    )


def test_request_validates_member_identifier(client: TestClient) -> None:
    response = client.post(
        f"/v1/organizations/{ORGANIZATION_ID}/ownership-transfers",
        json={"member_id": "invalid"},
    )
    assert response.status_code == 422
