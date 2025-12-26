from pydantic import EmailStr
from sendgrid import SendGridAPIClient  # type: ignore
from sendgrid.helpers.mail import Mail  # type: ignore

from luml.settings import config


class EmailHandler:
    _email_client = SendGridAPIClient(config.SENDGRID_API_KEY)

    def __init__(self, sender_email: EmailStr = config.SENDER_EMAIL) -> None:
        self.sender_email = sender_email

    def send_activation_email(
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

        self._email_client.send(message)

    def send_password_reset_email(
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

        self._email_client.send(message)

    def send_organization_invite_email(
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

        self._email_client.send(message)

    def send_added_to_orbit_email(
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

        self._email_client.send(message)
