from time import time
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import httpx
import jwt
import pytest
from luml.clients.oauth_providers import OAuthGoogleProvider
from luml.handlers.auth import AuthHandler
from luml.handlers.platform_admin_auth import (
    AUDIENCE,
    PlatformAdminAuthHandler,
    PlatformAdminConfig,
    PlatformAdminConfigError,
    code_challenge_for,
)
from luml.infra.exceptions import AuthError
from luml.schemas.auth import UserInfo
from luml.schemas.platform_admin import (
    GoogleCodeGrant,
    PasswordGrant,
    PlatformAdminAuthMethod,
)
from luml.schemas.user import AuthProvider, User
from luml.settings import config

ADMIN_EMAIL = "admin@luml.ai"
REDIRECT_URI = "https://api.example.com/v1/platform-admin/auth/google/callback"
CODE_VERIFIER = "v" * 43
PORT = 53682

ADD_TOKEN = "luml.handlers.platform_admin_auth.TokenBlackListRepository.add_token"


def _config(**overrides: object) -> PlatformAdminConfig:
    settings: dict[str, object] = {
        "PLATFORM_ADMIN_EMAIL": ADMIN_EMAIL,
        "PLATFORM_ADMIN_AUTH_METHODS": "GOOGLE,EMAIL",
        "PLATFORM_ADMIN_GOOGLE_REDIRECT_URI": REDIRECT_URI,
        "PLATFORM_ADMIN_GOOGLE_HOSTED_DOMAIN": "luml.ai",
    }
    settings.update(overrides)
    return PlatformAdminConfig.from_settings(config.model_copy(update=settings))


def _google_provider(userinfo: UserInfo) -> type[OAuthGoogleProvider]:
    class FakeGoogleProvider(OAuthGoogleProvider):
        @staticmethod
        async def exchange_code_for_token(
            client: httpx.AsyncClient, code: str, redirect_uri: str = ""
        ) -> str:
            assert redirect_uri == REDIRECT_URI
            return "google-access-token"

        @staticmethod
        async def get_user_info(
            client: httpx.AsyncClient, access_token: str
        ) -> UserInfo:
            return userinfo

    return FakeGoogleProvider


def _handler(
    admin_config: PlatformAdminConfig | None = None,
    userinfo: UserInfo | None = None,
) -> PlatformAdminAuthHandler:
    return PlatformAdminAuthHandler(
        admin_config or _config(),
        AuthHandler(secret_key=config.AUTH_SECRET_KEY),
        _google_provider(
            userinfo
            or UserInfo(
                email="Admin@luml.ai",
                full_name="Admin",
                email_verified=True,
                hosted_domain="luml.ai",
            )
        ),
    )


def _db_user(disabled: bool = False) -> User:
    return User(
        id=UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b"),
        email=ADMIN_EMAIL,
        auth_method=AuthProvider.EMAIL,
        email_verified=True,
        disabled=disabled,
    )


def _query(url: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlparse(url).query).items()}


async def _google_login_code(handler: PlatformAdminAuthHandler) -> str:
    login_url = handler.google_login_url(PORT, code_challenge_for(CODE_VERIFIER))
    redirect = await handler.google_callback_redirect(
        "google-code", _query(login_url)["state"], None
    )
    assert redirect.startswith(f"http://127.0.0.1:{PORT}/callback?")
    return _query(redirect)["code"]


class TestPlatformAdminConfig:
    def test_disabled_without_admin_email(self) -> None:
        admin_config = _config(
            PLATFORM_ADMIN_EMAIL=None, PLATFORM_ADMIN_GOOGLE_REDIRECT_URI=None
        )

        assert not admin_config.enabled

    def test_defaults_to_google_only(self) -> None:
        admin_config = PlatformAdminConfig.from_settings(
            config.model_copy(
                update={
                    "PLATFORM_ADMIN_EMAIL": ADMIN_EMAIL,
                    "PLATFORM_ADMIN_GOOGLE_REDIRECT_URI": REDIRECT_URI,
                }
            )
        )

        assert admin_config.auth_methods == {PlatformAdminAuthMethod.GOOGLE}

    def test_normalizes_admin_email_and_methods(self) -> None:
        admin_config = _config(
            PLATFORM_ADMIN_EMAIL="  Admin@LUML.ai ",
            PLATFORM_ADMIN_AUTH_METHODS=" email , google ",
        )

        assert admin_config.admin_email == ADMIN_EMAIL
        assert admin_config.auth_methods == set(PlatformAdminAuthMethod)

    def test_google_requires_redirect_uri_when_enabled(self) -> None:
        with pytest.raises(PlatformAdminConfigError, match="REDIRECT_URI"):
            _config(PLATFORM_ADMIN_GOOGLE_REDIRECT_URI=None)

    def test_email_only_does_not_require_redirect_uri(self) -> None:
        admin_config = _config(
            PLATFORM_ADMIN_AUTH_METHODS="EMAIL", PLATFORM_ADMIN_GOOGLE_REDIRECT_URI=None
        )

        assert admin_config.auth_methods == {PlatformAdminAuthMethod.EMAIL}

    @pytest.mark.parametrize("methods", ["MICROSOFT", "GOOGLE,SAML", " , "])
    def test_rejects_unknown_or_empty_methods(self, methods: str) -> None:
        with pytest.raises(PlatformAdminConfigError):
            _config(PLATFORM_ADMIN_AUTH_METHODS=methods)

    def test_signing_key_differs_from_user_secret(self) -> None:
        assert _config().signing_key != config.AUTH_SECRET_KEY


