import hashlib
import hmac
import logging
import secrets
from time import time
from typing import Any
from uuid import UUID, uuid4

import httpx2
import jwt
from argon2 import (
    PasswordHasher,
    exceptions as argon2_exceptions,
)
from jwt.exceptions import InvalidTokenError
from pydantic import EmailStr
from sqlalchemy.exc import IntegrityError

from luml.clients.oauth_providers import (
    OAuthProvider,
)
from luml.handlers.emails import EmailHandler
from luml.infra.db import engine
from luml.infra.exceptions import (
    AuthError,
    EmailDeliveryError,
    RefreshTokenReusedError,
)
from luml.repositories.base import violates
from luml.repositories.token_blacklist import TokenBlackListRepository
from luml.repositories.users import UserRepository
from luml.schemas.auth import OAuthLogin, Token
from luml.schemas.user import (
    AuthProvider,
    ChangeEmailIn,
    ChangePasswordIn,
    CreateUser,
    CreateUserIn,
    CurrentUserOut,
    EmailChange,
    SignInResponse,
    SignInUser,
    UpdateUser,
    UpdateUserIn,
    User,
)
from luml.settings import config

logger = logging.getLogger(__name__)


class AuthHandler:
    __user_repository = UserRepository(engine)
    __token_black_list_repository = TokenBlackListRepository(engine)
    __emails_handler = EmailHandler()
    _password_hasher: PasswordHasher = PasswordHasher()

    def __init__(
        self,
        secret_key: str,
        oauth_provider: type[OAuthProvider] | None = None,
        algorithm: str = "HS256",
        access_token_expire: int = 10800,  # 3 hours
        refresh_token_expire: int = 604800,  # 7 days
    ) -> None:
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.oauth_provider = oauth_provider
        self.access_token_expire = access_token_expire
        self.refresh_token_expire = refresh_token_expire

    @classmethod
    def _verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        try:
            cls._password_hasher.verify(hashed_password, plain_password)
            return True
        except (
            argon2_exceptions.VerificationError,
            argon2_exceptions.InvalidHash,
        ):
            return False

    @classmethod
    def _get_password_hash(cls, password: str) -> str:
        return cls._password_hasher.hash(password)

    @staticmethod
    def _get_email_confirmation_link(token: str) -> str:
        return config.CONFIRM_EMAIL_URL + token

    @staticmethod
    def _get_password_reset_link(token: str) -> str:
        return config.CHANGE_PASSWORD_URL + token

    def _generate_email_confirmation_token(
        self,
        email: EmailStr,
        user_id: UUID | None = None,
        email_version: UUID | None = None,
    ) -> str:
        return self._create_token(
            data={
                "sub": email,
                "uid": str(user_id),
                "ev": str(email_version),
                "type": "email_confirmation",
            },
            expires_delta=86400,  # 24 hours
        )

    def _generate_password_reset_token(
        self,
        email: EmailStr,
        user_id: UUID | None = None,
        email_version: UUID | None = None,
    ) -> str:
        return self._create_token(
            data={
                "sub": email,
                "uid": str(user_id),
                "ev": str(email_version),
                "type": "password_reset",
                "jti": str(uuid4()),
            },
            expires_delta=3600,  # 1 hour
        )

    def _create_token(self, data: dict[str, Any], expires_delta: int) -> str:
        to_encode = data.copy()
        expire = int(time()) + expires_delta
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def _password_fingerprint(self, hashed_password: str | None) -> str:
        return hmac.new(
            self.secret_key.encode(), (hashed_password or "").encode(), hashlib.sha256
        ).hexdigest()[:32]

    def _create_tokens(
        self,
        user_email: EmailStr,
        hashed_password: str | None = None,
        user_id: UUID | None = None,
        email_version: UUID | None = None,
    ) -> Token:
        fingerprint = self._password_fingerprint(hashed_password)
        access_token = self._create_token(
            data={
                "sub": user_email,
                "uid": str(user_id),
                "ev": str(email_version),
                "type": "access",
                "pwh": fingerprint,
                "jti": str(uuid4()),
            },
            expires_delta=self.access_token_expire,
        )
        refresh_token = self._create_token(
            data={
                "sub": user_email,
                "uid": str(user_id),
                "ev": str(email_version),
                "type": "refresh",
                "pwh": fingerprint,
                "jti": str(uuid4()),
            },
            expires_delta=self.refresh_token_expire,
        )
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

    def _verify_token(self, token: str) -> tuple[EmailStr, str | None, str, str]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get("type") != "access":
                raise AuthError("Invalid token type", 401)
            email: EmailStr | None = payload.get("sub")
            if email is None:
                raise AuthError("Invalid token", 401)
            fingerprint = payload.get("pwh")
            if fingerprint is not None and not isinstance(fingerprint, str):
                raise AuthError("Invalid token", 401)
            user_id = payload.get("uid")
            if not isinstance(user_id, str) or user_id == "None":
                raise AuthError("Invalid token", 401)
            email_version = payload.get("ev")
            if not isinstance(email_version, str) or email_version == "None":
                raise AuthError("Invalid token", 401)
            return email, fingerprint, user_id, email_version
        except InvalidTokenError as err:
            raise AuthError("Invalid token", 401) from err

    async def _authenticate_user(self, email: EmailStr, password: str) -> User:
        user = await self.__user_repository.get_user(email)
        if user is None:
            raise AuthError("Invalid email or password", 400)
        if user.auth_method != AuthProvider.EMAIL:
            raise AuthError("Invalid auth method", 400)
        if user.hashed_password is None:
            raise AuthError("Password is invalid", 400)
        if not self._verify_password(password, user.hashed_password):
            raise AuthError("Invalid email or password", 401)
        if not user.email_verified:
            raise AuthError("Email not verified", 400)
        return user

    async def handle_signup(self, create_user_in: CreateUserIn) -> dict[str, str]:
        existing_user = await self.__user_repository.get_user(create_user_in.email)
        if existing_user:
            if (
                existing_user.email_verified
                or existing_user.auth_method != AuthProvider.EMAIL
                or existing_user.hashed_password is None
                or not self._verify_password(
                    create_user_in.password, existing_user.hashed_password
                )
            ):
                return {"detail": "Please confirm your email address"}
            user = existing_user
        else:
            hashed_password = self._get_password_hash(create_user_in.password)

            create_user = CreateUser(
                email=create_user_in.email,
                full_name=create_user_in.full_name,
                photo=create_user_in.photo,
                hashed_password=hashed_password,
                auth_method=AuthProvider.EMAIL,
            )

            try:
                user = await self.__user_repository.create_user(create_user=create_user)
            except IntegrityError as error:
                if not violates(error, "users_email_key"):
                    raise
                return {"detail": "Please confirm your email address"}

        confirmation_token = self._generate_email_confirmation_token(
            user.email, user.id, user.email_version
        )
        confirmation_link = self._get_email_confirmation_link(confirmation_token)
        try:
            await self.__emails_handler.send_activation_email(
                user.email, confirmation_link, user.full_name
            )
        except Exception as error:
            if existing_user is None:
                await self.__user_repository.delete_signup(user.id)
            raise EmailDeliveryError("Error sending confirmation email.") from error
        return {"detail": "Please confirm your email address"}

    async def handle_signin(self, user: SignInUser) -> SignInResponse:
        db_user = await self._authenticate_user(user.email, user.password)
        tokens = self._create_tokens(
            db_user.email, db_user.hashed_password, db_user.id, db_user.email_version
        )
        return SignInResponse(token=tokens, user_id=db_user.id)

    async def handle_refresh_token(self, refresh_token: str) -> Token:
        try:
            payload = jwt.decode(
                refresh_token, self.secret_key, algorithms=[self.algorithm]
            )

            if payload.get("type") != "refresh":
                raise AuthError("Invalid token type", 400)

            email: EmailStr | None = payload.get("sub")
            if email is None:
                raise AuthError("Invalid token", 400)

            service_user = await self.__user_repository.get_user(email)
            if service_user is None:
                raise AuthError("User not found", 401)

            if payload.get("uid") != str(service_user.id) or payload.get("ev") != str(
                service_user.email_version
            ):
                raise AuthError("Token has been revoked", 401)

            fingerprint = payload.get("pwh")
            if fingerprint is not None and fingerprint != self._password_fingerprint(
                service_user.hashed_password
            ):
                raise AuthError("Token has been revoked", 400)

            exp = int(payload["exp"])

            if not await self.__token_black_list_repository.add_token(
                refresh_token, exp
            ):
                raise RefreshTokenReusedError

            return self._create_tokens(
                service_user.email,
                service_user.hashed_password,
                service_user.id,
                service_user.email_version,
            )

        except InvalidTokenError as err:
            raise AuthError("Invalid refresh token", 400) from err

    async def update_user(
        self,
        email: EmailStr,
        update_user: UpdateUserIn,
        *,
        expected_identity: tuple[UUID, UUID],
    ) -> bool:
        user = await self.__user_repository.get_user(email)
        if user is None:
            raise AuthError("User not found", 404)
        if (user.id, user.email_version) != expected_identity:
            raise AuthError("Token has been revoked", 401)
        update_user = UpdateUser(
            **update_user.model_dump(exclude_unset=True), email=email
        )
        return await self.__user_repository.update_user(
            update_user, expected_identity=expected_identity
        )

    async def handle_change_password(
        self,
        email: EmailStr,
        passwords: ChangePasswordIn,
        *,
        expected_identity: tuple[UUID, UUID],
    ) -> Token:
        user = await self.__user_repository.get_user(email)
        if user is None:
            raise AuthError("User not found", 404)
        if (user.id, user.email_version) != expected_identity:
            raise AuthError("Token has been revoked", 401)
        if user.auth_method != AuthProvider.EMAIL or user.hashed_password is None:
            raise AuthError("Invalid auth method", 400)
        if not self._verify_password(passwords.current_password, user.hashed_password):
            raise AuthError("Invalid current password", 400)

        hashed_password = self._get_password_hash(passwords.new_password)
        if not await self.__user_repository.update_password(
            email, hashed_password, expected_identity=expected_identity
        ):
            raise AuthError("User not found", 404)
        return self._create_tokens(email, hashed_password, user.id, user.email_version)

    async def handle_change_email(
        self,
        email: EmailStr,
        request: ChangeEmailIn,
        *,
        expected_identity: tuple[UUID, UUID],
    ) -> dict[str, str]:
        user = await self.__user_repository.get_user(email)
        if user is None:
            raise AuthError("User not found", 404)
        if (user.id, user.email_version) != expected_identity:
            raise AuthError("Token has been revoked", 401)
        if user.auth_method != AuthProvider.EMAIL or user.hashed_password is None:
            raise AuthError("Email is managed by your sign-in provider", 400)
        if not self._verify_password(request.current_password, user.hashed_password):
            raise AuthError("Invalid current password", 400)
        if user.email.lower() == request.new_email:
            raise AuthError("New email must differ from the current address", 400)
        if not await self.__user_repository.email_exists(request.new_email):
            token = self._generate_email_change_token(user, request.new_email)
            try:
                await self.__emails_handler.send_email_change_confirmation(
                    request.new_email, config.CHANGE_EMAIL_URL + token, user.full_name
                )
            except Exception as error:
                raise EmailDeliveryError() from error
        return {
            "detail": (
                "If this address can be used, we have sent a confirmation link to it"
            )
        }

    def _generate_email_change_token(self, user: User, new_email: EmailStr) -> str:
        return self._create_token(
            {
                "type": "email_change",
                "uid": str(user.id),
                "ev": str(user.email_version),
                "sub": user.email,
                "new_email": new_email,
                "pwh": self._password_fingerprint(user.hashed_password),
                "jti": str(uuid4()),
            },
            86400,
        )

    async def handle_confirm_email_change(self, token: str) -> EmailChange:
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={
                    "require": ["exp", "uid", "ev", "sub", "new_email", "pwh", "jti"]
                },
            )
            if payload.get("type") != "email_change":
                raise ValueError
            user_id = UUID(payload["uid"])
            old_email = payload["sub"]
            new_email = payload["new_email"]
            if not isinstance(old_email, str) or not isinstance(new_email, str):
                raise ValueError
        except (InvalidTokenError, ValueError, TypeError, AttributeError) as error:
            raise AuthError(
                "Email change link is expired, already used or invalid", 400
            ) from error
        user = await self.__user_repository.get_user(old_email)
        if (
            user is None
            or user.id != user_id
            or payload["ev"] != str(user.email_version)
            or user.email != old_email
            or user.auth_method != AuthProvider.EMAIL
            or user.hashed_password is None
            or payload["pwh"] != self._password_fingerprint(user.hashed_password)
            or old_email == new_email
        ):
            raise AuthError(
                "Email change link is expired, already used or invalid", 400
            )
        if not await self.__user_repository.change_email(
            user_id,
            old_email,
            new_email,
            user.hashed_password,
            token,
            int(payload["exp"]),
            user.email_version,
        ):
            raise AuthError(
                "Email change link is expired, already used or invalid", 400
            )
        return EmailChange(
            old_email=old_email, new_email=new_email, full_name=user.full_name
        )

    async def send_email_changed_notice(self, change: EmailChange) -> None:
        local, domain = change.new_email.rsplit("@", 1)
        try:
            await self.__emails_handler.send_email_changed_notice(
                change.old_email, f"{local[0]}***@{domain}", change.full_name
            )
        except Exception:
            logger.exception("Email change notice could not be delivered")

    async def handle_delete_account(
        self, email: EmailStr, *, expected_identity: tuple[UUID, UUID]
    ) -> None:
        await self.__user_repository.delete_user(
            email, expected_identity=expected_identity
        )

    async def handle_get_current_user(
        self,
        email: EmailStr,
        password_fingerprint: str | None = None,
        user_id: str | None = None,
        email_version: str | None = None,
    ) -> CurrentUserOut:
        user = await self.__user_repository.get_current_user(email)
        if user is None:
            raise AuthError("User not found", 404)
        if (
            password_fingerprint is not None
            and password_fingerprint != self._password_fingerprint(user.hashed_password)
        ):
            raise AuthError("Token has been revoked", 401)

        if email_version is not None and str(user.email_version) != email_version:
            raise AuthError("Token has been revoked", 401)

        if user_id is not None and str(user.id) != user_id:
            raise AuthError("Token has been revoked", 401)

        if user.disabled:
            raise AuthError("Account is disabled", 400)

        return user

    async def handle_logout(self, access_token: str | None, refresh_token: str) -> None:
        try:
            payload = jwt.decode(
                refresh_token, self.secret_key, algorithms=[self.algorithm]
            )
            refresh_exp = payload["exp"]

            if access_token:
                try:
                    access_payload = jwt.decode(
                        access_token, self.secret_key, algorithms=[self.algorithm]
                    )
                    await self.__token_black_list_repository.add_token(
                        access_token, access_payload["exp"]
                    )
                except InvalidTokenError:
                    pass

            await self.__token_black_list_repository.add_token(
                refresh_token, refresh_exp
            )

        except InvalidTokenError as err:
            raise AuthError("Invalid refresh token", 400) from err

    def create_oauth_state(self) -> str:
        if not self.oauth_provider:
            raise AuthError("OAuth provider is not configured for this handler", 500)
        provider = self.oauth_provider.PROVIDER_TYPE.lower()
        token = self._create_token(
            data={
                "type": "oauth_state",
                "aud": "luml-user-oauth",
                "iat": int(time()),
                "provider": provider,
                "nonce": secrets.token_urlsafe(32),
            },
            expires_delta=300,
        )
        return f"{provider}.{token}"

    def validate_oauth_state(self, state: str | None, cookie: str | None) -> None:
        if (
            not state
            or not cookie
            or not secrets.compare_digest(state.encode(), cookie.encode())
        ):
            raise AuthError("Invalid or missing OAuth state", 400)
        if not self.oauth_provider:
            raise AuthError("OAuth provider is not configured for this handler", 500)
        provider, _, token = state.partition(".")
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                audience="luml-user-oauth",
                options={"require": ["exp", "iat", "aud", "nonce"]},
            )
        except InvalidTokenError as err:
            raise AuthError("Invalid or expired OAuth state", 400) from err
        if (
            payload.get("type") != "oauth_state"
            or provider != self.oauth_provider.PROVIDER_TYPE.lower()
            or payload.get("provider") != provider
        ):
            raise AuthError("Invalid OAuth state", 400)

    def get_oauth_login_url(self, state: str) -> str:
        if not self.oauth_provider:
            raise AuthError("OAuth provider is not configured for this handler", 500)
        return self.oauth_provider.login_url(state)

    async def handle_oauth(self, code: str | None) -> OAuthLogin:
        if not code:
            raise AuthError("OAuth callback code is missing", 400)

        if not self.oauth_provider:
            raise AuthError("OAuth provider is not configured for this handler", 500)

        async with httpx2.AsyncClient(timeout=10.0) as client:
            oauth_token = await self.oauth_provider.exchange_code_for_token(
                client, code
            )
            userinfo = await self.oauth_provider.get_user_info(client, oauth_token)

        if not userinfo.email:
            raise AuthError("Failed to retrieve user email", 400)

        if userinfo.email_verified is not True:
            raise AuthError("OAuth account email is not verified", 403)

        user = await self.__user_repository.get_user(userinfo.email)

        if user:
            update_user = UpdateUser(email=userinfo.email)

            if user.auth_method != self.oauth_provider.PROVIDER_TYPE:
                update_user.auth_method = self.oauth_provider.PROVIDER_TYPE

            if userinfo.photo_url != user.photo:
                update_user.photo = userinfo.photo_url

            await self.__user_repository.update_user(update_user)

        if not user:
            user = await self.__user_repository.create_user(
                CreateUser(
                    email=userinfo.email,
                    full_name=userinfo.full_name,
                    photo=userinfo.photo_url,
                    email_verified=True,
                    auth_method=self.oauth_provider.PROVIDER_TYPE,
                    hashed_password=None,
                )
            )

        return OAuthLogin(
            token=self._create_tokens(
                user.email, user.hashed_password, user.id, user.email_version
            ),
            user_id=user.id,
        )

    async def send_password_reset_email(self, email: EmailStr) -> None:
        if not (service_user := await self.__user_repository.get_user(email)):
            return
        token = self._generate_password_reset_token(
            service_user.email, service_user.id, service_user.email_version
        )
        link = self._get_password_reset_link(token)
        try:
            await self.__emails_handler.send_password_reset_email(
                email, link, service_user.full_name
            )
        except Exception as error:
            raise EmailDeliveryError() from error

    async def handle_email_confirmation(self, token: str) -> None:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            email: EmailStr | None = payload.get("sub")
        except InvalidTokenError as err:
            raise AuthError("Invalid token", 400) from err
        if payload.get("type") != "email_confirmation":
            raise AuthError("Invalid token type", 400)
        if email is None:
            raise AuthError("Invalid token", 400)

        if (service_user := await self.__user_repository.get_user(email)) is None:
            raise AuthError("User not found", 404)

        if payload.get("uid") != str(service_user.id) or payload.get("ev") != str(
            service_user.email_version
        ):
            raise AuthError("Invalid token", 400)

        if service_user.email_verified:
            return

        await self.__user_repository.update_user(
            UpdateUser(email=email, email_verified=True),
            expected_identity=(service_user.id, service_user.email_version),
        )

    async def handle_reset_password(self, token: str, new_password: str) -> None:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get("type") != "password_reset":
                raise AuthError("Invalid token type", 400)
            email: EmailStr | None = payload.get("sub")
            exp = payload.get("exp")
            if exp is None or exp < time():
                raise AuthError("Token expired", 400)
            if email is None:
                raise AuthError("Invalid token", 400)

            service_user = await self.__user_repository.get_user(email)
            if service_user is None:
                raise AuthError("User not found", 404)
            if payload.get("uid") != str(service_user.id) or payload.get("ev") != str(
                service_user.email_version
            ):
                raise AuthError("Invalid token", 400)

            if not await self.__user_repository.update_password(
                email,
                self._get_password_hash(new_password),
                reset_token=(token, int(exp)),
                expected_identity=(service_user.id, service_user.email_version),
            ):
                raise AuthError("Token has been revoked", 400)
        except InvalidTokenError as err:
            raise AuthError("Invalid token", 400) from err

    async def is_token_blacklisted(self, token: str) -> bool:
        return await self.__token_black_list_repository.is_token_blacklisted(token)
