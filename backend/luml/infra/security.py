from starlette.authentication import AuthCredentials, AuthenticationBackend
from starlette.requests import HTTPConnection

from luml.handlers.api_keys import APIKeyHandler
from luml.handlers.auth import AuthHandler
from luml.handlers.satellites import SatelliteHandler
from luml.infra.exceptions import AuthError
from luml.models import AuthSatellite, AuthUser
from luml.settings import config

type AuthPrincipal = AuthUser | AuthSatellite


class JWTAuthenticationBackend(AuthenticationBackend):
    def __init__(self) -> None:
        self.auth_handler = AuthHandler(
            secret_key=config.AUTH_SECRET_KEY,
        )
        self.api_key_handler = APIKeyHandler()
        self.satellite_handler = SatelliteHandler()

    async def _authenticate_with_api_key(
        self, token: str
    ) -> tuple[AuthCredentials, AuthPrincipal] | None:
        user = await self.api_key_handler.authenticate_api_key(token)
        if user:
            auth_user = AuthUser(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                disabled=user.disabled,
            )
            return AuthCredentials(["authenticated", "api_key"]), auth_user
        return None

    async def _authenticate_with_satellite_key(
        self, token: str
    ) -> tuple[AuthCredentials, AuthPrincipal] | None:
        sat = await self.satellite_handler.authenticate_api_key(token)
        if sat:
            await self.satellite_handler.touch_last_seen(sat.id)
            auth_sat = AuthSatellite(satellite_id=sat.id, orbit_id=sat.orbit_id)
            return AuthCredentials(["authenticated", "satellite"]), auth_sat
        return None

    async def _authenticate_with_jwt_token(
        self, token: str
    ) -> tuple[AuthCredentials, AuthPrincipal] | None:
        if await self.auth_handler.is_token_blacklisted(token):
            return None
        try:
            email = self.auth_handler._verify_token(token)
            user = await self.auth_handler.handle_get_current_user(email)
            auth_user = AuthUser(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                disabled=user.disabled,
            )
            return AuthCredentials(["authenticated", "jwt"]), auth_user
        except AuthError:
            return None

    async def authenticate(
        self,
        conn: HTTPConnection,
    ) -> tuple[AuthCredentials, AuthPrincipal] | None:
        authorization: str | None = conn.headers.get("Authorization")
        token: str | None = None

        if authorization:
            try:
                scheme, token_value = authorization.split()
                if scheme.lower() != "bearer":
                    return None
                token = token_value
            except ValueError:
                return None
        else:
            token = conn.cookies.get("access_token")

        if token:
            if token.startswith("dfs_"):
                return await self._authenticate_with_api_key(token)
            if token.startswith("dfssat_"):
                return await self._authenticate_with_satellite_key(token)
            return await self._authenticate_with_jwt_token(token)

        return None