class TestPlatformAdminTokens:
    @patch.object(AuthHandler, "_authenticate_user", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_password_grant_issues_verifiable_token(
        self, mock_authenticate_user: AsyncMock
    ) -> None:
        mock_authenticate_user.return_value = _db_user()
        handler = _handler()

        token = await handler.issue_token(
            PasswordGrant(grant_type="password", email="ADMIN@luml.ai", password="pw")
        )
        admin = handler.authenticate(token.access_token)

        assert admin.email == ADMIN_EMAIL
        assert admin.auth_method == PlatformAdminAuthMethod.EMAIL
        assert token.expires_in == 3600
        mock_authenticate_user.assert_awaited_once_with(ADMIN_EMAIL, "pw")

    def test_user_access_token_is_not_an_admin_token(self) -> None:
        user_tokens = AuthHandler(secret_key=config.AUTH_SECRET_KEY)._create_tokens(
            ADMIN_EMAIL
        )

        with pytest.raises(AuthError):
            _handler().authenticate(user_tokens.access_token)

    @patch.object(AuthHandler, "_authenticate_user", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_admin_token_is_not_a_user_token(
        self, mock_authenticate_user: AsyncMock
    ) -> None:
        mock_authenticate_user.return_value = _db_user()
        token = await _handler().issue_token(
            PasswordGrant(grant_type="password", email=ADMIN_EMAIL, password="pw")
        )

        with pytest.raises(AuthError):
            AuthHandler(secret_key=config.AUTH_SECRET_KEY)._verify_token(
                token.access_token
            )

    @patch.object(AuthHandler, "_authenticate_user", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_token_stops_working_when_admin_email_changes(
        self, mock_authenticate_user: AsyncMock
    ) -> None:
        mock_authenticate_user.return_value = _db_user()
        token = await _handler().issue_token(
            PasswordGrant(grant_type="password", email=ADMIN_EMAIL, password="pw")
        )

        replaced = _handler(_config(PLATFORM_ADMIN_EMAIL="new-admin@luml.ai"))

        with pytest.raises(AuthError, match="Not a platform admin"):
            replaced.authenticate(token.access_token)

    def test_expired_token_is_rejected(self) -> None:
        admin_config = _config()
        now = int(time())
        expired = jwt.encode(
            {
                "type": "platform_admin_access",
                "sub": ADMIN_EMAIL,
                "amr": "EMAIL",
                "aud": AUDIENCE,
                "iat": now - 7200,
                "exp": now - 3600,
            },
            admin_config.signing_key,
            algorithm="HS256",
        )

        with pytest.raises(AuthError, match="expired"):
            _handler(admin_config).authenticate(expired)

    @pytest.mark.asyncio
    async def test_password_grant_disabled_by_default(self) -> None:
        handler = _handler(_config(PLATFORM_ADMIN_AUTH_METHODS="GOOGLE"))

        with pytest.raises(AuthError) as error:
            await handler.issue_token(
                PasswordGrant(grant_type="password", email=ADMIN_EMAIL, password="pw")
            )

        assert error.value.status_code == 403

    @patch.object(AuthHandler, "_authenticate_user", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_password_grant_rejects_other_users_without_checking_password(
        self, mock_authenticate_user: AsyncMock
    ) -> None:
        with pytest.raises(AuthError) as error:
            await _handler().issue_token(
                PasswordGrant(
                    grant_type="password", email="someone@luml.ai", password="pw"
                )
            )

        assert error.value.status_code == 401
        mock_authenticate_user.assert_not_awaited()

    @patch.object(AuthHandler, "_authenticate_user", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_password_grant_rejects_disabled_admin(
        self, mock_authenticate_user: AsyncMock
    ) -> None:
        mock_authenticate_user.return_value = _db_user(disabled=True)

        with pytest.raises(AuthError) as error:
            await _handler().issue_token(
                PasswordGrant(grant_type="password", email=ADMIN_EMAIL, password="pw")
            )

        assert error.value.status_code == 403


class TestPlatformAdminGoogleLogin:
    def test_login_url_targets_admin_callback(self) -> None:
        login_url = _handler().google_login_url(PORT, code_challenge_for(CODE_VERIFIER))
        params = _query(login_url)

        assert login_url.startswith(config.GOOGLE_AUTH_URL)
        assert params["redirect_uri"] == REDIRECT_URI
        assert params["hd"] == "luml.ai"
        assert params["prompt"] == "select_account"
        assert params["state"]

    def test_login_disabled_when_google_not_allowed(self) -> None:
        handler = _handler(_config(PLATFORM_ADMIN_AUTH_METHODS="EMAIL"))

        with pytest.raises(AuthError) as error:
            handler.google_login_url(PORT, code_challenge_for(CODE_VERIFIER))

        assert error.value.status_code == 403

    @patch(ADD_TOKEN, new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_login_code_exchanges_for_admin_token(
        self, mock_add_token: AsyncMock
    ) -> None:
        mock_add_token.return_value = True
        handler = _handler()
        login_code = await _google_login_code(handler)

        token = await handler.issue_token(
            GoogleCodeGrant(
                grant_type="google_code", code=login_code, code_verifier=CODE_VERIFIER
            )
        )

        admin = handler.authenticate(token.access_token)
        assert admin.email == ADMIN_EMAIL
        assert admin.auth_method == PlatformAdminAuthMethod.GOOGLE
        mock_add_token.assert_awaited_once()

    @patch(ADD_TOKEN, new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_login_code_is_single_use(self, mock_add_token: AsyncMock) -> None:
        mock_add_token.return_value = False
        handler = _handler()
        login_code = await _google_login_code(handler)

        with pytest.raises(AuthError, match="already been used"):
            await handler.issue_token(
                GoogleCodeGrant(
                    grant_type="google_code",
                    code=login_code,
                    code_verifier=CODE_VERIFIER,
                )
            )

    @patch(ADD_TOKEN, new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_login_code_requires_matching_verifier(
        self, mock_add_token: AsyncMock
    ) -> None:
        handler = _handler()
        login_code = await _google_login_code(handler)

        with pytest.raises(AuthError, match="verifier"):
            await handler.issue_token(
                GoogleCodeGrant(
                    grant_type="google_code", code=login_code, code_verifier="w" * 43
                )
            )

        mock_add_token.assert_not_awaited()

    @pytest.mark.parametrize(
        "userinfo",
        [
            UserInfo(
                email="intruder@luml.ai",
                full_name="Intruder",
                email_verified=True,
                hosted_domain="luml.ai",
            ),
            UserInfo(
                email=ADMIN_EMAIL,
                full_name="Admin",
                email_verified=False,
                hosted_domain="luml.ai",
            ),
            UserInfo(
                email=ADMIN_EMAIL,
                full_name="Admin",
                email_verified=True,
                hosted_domain=None,
            ),
        ],
        ids=["not-admin", "unverified-email", "outside-hosted-domain"],
    )
    @pytest.mark.asyncio
    async def test_callback_denies_non_admin_identities(
        self, userinfo: UserInfo
    ) -> None:
        handler = _handler(userinfo=userinfo)
        login_url = handler.google_login_url(PORT, code_challenge_for(CODE_VERIFIER))

        redirect = await handler.google_callback_redirect(
            "google-code", _query(login_url)["state"], None
        )

        assert _query(redirect) == {"error": "access_denied"}

    @pytest.mark.asyncio
    async def test_callback_forwards_google_errors_to_loopback(self) -> None:
        handler = _handler()
        login_url = handler.google_login_url(PORT, code_challenge_for(CODE_VERIFIER))

        redirect = await handler.google_callback_redirect(
            None, _query(login_url)["state"], "access_denied"
        )

        assert redirect == f"http://127.0.0.1:{PORT}/callback?error=access_denied"

    @pytest.mark.asyncio
    async def test_callback_rejects_forged_state(self) -> None:
        forged = jwt.encode(
            {"type": "platform_admin_oauth_state", "port": PORT, "aud": AUDIENCE},
            "not-the-signing-key",
            algorithm="HS256",
        )

        with pytest.raises(AuthError):
            await _handler().google_callback_redirect("google-code", forged, None)
