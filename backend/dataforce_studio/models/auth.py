from pydantic import EmailStr
from starlette.authentication import BaseUser

from dataforce_studio.schemas.base import ShortUUID


class AuthUser(BaseUser):
    def __init__(
        self,
        user_id: str,
        email: EmailStr,
        full_name: str | None = None,
        disabled: bool | None = None,
    ) -> None:
        self.id = user_id
        self.email = email
        self.full_name = full_name
        self.disabled = disabled

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> EmailStr:
        return self.email


class AuthSatellite(BaseUser):
    def __init__(self, satellite_id: str, orbit_id: str) -> None:
        self.id = satellite_id
        self.orbit_id = orbit_id

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return f"satellite-{self.id}"
