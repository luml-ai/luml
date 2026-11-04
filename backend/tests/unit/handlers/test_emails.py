import asyncio
import threading
from typing import cast
from unittest.mock import Mock

import pytest
from fastapi import BackgroundTasks
from luml.handlers.emails import EmailHandler
from luml.settings import config


@pytest.fixture(
    params=[
        (
            "send_activation_email",
            ("recipient@example.com", "https://example.com/activate", None),
            "TEMPLATE_ID_ACTIVATION_EMAIL",
            {"name": "", "confirm_email_link": "https://example.com/activate"},
        ),
        (
            "send_password_reset_email",
            ("recipient@example.com", "https://example.com/reset", "Recipient"),
            "TEMPLATE_ID_RESET_PASSWORD_EMAIL",
            {"name": "Recipient", "reset_password_link": "https://example.com/reset"},
        ),
        (
            "send_organization_invite_email",
            ("recipient@example.com", "Sender", "Organization", "https://example.com"),
            "TEMPLATE_ID_ORGANIZATION_INVITE_EMAIL",
            {
                "invite_sender": "Sender",
                "organization": "Organization",
                "open_platform_link": "https://example.com",
            },
        ),
        (
            "send_added_to_orbit_email",
            ("Recipient", "recipient@example.com", "Orbit", "https://example.com"),
            "TEMPLATE_ID_ADDED_TO_ORBIT_EMAIL",
            {
                "name": "Recipient",
                "orbit": "Orbit",
                "open_platform_link": "https://example.com",
            },
        ),
    ],
    ids=["activation", "password_reset", "organization_invite", "orbit_member"],
)
def email_case(
    request: pytest.FixtureRequest,
) -> tuple[str, tuple[str | None, ...], str, dict[str, str]]:
    return cast(tuple[str, tuple[str | None, ...], str, dict[str, str]], request.param)


async def test_send_keeps_event_loop_responsive_and_delivers_message(
    email_case: tuple[str, tuple[str | None, ...], str, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    method_name, args, template_setting, expected_data = email_case
    handler = EmailHandler(sender_email="sender@example.com")
    started = threading.Event()
    release = threading.Event()
    sender_threads: list[int] = []

    def send(message: object) -> None:
        sender_threads.append(threading.get_ident())
        started.set()
        if not release.wait(timeout=5):
            raise TimeoutError("event loop did not release email send")

    client = Mock(send=Mock(side_effect=send))
    monkeypatch.setattr(handler, "_email_client", client)

    async def deliver() -> None:
        await getattr(handler, method_name)(*args)

    delivery = asyncio.create_task(deliver())
    try:
        assert await asyncio.to_thread(started.wait, 5)
        assert len(sender_threads) == 1
        assert sender_threads[0] != threading.get_ident()
        assert not delivery.done()
    finally:
        release.set()
        await asyncio.gather(delivery, return_exceptions=True)
    await delivery

    client.send.assert_called_once()
    message = client.send.call_args.args[0].get()
    assert message["from"]["email"] == handler.sender_email
    assert message["template_id"] == getattr(config, template_setting)
    assert message["personalizations"][0]["to"] == [{"email": "recipient@example.com"}]
    assert message["personalizations"][0]["dynamic_template_data"] == expected_data


async def test_send_propagates_delivery_failure(
    email_case: tuple[str, tuple[str | None, ...], str, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    method_name, args, _, _ = email_case
    handler = EmailHandler()
    failure = RuntimeError("email rejected")
    client = Mock(send=Mock(side_effect=failure))
    monkeypatch.setattr(handler, "_email_client", client)

    with pytest.raises(RuntimeError, match="email rejected") as error:
        await getattr(handler, method_name)(*args)

    assert error.value is failure
    client.send.assert_called_once()


async def test_orbit_email_is_delivered_by_background_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handler = EmailHandler()
    client = Mock()
    monkeypatch.setattr(handler, "_email_client", client)
    background_tasks = BackgroundTasks()
    background_tasks.add_task(
        handler.send_added_to_orbit_email,
        name="Recipient",
        email="recipient@example.com",
        orbit="Orbit",
        link="https://example.com",
    )

    client.send.assert_not_called()
    await background_tasks()

    client.send.assert_called_once()
