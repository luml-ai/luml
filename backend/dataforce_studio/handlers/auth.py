from time import time
from typing import Any

import httpx
import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from pydantic import EmailStr

from dataforce_studio.handlers.emails import EmailHandler
from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import AuthError, EmailDeliveryError
from dataforce_studio.repositories.token_blacklist import TokenBlackListRepository
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.auth import Token
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
from dataforce_studio.settings import config


class AuthHandler:
    __user_repository = UserRepository(engine)
    __token_black_list_repository = TokenBlackListRepository(engine)
    __emails_handler = EmailHandler()

    def __init__(
        self,
        secret_key: str,
        pwd_context: CryptContext,
        algorithm: str = "HS256",
        access_token_expire: int = 10800,  # 3 hours
        refresh_token_expire: int = 604800,  # 7 days
    ) -> None:
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire = access_token_expire
        self.refresh_token_expire = refresh_token_expire
        self.pwd_context = pwd_context

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self.pwd_context.verify(plain_password, hashed_password)

    def _get_password_hash(self, password: str) -> str:
        return self.pwd_context.hash(password)

    async def _authenticate_user(self, email: EmailStr, password: str) -> User:
        user = await self.__user_repository.get_user(email)
        if user is None:
            raise AuthError("Invalid email or password", 400)
        if user.auth_method != AuthProvider.EMAIL:
            raise AuthError("Invalid auth method", 400)
        if user.hashed_password is None:
            raise AuthError("Password is invalid", 400)
        if not user or not self._verify_password(password, user.hashed_password):
            raise AuthError("Invalid email or password", 400)
        if not user.email_verified:
            raise AuthError("Email not verified", 400)
        return user

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

    def _get_email_confirmation_link(self, token: str) -> str:
        return config.CONFIRM_EMAIL_URL + token

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

    async def handle_google_auth(self, code: str | None) -> dict[str, Any]:
        if not code:
            raise AuthError("Google callback code is missing")
        data = {
            "code": code,
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "redirect_uri": config.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token", data=data
            )
            if token_response.status_code != 200:
                raise AuthError("Failed to retrieve token from Google", 400)

            token_data = token_response.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise AuthError("Failed to retrieve access token", 400)

            userinfo_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if userinfo_response.status_code != 200:
                raise AuthError("Failed to retrieve user info from Google", 400)

        userinfo = userinfo_response.json()
        email = userinfo.get("email")
        full_name = userinfo.get("name")
        photo_url = userinfo.get("picture")

        if not email:
            raise AuthError("Failed to retrieve user email", 400)

        user = await self.__user_repository.get_user(email)
        if user and user.auth_method != AuthProvider.GOOGLE:
            await self.__user_repository.update_user(
                UpdateUser(email=email, auth_method=AuthProvider.GOOGLE)
            )
        if not user:
            user = await self.__user_repository.create_user(
                CreateUser(
                    email=email,
                    full_name=full_name,
                    photo=photo_url,
                    email_verified=True,
                    auth_method=AuthProvider.GOOGLE,
                    hashed_password=None,
                )
            )

        if user and photo_url != user.photo:
            await self.__user_repository.update_user(
                UpdateUser(email=email, photo=photo_url)
            )

        return {"token": self._create_tokens(user.email), "user_id": user.id}

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

    def _get_password_reset_link(self, token: str) -> str:
        return config.CHANGE_PASSWORD_URL + token

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
