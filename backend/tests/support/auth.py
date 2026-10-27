from uuid import UUID

from luml.models import AuthRelay, AuthSatellite, AuthUser
from starlette.authentication import AuthCredentials

from tests.support.ids import RELAY_ID, USER_ID

type Principal = tuple[AuthCredentials, AuthUser | AuthSatellite | AuthRelay] | None

CALLER_EMAIL = "caller@example.com"

SIGNED_IN_USER: Principal = (
    AuthCredentials(["authenticated", "jwt"]),
    AuthUser(user_id=USER_ID, email=CALLER_EMAIL),
)

API_KEY_USER: Principal = (
    AuthCredentials(["authenticated", "api_key"]),
    AuthUser(user_id=USER_ID, email=CALLER_EMAIL),
)

ANONYMOUS: Principal = None


def satellite(satellite_id: UUID, orbit_id: UUID) -> Principal:
    return (
        AuthCredentials(["authenticated", "satellite"]),
        AuthSatellite(satellite_id=satellite_id, orbit_id=orbit_id),
    )


def relay(relay_id: UUID = RELAY_ID) -> Principal:
    return AuthCredentials(["authenticated", "relay"]), AuthRelay(relay_id)
