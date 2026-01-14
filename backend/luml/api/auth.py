from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from pydantic import EmailStr
from starlette.responses import RedirectResponse

from luml.clients.oauth_providers import (
    OAuthGoogleProvider,
    OAuthMicrosoftProvider,
)
from luml.handlers.auth import AuthHandler
from luml.infra.dependencies import UserAuthentication
from luml.schemas.auth import Token
from luml.schemas.user import (
    CreateUserIn,
    DetailResponse,
    SignInAPIResponse,
    SignInUser,
    UpdateUserIn,
    UserOut,
)
from luml.settings import config

is_user_authenticated = UserAuthentication(["jwt"])

auth_router = APIRouter(prefix="/auth", tags=["auth"])

auth_handler = AuthHandler(secret_key=config.AUTH_SECRET_KEY)
google_auth_handler = AuthHandler(
    secret_key=config.AUTH_SECRET_KEY, oauth_provider=OAuthGoogleProvider
)
microsoft_auth_handler = AuthHandler(
    secret_key=config.AUTH_SECRET_KEY, oauth_provider=OAuthMicrosoftProvider
)


def set_auth_cookies(response: Response, data: Token) -> None:
    response.set_cookie(
        key="access_token",
        value=data.access_token,
        httponly=True,
        secure=True,
        samesite=config.AUTH_COOKIE_SAMESITE,
        path="/",
        max_age=auth_handler.access_token_expire,
    )

    if data.refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=data.refresh_token,
            httponly=True,
            secure=True,
            samesite=config.AUTH_COOKIE_SAMESITE,
            path="/",
            max_age=auth_handler.refresh_token_expire,
        )


@auth_router.post("/signup", response_model=DetailResponse)
async def signup(create_user: CreateUserIn) -> dict[str, str]:
    return await auth_handler.handle_signup(create_user)


@auth_router.post("/signin", response_model=SignInAPIResponse)
async def signin(user: SignInUser, response: Response) -> SignInAPIResponse:
    signin_response = await auth_handler.handle_signin(user)
    set_auth_cookies(response, signin_response.token)
    return SignInAPIResponse(
        detail="Successfully signed in", user_id=signin_response.user_id
    )


@auth_router.get("/google/login")
async def google_login() -> RedirectResponse:
    return RedirectResponse(google_auth_handler.get_oauth_login_url())


@auth_router.get("/google/callback", response_model=SignInAPIResponse)
async def google_callback(code: str | None, response: Response) -> SignInAPIResponse:
    signin_response = await google_auth_handler.handle_oauth(code)
    set_auth_cookies(response, signin_response.token)
    return SignInAPIResponse(
        detail="Successfully authenticated with Google", user_id=signin_response.user_id
    )


@auth_router.post("/refresh", response_model=DetailResponse)
async def refresh(request: Request, response: Response) -> dict[str, str]:
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token not found")

    tokens = await auth_handler.handle_refresh_token(refresh_token)
    set_auth_cookies(response, tokens)
    return {"detail": "Tokens refreshed successfully"}


@auth_router.post("/forgot-password", response_model=DetailResponse)
async def forgot_password(email: Annotated[EmailStr, Body()]) -> dict[str, str]:
    await auth_handler.send_password_reset_email(email)
    return {"detail": "Password reset email has been sent"}


@auth_router.get("/users/me", response_model=UserOut)
async def get_current_user_info(
    request: Request,
    _: Annotated[None, Depends(is_user_authenticated)],
) -> UserOut:
    return await auth_handler.handle_get_current_user(request.user.email)


@auth_router.delete("/users/me", response_model=DetailResponse)
async def delete_account(
    request: Request,
    _: Annotated[None, Depends(is_user_authenticated)],
) -> dict[str, str]:
    await auth_handler.handle_delete_account(request.user.email)
    return {"detail": "Account deleted successfully"}


@auth_router.patch("/users/me", response_model=DetailResponse)
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


@auth_router.post("/logout", response_model=DetailResponse)
async def logout(request: Request, response: Response) -> dict[str, str]:
    access_token = request.cookies.get("access_token")
    refresh_token = request.cookies.get("refresh_token")
    samesite = config.AUTH_COOKIE_SAMESITE

    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token not found")

    await auth_handler.handle_logout(access_token, refresh_token)

    response.delete_cookie(
        key="access_token", httponly=True, secure=True, samesite=samesite, path="/"
    )
    response.delete_cookie(
        key="refresh_token", httponly=True, secure=True, samesite=samesite, path="/"
    )

    return {"detail": "Successfully logged out"}


@auth_router.get("/confirm-email")
async def confirm_email(
    confirmation_token: str,
) -> RedirectResponse:
    await auth_handler.handle_email_confirmation(confirmation_token)
    return RedirectResponse(config.CONFIRM_EMAIL_REDIRECT_URL)


@auth_router.post("/reset-password", response_model=DetailResponse)
async def reset_password(
    reset_token: Annotated[str, Body()],
    new_password: Annotated[str, Body(min_length=8, max_length=36)],
) -> dict[str, str]:
    await auth_handler.handle_reset_password(reset_token, new_password)
    return {"detail": "Password reset successfully"}


@auth_router.get("/microsoft/login")
async def microsoft_login() -> RedirectResponse:
    return RedirectResponse(microsoft_auth_handler.get_oauth_login_url())


@auth_router.get("/microsoft/callback")
async def microsoft_callback(code: str | None, response: Response) -> SignInAPIResponse:
    signin_response = await microsoft_auth_handler.handle_oauth(code)
    set_auth_cookies(response, signin_response.token)

    return SignInAPIResponse(
        detail="Successfully authenticated with Microsoft",
        user_id=signin_response.user_id,
    )
