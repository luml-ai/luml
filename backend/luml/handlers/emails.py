import asyncio

from pydantic import EmailStr
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from luml.schemas.organization import OwnershipTransfer
from luml.settings import config


class EmailHandler:
    _email_client = SendGridAPIClient(config.SENDGRID_API_KEY)

    def __init__(self, sender_email: EmailStr = config.SENDER_EMAIL) -> None:
        self.sender_email = sender_email

    async def send_activation_email(
        self, email: EmailStr, activation_link: str, name: str | None
    ) -> None:
        message = Mail(
            from_email=self.sender_email,
            to_emails=str(email),
            subject="Welcome to LUML AI",
        )
        message.template_id = config.TEMPLATE_ID_ACTIVATION_EMAIL
        message.dynamic_template_data = {
            "name": name or "",
            "confirm_email_link": activation_link,
        }

        await asyncio.to_thread(self._email_client.send, message)

    async def send_password_reset_email(
        self, email: EmailStr, reset_password_link: str, name: str | None
    ) -> None:
        message = Mail(
            from_email=self.sender_email,
            to_emails=str(email),
            subject="Reset Your Password",
        )
        message.template_id = config.TEMPLATE_ID_RESET_PASSWORD_EMAIL
        message.dynamic_template_data = {
            "reset_password_link": reset_password_link,
            "name": name or "",
        }

        await asyncio.to_thread(self._email_client.send, message)

    async def send_organization_invite_email(
        self, email: EmailStr, sender: str, organization: str, link: str
    ) -> None:
        message = Mail(
            from_email=self.sender_email,
            to_emails=str(email),
        )
        message.template_id = config.TEMPLATE_ID_ORGANIZATION_INVITE_EMAIL
        message.dynamic_template_data = {
            "invite_sender": sender or "",
            "organization": organization,
            "open_platform_link": link,
        }

        await asyncio.to_thread(self._email_client.send, message)

    async def send_added_to_orbit_email(
        self, name: str, email: EmailStr, orbit: str, link: str
    ) -> None:
        message = Mail(
            from_email=self.sender_email,
            to_emails=str(email),
        )
        message.template_id = config.TEMPLATE_ID_ADDED_TO_ORBIT_EMAIL
        message.dynamic_template_data = {
            "name": name,
            "orbit": orbit or "",
            "open_platform_link": link,
        }

        await asyncio.to_thread(self._email_client.send, message)

    async def send_ownership_transfer_email(
        self, request: OwnershipTransfer, *, result: bool
    ) -> None:
        template = (
            config.TEMPLATE_ID_OWNERSHIP_TRANSFER_RESULT_EMAIL
            if result
            else config.TEMPLATE_ID_OWNERSHIP_TRANSFER_REQUEST_EMAIL
        )
        if not template:
            raise ValueError("Ownership transfer email template is not configured")
        message = Mail(
            from_email=self.sender_email,
            to_emails=request.sender_email if result else request.recipient_email,
        )
        message.template_id = template
        message.dynamic_template_data = {
            "organization": request.organization_name,
            "sender": request.sender_email,
            "recipient": request.recipient_email,
            "expires_at": request.expires_at.isoformat(),
            "status": request.status,
            "open_platform_link": f"{config.APP_EMAIL_URL.rstrip('/')}/invitations"
            if not result
            else config.APP_EMAIL_URL,
        }
        await asyncio.to_thread(self._email_client.send, message)
