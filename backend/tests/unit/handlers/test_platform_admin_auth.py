from time import time
from unittest.mock import ANY, Mock
from urllib.parse import parse_qs, urlparse

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

from tests.support.ids import USER_ID
from tests.support.mocks import CollaboratorMocks, mock_collaborators

ADMIN_EMAIL = "admin@luml.ai"
REDIRECT_URI = "https://api.example.com/v1/platform-admin/auth/google/callback"
CODE_VERIFIER = "v" * 43
PORT = 53682


def _config(**overrides: object) -> PlatformAdminConfig:
    settings: dict[str, object] = {
        "PLATFORM_ADMIN_EMAIL": ADMIN_EMAIL,
        "PLATFORM_ADMIN_AUTH_METHODS": "GOOGLE,EMAIL",
        "PLATFORM_ADMIN_GOOGLE_REDIRECT_URI": REDIRECT_URI,
        "PLATFORM_ADMIN_GOOGLE_HOSTED_DOMAIN": "luml.ai",
    }
    settings.update(overrides)
    return PlatformAdminConfig.from_settings(config.model_copy(update=settings))


@pytest.fixture
def mocks() -> CollaboratorMocks[PlatformAdminAuthHandler]:
    auth_handler = Mock(spec=AuthHandler)
    google_provider = Mock(spec=OAuthGoogleProvider)
    google_provider.exchange_code_for_token.return_value = "google-access-token"
    google_provider.get_user_info.return_value = UserInfo(
        email="Admin@luml.ai",
        full_name="Admin",
        email_verified=True,
        hosted_domain="luml.ai",
    )
    mocks = mock_collaborators(
        PlatformAdminAuthHandler(_config(), auth_handler, google_provider)
    )
    mocks.auth_handler = auth_handler
    mocks.google_provider = google_provider
    return mocks


