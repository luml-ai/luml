from datetime import UTC, datetime, timedelta
from typing import Literal
from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest
from luml.handlers.emails import EmailHandler
from luml.handlers.ownership_transfers import OwnershipTransferHandler
from luml.schemas.organization import OwnershipTransfer
from luml.settings import config


@pytest.fixture
def transfer() -> OwnershipTransfer:
    return OwnershipTransfer(
        id=uuid7(),
        organization_id=uuid7(),
        organization_name="Test organization",
        sender_id=uuid7(),
        sender_email="owner@example.com",
        recipient_id=uuid7(),
        recipient_email="member@example.com",
        status="pending",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )


@pytest.mark.parametrize("result", [False, True])
async def test_transfer_email_template_recipient_and_link(
    transfer: OwnershipTransfer, monkeypatch: pytest.MonkeyPatch, result: bool
) -> None:
    monkeypatch.setattr(
        config, "TEMPLATE_ID_OWNERSHIP_TRANSFER_REQUEST_EMAIL", "request-template"
    )
    monkeypatch.setattr(
        config, "TEMPLATE_ID_OWNERSHIP_TRANSFER_RESULT_EMAIL", "result-template"
    )
    monkeypatch.setattr(config, "APP_EMAIL_URL", "https://app.example.com/")
    handler = EmailHandler(sender_email="sender@example.com")
    client = Mock()
    monkeypatch.setattr(handler, "_email_client", client)
    if result:
        transfer = transfer.model_copy(update={"status": "accepted"})
    await handler.send_ownership_transfer_email(transfer, result=result)
    message = client.send.call_args.args[0].get()
    assert message["template_id"] == (
        "result-template" if result else "request-template"
    )
    personalization = message["personalizations"][0]
    assert personalization["to"][0]["email"] == (
        transfer.sender_email if result else transfer.recipient_email
    )
    assert personalization["dynamic_template_data"] == (
        {
            "organization": "Test organization",
            "recipient": "member@example.com",
            "status": "accepted",
            "open_platform_link": "https://app.example.com/organization/"
            f"{transfer.organization_id}",
        }
        if result
        else {
            "invite_sender": "owner@example.com",
            "organization": "Test organization",
            "open_platform_link": "https://app.example.com/invitations",
        }
    )


async def test_unconfigured_email_does_not_silently_succeed(
    transfer: OwnershipTransfer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "TEMPLATE_ID_OWNERSHIP_TRANSFER_REQUEST_EMAIL", "")
    with pytest.raises(ValueError, match="not configured"):
        await EmailHandler().send_ownership_transfer_email(transfer, result=False)


async def test_request_email_failure_preserves_saved_request(
    transfer: OwnershipTransfer, monkeypatch: pytest.MonkeyPatch
) -> None:
    handler = OwnershipTransferHandler()
    repository = Mock(create=AsyncMock(return_value=transfer))
    email = Mock(send_ownership_transfer_email=AsyncMock(side_effect=RuntimeError))
    monkeypatch.setattr(handler, "repository", repository)
    monkeypatch.setattr(handler, "email_handler", email)
    result = await handler.create(transfer.organization_id, transfer.sender_id, uuid7())
    assert result.email_delivery_failed is True
    repository.create.assert_awaited_once()


@pytest.mark.parametrize("action", ["accepted", "declined", "cancelled"])
async def test_only_recipient_responses_send_result_email(
    transfer: OwnershipTransfer,
    monkeypatch: pytest.MonkeyPatch,
    action: Literal["accepted", "declined", "cancelled"],
) -> None:
    handler = OwnershipTransferHandler()
    repository = Mock(resolve=AsyncMock(return_value=transfer))
    email = Mock(send_ownership_transfer_email=AsyncMock())
    monkeypatch.setattr(handler, "repository", repository)
    monkeypatch.setattr(handler, "email_handler", email)
    assert transfer.recipient_id is not None
    await handler.resolve(
        transfer.organization_id, transfer.id, transfer.recipient_id, action
    )
    assert email.send_ownership_transfer_email.await_count == (
        0 if action == "cancelled" else 1
    )
