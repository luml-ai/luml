import base64
import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from time import time
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from jwt.exceptions import InvalidTokenError

from luml.clients.oauth_providers import OAuthGoogleProvider
from luml.handlers.auth import AuthHandler
from luml.infra.db import engine
from luml.infra.exceptions import AuthError
from luml.repositories.token_blacklist import TokenBlackListRepository
from luml.schemas.platform_admin import (
    GoogleCodeGrant,
    PasswordGrant,
    PlatformAdmin,
    PlatformAdminAuthMethod,
    PlatformAdminToken,
)
from luml.settings import Settings

logger = logging.getLogger("luml.platform_admin.auth")

AUDIENCE = "luml-platform-admin"
ACCESS_TOKEN_TYPE = "platform_admin_access"
OAUTH_STATE_TYPE = "platform_admin_oauth_state"
LOGIN_CODE_TYPE = "platform_admin_login_code"
OAUTH_STATE_EXPIRE = 300
LOGIN_CODE_EXPIRE = 60
ALGORITHM = "HS256"
LOOPBACK_HOST = "127.0.0.1"


class PlatformAdminConfigError(ValueError):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


def code_challenge_for(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _parse_auth_methods(raw: str) -> frozenset[PlatformAdminAuthMethod]:
    names = [name.strip().upper() for name in raw.split(",") if name.strip()]
    try:
        methods = frozenset(PlatformAdminAuthMethod(name) for name in names)
    except ValueError as err:
        allowed = ", ".join(PlatformAdminAuthMethod)
        raise PlatformAdminConfigError(
            f"PLATFORM_ADMIN_AUTH_METHODS accepts only: {allowed}"
        ) from err
    if not methods:
        raise PlatformAdminConfigError("PLATFORM_ADMIN_AUTH_METHODS is empty")
    return methods


@dataclass(frozen=True)
class PlatformAdminConfig:
    admin_email: str | None
    auth_methods: frozenset[PlatformAdminAuthMethod]
    signing_key: str
    token_expire: int
    google_client_id: str
    google_auth_url: str
    google_redirect_uri: str | None = None
    google_hosted_domain: str | None = None

    @property
    def enabled(self) -> bool:
        return self.admin_email is not None

    @classmethod
    def from_settings(cls, settings: Settings) -> PlatformAdminConfig:
        admin_email = settings.PLATFORM_ADMIN_EMAIL
        methods = _parse_auth_methods(settings.PLATFORM_ADMIN_AUTH_METHODS)
        redirect_uri = settings.PLATFORM_ADMIN_GOOGLE_REDIRECT_URI
        if (
            admin_email
            and PlatformAdminAuthMethod.GOOGLE in methods
            and not redirect_uri
        ):
            raise PlatformAdminConfigError(
                "PLATFORM_ADMIN_GOOGLE_REDIRECT_URI is required when GOOGLE is "
                "listed in PLATFORM_ADMIN_AUTH_METHODS"
            )
        # A key derived from the main secret keeps admin and user tokens
        # mutually unverifiable without introducing another secret to manage.
        signing_key = hmac.new(
            settings.AUTH_SECRET_KEY.encode(), AUDIENCE.encode(), hashlib.sha256
        ).hexdigest()
        hosted_domain = settings.PLATFORM_ADMIN_GOOGLE_HOSTED_DOMAIN
        return cls(
            admin_email=normalize_email(admin_email) if admin_email else None,
            auth_methods=methods,
            signing_key=signing_key,
            token_expire=settings.PLATFORM_ADMIN_TOKEN_EXPIRE,
            google_client_id=settings.GOOGLE_CLIENT_ID,
            google_auth_url=settings.GOOGLE_AUTH_URL,
            google_redirect_uri=redirect_uri,
            google_hosted_domain=hosted_domain.lower() if hosted_domain else None,
        )


class PlatformAdminAuthHandler:
    __token_black_list_repository = TokenBlackListRepository(engine)

    def __init__(
        self,
        admin_config: PlatformAdminConfig,
        auth_handler: AuthHandler,
        google_provider: type[OAuthGoogleProvider] = OAuthGoogleProvider,
    ) -> None:
        self.config = admin_config
        self._auth_handler = auth_handler
        self._google_provider = google_provider

    def google_login_url(self, port: int, code_challenge: str) -> str:
        self._require_method(PlatformAdminAuthMethod.GOOGLE)
        state = self._encode(
            {"type": OAUTH_STATE_TYPE, "port": port, "challenge": code_challenge},
            OAUTH_STATE_EXPIRE,
        )
        params = {
            "client_id": self.config.google_client_id,
            "redirect_uri": self.config.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "prompt": "select_account",
            "state": state,
        }
        if self.config.google_hosted_domain:
            params["hd"] = self.config.google_hosted_domain
        return f"{self.config.google_auth_url}?{urlencode(params)}"

    async def google_callback_redirect(
        self, code: str | None, state: str, error: str | None
    ) -> str:
        """Finish the Google leg and return the loopback URL for the client.

        The admin token itself never travels in a URL: the loopback only gets a
        single-use login code bound to the client's PKCE challenge.
        """
        self._require_method(PlatformAdminAuthMethod.GOOGLE)
        state_payload = self._decode(state, OAUTH_STATE_TYPE)
        loopback = f"http://{LOOPBACK_HOST}:{int(state_payload['port'])}/callback"

        if error or not code:
            return f"{loopback}?{urlencode({'error': error or 'missing_code'})}"

        try:
            email = await self._verified_google_admin_email(code)
        except AuthError as err:
            logger.warning("Platform admin Google login rejected: %s", err.message)
            return f"{loopback}?{urlencode({'error': 'access_denied'})}"

        login_code = self._encode(
            {
                "type": LOGIN_CODE_TYPE,
                "sub": email,
                "challenge": state_payload["challenge"],
                "jti": secrets.token_urlsafe(16),
            },
            LOGIN_CODE_EXPIRE,
        )
        return f"{loopback}?{urlencode({'code': login_code})}"

    async def issue_token(
        self, grant: PasswordGrant | GoogleCodeGrant
    ) -> PlatformAdminToken:
        if isinstance(grant, PasswordGrant):
            email = await self._password_admin_email(grant)
            method = PlatformAdminAuthMethod.EMAIL
        else:
            email = await self._login_code_admin_email(grant)
            method = PlatformAdminAuthMethod.GOOGLE

        logger.info("Platform admin token issued for %s via %s", email, method)
        token = self._encode(
            {
                "type": ACCESS_TOKEN_TYPE,
                "sub": email,
                "amr": method.value,
                "jti": secrets.token_urlsafe(16),
            },
            self.config.token_expire,
        )
        return PlatformAdminToken(
            access_token=token, expires_in=self.config.token_expire
        )

    def authenticate(self, token: str) -> PlatformAdmin:
        payload = self._decode(token, ACCESS_TOKEN_TYPE)
        if payload["sub"] != self.config.admin_email:
            raise AuthError("Not a platform admin", 401)
        try:
            method = PlatformAdminAuthMethod(str(payload.get("amr")))
        except ValueError as err:
            raise AuthError("Invalid token", 401) from err
        return PlatformAdmin(
            email=payload["sub"],
            auth_method=method,
            expires_at=payload["exp"],
        )

    async def _verified_google_admin_email(self, code: str) -> str:
        assert self.config.google_redirect_uri is not None
        async with httpx.AsyncClient(timeout=10.0) as client:
            access_token = await self._google_provider.exchange_code_for_token(
                client, code, redirect_uri=self.config.google_redirect_uri
            )
            userinfo = await self._google_provider.get_user_info(client, access_token)

        if not userinfo.email or userinfo.email_verified is not True:
            raise AuthError("Google account email is not verified", 403)
        hosted_domain = self.config.google_hosted_domain
        if hosted_domain and (userinfo.hosted_domain or "").lower() != hosted_domain:
            raise AuthError("Google account is outside the allowed domain", 403)
        email = normalize_email(userinfo.email)
        if email != self.config.admin_email:
            raise AuthError(f"{email} is not a platform admin", 403)
        return email

    async def _password_admin_email(self, grant: PasswordGrant) -> str:
        self._require_method(PlatformAdminAuthMethod.EMAIL)
        email = normalize_email(grant.email)
        if email != self.config.admin_email:
            raise AuthError("Invalid email or password", 401)
        user = await self._auth_handler._authenticate_user(email, grant.password)
        if user.disabled:
            raise AuthError("Account is disabled", 403)
        return email

    async def _login_code_admin_email(self, grant: GoogleCodeGrant) -> str:
        self._require_method(PlatformAdminAuthMethod.GOOGLE)
        payload = self._decode(grant.code, LOGIN_CODE_TYPE)
        if not hmac.compare_digest(
            code_challenge_for(grant.code_verifier), str(payload.get("challenge"))
        ):
            raise AuthError("Invalid code verifier", 400)
        if payload["sub"] != self.config.admin_email:
            raise AuthError("Not a platform admin", 403)
        first_use = await self.__token_black_list_repository.add_token(
            grant.code, int(payload["exp"])
        )
        if not first_use:
            raise AuthError("Login code has already been used", 400)
        return str(payload["sub"])

    def _require_method(self, method: PlatformAdminAuthMethod) -> None:
        if method not in self.config.auth_methods:
            raise AuthError(f"{method} login is disabled for platform admin", 403)

    def _encode(self, claims: dict[str, Any], expires_in: int) -> str:
        now = int(time())
        payload = {**claims, "aud": AUDIENCE, "iat": now, "exp": now + expires_in}
        return jwt.encode(payload, self.config.signing_key, algorithm=ALGORITHM)

    def _decode(self, token: str, expected_type: str) -> dict[str, Any]:
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                self.config.signing_key,
                algorithms=[ALGORITHM],
                audience=AUDIENCE,
                options={"require": ["exp", "iat", "aud"]},
            )
        except InvalidTokenError as err:
            raise AuthError("Invalid or expired token", 401) from err
        if payload.get("type") != expected_type:
            raise AuthError("Invalid token type", 401)
        return payload