def _db_user(disabled: bool = False) -> User:
    return User(
        id=USER_ID,
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


class TestPlatformAdminAuthHandler:
    def test_config_is_disabled_when_admin_email_missing(self) -> None:
        admin_config = _config(
            PLATFORM_ADMIN_EMAIL=None, PLATFORM_ADMIN_GOOGLE_REDIRECT_URI=None
        )

        assert not admin_config.enabled

    def test_config_defaults_to_google_only_when_methods_unset(self) -> None:
        admin_config = PlatformAdminConfig.from_settings(
            config.model_copy(
                update={
                    "PLATFORM_ADMIN_EMAIL": ADMIN_EMAIL,
                    "PLATFORM_ADMIN_GOOGLE_REDIRECT_URI": REDIRECT_URI,
                }
            )
        )

        assert admin_config.auth_methods == {PlatformAdminAuthMethod.GOOGLE}

    def test_config_normalizes_admin_email_and_methods(self) -> None:
        admin_config = _config(
            PLATFORM_ADMIN_EMAIL="  Admin@LUML.ai ",
            PLATFORM_ADMIN_AUTH_METHODS=" email , google ",
        )

        assert admin_config.admin_email == ADMIN_EMAIL
        assert admin_config.auth_methods == set(PlatformAdminAuthMethod)

    def test_config_raises_config_error_when_google_enabled_without_redirect_uri(
        self,
    ) -> None:
        with pytest.raises(PlatformAdminConfigError, match="REDIRECT_URI"):
            _config(PLATFORM_ADMIN_GOOGLE_REDIRECT_URI=None)

    def test_config_accepts_email_only_without_redirect_uri(self) -> None:
        admin_config = _config(
            PLATFORM_ADMIN_AUTH_METHODS="EMAIL", PLATFORM_ADMIN_GOOGLE_REDIRECT_URI=None
        )

        assert admin_config.auth_methods == {PlatformAdminAuthMethod.EMAIL}

    @pytest.mark.parametrize("methods", ["MICROSOFT", "GOOGLE,SAML", " , "])
    def test_config_raises_config_error_when_methods_unknown_or_empty(
        self, methods: str
    ) -> None:
        with pytest.raises(PlatformAdminConfigError):
            _config(PLATFORM_ADMIN_AUTH_METHODS=methods)

    def test_config_derives_signing_key_different_from_user_secret(self) -> None:
        assert _config().signing_key != config.AUTH_SECRET_KEY

    async def test_tokens_password_grant_issues_verifiable_token(
        self, mocks: CollaboratorMocks[PlatformAdminAuthHandler]
    ) -> None:
        mocks.auth_handler._authenticate_user.return_value = _db_user()

        token = await mocks.handler.issue_token(
            PasswordGrant(grant_type="password", email="ADMIN@luml.ai", password="pw")
        )
        admin = mocks.handler.authenticate(token.access_token)

        assert admin.email == ADMIN_EMAIL
        assert admin.auth_method == PlatformAdminAuthMethod.EMAIL
        assert token.expires_in == 3600
        mocks.auth_handler._authenticate_user.assert_awaited_once_with(
            ADMIN_EMAIL, "pw"
        )

    def test_tokens_authenticate_rejects_user_access_token(
        self, mocks: CollaboratorMocks[PlatformAdminAuthHandler]
    ) -> None:
        user_tokens = AuthHandler(secret_key=config.AUTH_SECRET_KEY)._create_tokens(
            ADMIN_EMAIL
        )

        with pytest.raises(AuthError):
            mocks.handler.authenticate(user_tokens.access_token)

    async def test_tokens_user_token_verification_rejects_admin_token(
        self, mocks: CollaboratorMocks[PlatformAdminAuthHandler]
    ) -> None:
        mocks.auth_handler._authenticate_user.return_value = _db_user()
        token = await mocks.handler.issue_token(
            PasswordGrant(grant_type="password", email=ADMIN_EMAIL, password="pw")
        )

        with pytest.raises(AuthError):
            AuthHandler(secret_key=config.AUTH_SECRET_KEY)._verify_token(
                token.access_token
            )

    async def test_tokens_authenticate_rejects_token_when_admin_email_changes(
        self, mocks: CollaboratorMocks[PlatformAdminAuthHandler]
    ) -> None:
        mocks.auth_handler._authenticate_user.return_value = _db_user()
        token = await mocks.handler.issue_token(
            PasswordGrant(grant_type="password", email=ADMIN_EMAIL, password="pw")
        )

        mocks.handler.config = _config(PLATFORM_ADMIN_EMAIL="new-admin@luml.ai")

        with pytest.raises(AuthError, match="Not a platform admin"):
            mocks.handler.authenticate(token.access_token)

    def test_tokens_authenticate_rejects_expired_token(
        self, mocks: CollaboratorMocks[PlatformAdminAuthHandler]
    ) -> None:
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
            mocks.handler.config.signing_key,
            algorithm="HS256",
        )

        with pytest.raises(AuthError, match="expired"):
            mocks.handler.authenticate(expired)

    async def test_tokens_password_grant_raises_forbidden_when_email_method_disabled(
        self, mocks: CollaboratorMocks[PlatformAdminAuthHandler]
    ) -> None:
        mocks.handler.config = _config(PLATFORM_ADMIN_AUTH_METHODS="GOOGLE")

        with pytest.raises(AuthError) as error:
            await mocks.handler.issue_token(
                PasswordGrant(grant_type="password", email=ADMIN_EMAIL, password="pw")
            )

        assert error.value.status_code == 403

    async def test_tokens_password_grant_rejects_other_user_without_checking_password(
        self, mocks: CollaboratorMocks[PlatformAdminAuthHandler]
    ) -> None:
        with pytest.raises(AuthError) as error:
            await mocks.handler.issue_token(
                PasswordGrant(
                    grant_type="password", email="someone@luml.ai", password="pw"
                )
            )

        assert error.value.status_code == 401
        mocks.auth_handler._authenticate_user.assert_not_awaited()

    async def test_tokens_password_grant_raises_forbidden_when_admin_disabled(
        self, mocks: CollaboratorMocks[PlatformAdminAuthHandler]
    ) -> None:
        mocks.auth_handler._authenticate_user.return_value = _db_user(disabled=True)

        with pytest.raises(AuthError) as error:
            await mocks.handler.issue_token(
                PasswordGrant(grant_type="password", email=ADMIN_EMAIL, password="pw")
            )

        assert error.value.status_code == 403

    def test_google_login_url_targets_admin_callback(
        self, mocks: CollaboratorMocks[PlatformAdminAuthHandler]
    ) -> None:
        login_url = mocks.handler.google_login_url(
            PORT, code_challenge_for(CODE_VERIFIER)
        )
        params = _query(login_url)

        assert login_url.startswith(config.GOOGLE_AUTH_URL)
        assert params["redirect_uri"] == REDIRECT_URI
        assert params["hd"] == "luml.ai"
        assert params["prompt"] == "select_account"
        assert params["state"]

    def test_google_login_url_raises_forbidden_when_google_disabled(
        self, mocks: CollaboratorMocks[PlatformAdminAuthHandler]
    ) -> None:
        mocks.handler.config = _config(PLATFORM_ADMIN_AUTH_METHODS="EMAIL")

        with pytest.raises(AuthError) as error:
            mocks.handler.google_login_url(PORT, code_challenge_for(CODE_VERIFIER))

        assert error.value.status_code == 403

    async def test_google_login_code_exchanges_for_admin_token(
        self, mocks: CollaboratorMocks[PlatformAdminAuthHandler]
    ) -> None:
        mocks.token_black_list_repository.add_token.return_value = True
        login_code = await _google_login_code(mocks.handler)

        token = await mocks.handler.issue_token(
            GoogleCodeGrant(
                grant_type="google_code", code=login_code, code_verifier=CODE_VERIFIER
            )
        )

        admin = mocks.handler.authenticate(token.access_token)
        assert admin.email == ADMIN_EMAIL
        assert admin.auth_method == PlatformAdminAuthMethod.GOOGLE
        mocks.token_black_list_repository.add_token.assert_awaited_once()
        mocks.google_provider.exchange_code_for_token.assert_awaited_once_with(
            ANY, "google-code", redirect_uri=REDIRECT_URI
        )

    async def test_google_login_code_raises_when_already_used(
        self, mocks: CollaboratorMocks[PlatformAdminAuthHandler]
    ) -> None:
        mocks.token_black_list_repository.add_token.return_value = False
        login_code = await _google_login_code(mocks.handler)

        with pytest.raises(AuthError, match="already been used"):
            await mocks.handler.issue_token(
                GoogleCodeGrant(
                    grant_type="google_code",
                    code=login_code,
                    code_verifier=CODE_VERIFIER,
                )
            )

    async def test_google_login_code_raises_when_verifier_mismatches(
        self, mocks: CollaboratorMocks[PlatformAdminAuthHandler]
    ) -> None:
        login_code = await _google_login_code(mocks.handler)

        with pytest.raises(AuthError, match="verifier"):
            await mocks.handler.issue_token(
                GoogleCodeGrant(
                    grant_type="google_code", code=login_code, code_verifier="w" * 43
                )
            )

        mocks.token_black_list_repository.add_token.assert_not_awaited()

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
    async def test_google_callback_redirects_access_denied_when_identity_not_admin(
        self,
        mocks: CollaboratorMocks[PlatformAdminAuthHandler],
        userinfo: UserInfo,
    ) -> None:
        mocks.google_provider.get_user_info.return_value = userinfo
        login_url = mocks.handler.google_login_url(
            PORT, code_challenge_for(CODE_VERIFIER)
        )

        redirect = await mocks.handler.google_callback_redirect(
            "google-code", _query(login_url)["state"], None
        )

        assert _query(redirect) == {"error": "access_denied"}

    async def test_google_callback_forwards_google_error_to_loopback(
        self, mocks: CollaboratorMocks[PlatformAdminAuthHandler]
    ) -> None:
        login_url = mocks.handler.google_login_url(
            PORT, code_challenge_for(CODE_VERIFIER)
        )

        redirect = await mocks.handler.google_callback_redirect(
            None, _query(login_url)["state"], "access_denied"
        )

        assert redirect == f"http://127.0.0.1:{PORT}/callback?error=access_denied"

    async def test_google_callback_raises_when_state_forged(
        self, mocks: CollaboratorMocks[PlatformAdminAuthHandler]
    ) -> None:
        forged = jwt.encode(
            {"type": "platform_admin_oauth_state", "port": PORT, "aud": AUDIENCE},
            "not-the-signing-key",
            algorithm="HS256",
        )

        with pytest.raises(AuthError):
            await mocks.handler.google_callback_redirect("google-code", forged, None)
