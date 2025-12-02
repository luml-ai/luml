from time import time
from typing import Any

import httpx
import jwt
from argon2 import (
    PasswordHasher,
    exceptions as argon2_exceptions,
)
from jwt.exceptions import InvalidTokenError
from pydantic import EmailStr

from dataforce_studio.handlers.emails import EmailHandler
from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import (
    AuthError,
    EmailDeliveryError,
)
from dataforce_studio.repositories.token_blacklist import TokenBlackListRepository
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.auth import OAuthLogin, Token
from dataforce_studio.schemas.user import (
    AuthProvider,
    CreateUser,
    CreateUserIn,
    SignInResponse,
    SignInUser,
    UpdateUser,
    UpdateUserIn,
    User,
    UserOut,
)
from dataforce_studio.services.oauth_providers import (
    OAuthProvider,
)
from dataforce_studio.settings import config


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

    def _generate_email_confirmation_token(self, email: EmailStr) -> str:
        return self._create_token(
            data={"sub": email, "type": "email_confirmation"},
            expires_delta=86400,  # 24 hours
        )

    def _generate_password_reset_token(self, email: EmailStr) -> str:
        return self._create_token(
            data={"sub": email, "type": "password_reset"},
            expires_delta=3600,  # 1 hour
        )

    def _create_token(self, data: dict[str, Any], expires_delta: int) -> str:
        to_encode = data.copy()
        expire = int(time()) + expires_delta
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def _create_tokens(self, user_email: EmailStr) -> Token:
        access_token = self._create_token(
            data={"sub": user_email},
            expires_delta=self.access_token_expire,
        )
        refresh_token = self._create_token(
            data={"sub": user_email, "type": "refresh"},
            expires_delta=self.refresh_token_expire,
        )
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

    def _verify_token(self, token: str) -> EmailStr:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            email: EmailStr = payload.get("sub")
            if email is None:
                raise AuthError("Invalid token", 401)
            return email
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
            raise AuthError("Invalid email or password", 400)
        if not user.email_verified:
            raise AuthError("Email not verified", 400)
        return user

    async def handle_signup(self, create_user_in: CreateUserIn) -> dict[str, str]:
        if await self.__user_repository.get_user(create_user_in.email):
            raise AuthError("Email already registered", 400)

        hashed_password = self._get_password_hash(create_user_in.password)

        create_user = CreateUser(
            email=create_user_in.email,
            full_name=create_user_in.full_name,
            photo=create_user_in.photo,
            hashed_password=hashed_password,
            auth_method=AuthProvider.EMAIL,
        )

        user = await self.__user_repository.create_user(create_user=create_user)

        confirmation_token = self._generate_email_confirmation_token(user.email)
        confirmation_link = self._get_email_confirmation_link(confirmation_token)
        try:
            self.__emails_handler.send_activation_email(
                user.email, confirmation_link, user.full_name
            )
        except Exception as error:
            await self.__user_repository.delete_user(user.email)
            raise EmailDeliveryError(
                "Error sending confirmation email. User is not created."
            ) from error
        return {"detail": "Please confirm your email address"}

    async def handle_signin(self, user: SignInUser) -> SignInResponse:
        db_user = await self._authenticate_user(user.email, user.password)
        tokens = self._create_tokens(user.email)
        return SignInResponse(token=tokens, user_id=db_user.id)

    async def handle_refresh_token(self, refresh_token: str) -> Token:
        try:
            payload = jwt.decode(
                refresh_token, self.secret_key, algorithms=[self.algorithm]
            )

            if payload.get("type") != "refresh":
                raise AuthError("Invalid token type", 400)

            email: EmailStr = payload.get("sub")
            if email is None:
                raise AuthError("Invalid token", 400)

            if await self.__token_black_list_repository.is_token_blacklisted(
                refresh_token
            ):
                raise AuthError("Token has been revoked", 400)

            service_user = await self.__user_repository.get_user(email)
            if service_user is None:
                raise AuthError("User not found", 404)

            exp = int(payload.get("exp"))

            await self.__token_black_list_repository.add_token(refresh_token, exp)

            return self._create_tokens(service_user.email)

        except InvalidTokenError as err:
            raise AuthError("Invalid refresh token", 400) from err

    async def update_user(
        self,
        email: EmailStr,
        update_user: UpdateUserIn,
    ) -> bool:
        if not await self.__user_repository.get_user(email):
            raise AuthError("User not found", 404)
        hashed_password = (
            self._get_password_hash(update_user.password)
            if update_user.password
            else None
        )
        update_user = UpdateUser(
            **update_user.model_dump(exclude_unset=True), email=email
        )
        if hashed_password:
            update_user.hashed_password = hashed_password
        return await self.__user_repository.update_user(update_user)

    async def handle_delete_account(self, email: EmailStr) -> None:
        await self.__user_repository.delete_user(email)

    async def handle_get_current_user(self, email: EmailStr) -> UserOut:
        user = await self.__user_repository.get_public_user(email)
        if user is None:
            raise AuthError("User not found", 404)

        if user.disabled:
            raise AuthError("Account is disabled", 400)

        return user

    async def handle_logout(self, access_token: str | None, refresh_token: str) -> None:
        try:
            payload = jwt.decode(
                refresh_token, self.secret_key, algorithms=[self.algorithm]
            )
            exp = payload.get("exp")

            if access_token:
                try:
                    access_payload = jwt.decode(
                        access_token, self.secret_key, algorithms=[self.algorithm]
                    )
                    exp = access_payload.get("exp")
                    await self.__token_black_list_repository.add_token(
                        access_token, exp
                    )
                except InvalidTokenError:
                    pass

            await self.__token_black_list_repository.add_token(refresh_token, exp)

        except InvalidTokenError as err:
            raise AuthError("Invalid refresh token", 400) from err

    def get_oauth_login_url(self) -> str:
        if not self.oauth_provider:
            raise AuthError("OAuth provider is not configured for this handler", 500)
        return self.oauth_provider.login_url()

    async def handle_oauth(self, code: str | None) -> OAuthLogin:
        if not code:
            raise AuthError("OAuth callback code is missing", 400)

        if not self.oauth_provider:
            raise AuthError("OAuth provider is not configured for this handler", 500)

        async with httpx.AsyncClient(timeout=10.0) as client:
            access_token = await self.oauth_provider.exchange_code_for_token(
                client, code
            )
            userinfo = await self.oauth_provider.get_user_info(client, access_token)

        if not userinfo.email:
            raise AuthError("Failed to retrieve user email", 400)

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

        return OAuthLogin(token=self._create_tokens(user.email), user_id=user.id)

    async def send_password_reset_email(self, email: EmailStr) -> None:
        if not (service_user := await self.__user_repository.get_user(email)):
            return
        token = self._generate_password_reset_token(service_user.email)
        link = self._get_password_reset_link(token)
        try:
            self.__emails_handler.send_password_reset_email(
                email, link, service_user.full_name
            )
        except Exception as error:
            raise EmailDeliveryError() from error

    async def handle_email_confirmation(self, token: str) -> None:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            email: EmailStr = payload.get("sub")
        except InvalidTokenError as err:
            raise AuthError("Invalid token", 400) from err
        if email is None:
            raise AuthError("Invalid token", 400)

        if (service_user := await self.__user_repository.get_user(email)) is None:
            raise AuthError("User not found", 404)

        if service_user.email_verified:
            raise AuthError("Email already verified", 400)

        await self.__user_repository.update_user(
            UpdateUser(email=email, email_verified=True)
        )

    async def handle_reset_password(self, token: str, new_password: str) -> None:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            email: EmailStr = payload.get("sub")
            exp = payload.get("exp")
            if exp is None or exp < time():
                raise AuthError("Token expired", 400)
            if email is None:
                raise AuthError("Invalid token", 400)

            if (await self.__user_repository.get_user(email)) is None:
                raise AuthError("User not found", 404)

            await self.__user_repository.update_user(
                UpdateUser(
                    email=email, hashed_password=self._get_password_hash(new_password)
                )
            )
        except InvalidTokenError as err:
            raise AuthError("Invalid token", 400) from err

    async def is_token_blacklisted(self, token: str) -> bool:
        return await self.__token_black_list_repository.is_token_blacklisted(token)
