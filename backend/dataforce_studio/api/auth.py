from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import APIRouter, Body, Depends, Request
from passlib.context import CryptContext
from pydantic import EmailStr
from starlette.responses import RedirectResponse

from dataforce_studio.handlers.auth import AuthHandler
from dataforce_studio.infra.dependencies import UserAuthentication
from dataforce_studio.schemas.auth import Token
from dataforce_studio.schemas.user import (
    CreateUserIn,
    SignInResponse,
    SignInUser,
    UpdateUserIn,
    UserOut,
)
from dataforce_studio.settings import config

is_user_authenticated = UserAuthentication(["jwt"])

auth_router = APIRouter(prefix="/auth", tags=["auth"])

auth_handler = AuthHandler(
    secret_key=config.AUTH_SECRET_KEY,
    pwd_context=CryptContext(schemes=["bcrypt"], deprecated="auto"),
)


@auth_router.post("/signup", response_model=dict)
async def signup(create_user: CreateUserIn) -> dict[str, str]:
    return await auth_handler.handle_signup(create_user)


@auth_router.post("/signin", response_model=SignInResponse)
async def signin(user: SignInUser) -> SignInResponse:
    return await auth_handler.handle_signin(user)


@auth_router.get("/google/login")
async def google_login() -> RedirectResponse:
    params = {
        "client_id": config.GOOGLE_CLIENT_ID,
        "redirect_uri": config.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return RedirectResponse(url)


@auth_router.get("/google/callback")
async def google_callback(code: str | None = None) -> dict[str, Any]:
    return await auth_handler.handle_google_auth(code)


@auth_router.post("/refresh", response_model=Token)
async def refresh(refresh_token: Annotated[str, Body()]) -> Token:
    return await auth_handler.handle_refresh_token(refresh_token)


@auth_router.post("/forgot-password")
async def forgot_password(email: Annotated[EmailStr, Body()]) -> dict[str, str]:
    await auth_handler.send_password_reset_email(email)
    return {"detail": "Password reset email has been sent"}


@auth_router.get("/users/me", response_model=UserOut)
async def get_current_user_info(
    request: Request,
    _: Annotated[None, Depends(is_user_authenticated)],
) -> UserOut:
    return await auth_handler.handle_get_current_user(request.user.email)


@auth_router.delete("/users/me")
async def delete_account(
    request: Request,
) -> dict[str, str]:
    await auth_handler.handle_delete_account(request.user.email)
    return {"detail": "Account deleted successfully"}


@auth_router.patch("/users/me")
async def update_user_profile(
    request: Request,
    update_user: UpdateUserIn,
    _: Annotated[None, Depends(is_user_authenticated)],
) -> dict[str, str]:
    return {
        "detail": "User profile updated successfully"
        if (await auth_handler.update_user(request.user.email, update_user))
        else "No changes made to the user profile"
    }


@auth_router.post("/logout")
async def logout(
    request: Request,
    refresh_token: Annotated[str, Body()],
) -> dict[str, str]:
    auth_header = request.headers.get("Authorization")
    access_token = auth_header.split()[1] if auth_header else None
    await auth_handler.handle_logout(access_token, refresh_token)
    return {"detail": "Successfully logged out"}


@auth_router.get("/confirm-email")
async def confirm_email(
    confirmation_token: str,
) -> RedirectResponse:
    await auth_handler.handle_email_confirmation(confirmation_token)
    return RedirectResponse(config.CONFIRM_EMAIL_REDIRECT_URL)


@auth_router.post("/reset-password")
async def reset_password(
    reset_token: Annotated[str, Body()],
    new_password: Annotated[str, Body(min_length=8)],
) -> dict[str, str]:
    await auth_handler.handle_reset_password(reset_token, new_password)
    return {"detail": "Password reset successfully"}
