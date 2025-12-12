from abc import ABC, abstractmethod
from urllib.parse import urlencode

import httpx

from luml.infra.exceptions import AuthError
from luml.schemas.auth import UserInfo
from luml.schemas.user import AuthProvider
from luml.settings import config


class OAuthProvider(ABC):
    PROVIDER_TYPE: AuthProvider

    @staticmethod
    @abstractmethod
    def login_url() -> str:
        pass

    @staticmethod
    @abstractmethod
    async def exchange_code_for_token(client: httpx.AsyncClient, code: str) -> str:
        pass

    @staticmethod
    @abstractmethod
    async def get_user_info(client: httpx.AsyncClient, access_token: str) -> UserInfo:
        pass


class OAuthGoogleProvider(OAuthProvider):
    PROVIDER_TYPE = AuthProvider.GOOGLE

    @staticmethod
    def login_url() -> str:
        params = {
            "client_id": config.GOOGLE_CLIENT_ID,
            "redirect_uri": config.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent",
            "state": "google",
        }
        return config.GOOGLE_AUTH_URL + "?" + urlencode(params)

    @staticmethod
    async def exchange_code_for_token(client: httpx.AsyncClient, code: str) -> str:
        data = {
            "code": code,
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "redirect_uri": config.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }

        try:
            response = await client.post(config.GOOGLE_TOKEN_URL, data=data)
            response.raise_for_status()
        except Exception as err:
            raise AuthError(f"Failed to get access token: {err}", 503) from err

        token_data = response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            raise AuthError("Failed to retrieve access token.", 400)

        return str(access_token)

    @staticmethod
    async def get_user_info(client: httpx.AsyncClient, access_token: str) -> UserInfo:
        try:
            response = await client.get(
                config.GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
        except Exception as err:
            raise AuthError(f"Failed to get user info: {err}", 503) from err

        result = response.json()

        return UserInfo(
            email=result.get("email"),
            full_name=result.get("name"),
            photo_url=result.get("picture"),
        )


class OAuthMicrosoftProvider(OAuthProvider):
    PROVIDER_TYPE = AuthProvider.MICROSOFT

    @staticmethod
    def login_url() -> str:
        auth_url = (
            f"{config.MICROSOFT_AUTH_URL}/{config.MICROSOFT_TENANT}"
            f"/oauth2/v2.0/authorize"
        )
        params = {
            "client_id": config.MICROSOFT_CLIENT_ID,
            "redirect_uri": config.MICROSOFT_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile User.Read",
            "state": "microsoft",
        }
        return auth_url + "?" + urlencode(params)

    @staticmethod
    async def exchange_code_for_token(client: httpx.AsyncClient, code: str) -> str:
        data = {
            "code": code,
            "client_id": config.MICROSOFT_CLIENT_ID,
            "client_secret": config.MICROSOFT_CLIENT_SECRET,
            "redirect_uri": config.MICROSOFT_REDIRECT_URI,
            "grant_type": "authorization_code",
        }

        try:
            response = await client.post(
                f"{config.MICROSOFT_AUTH_URL}/{config.MICROSOFT_TENANT}/oauth2/v2.0/token",
                data=data,
            )
            response.raise_for_status()
        except Exception as err:
            raise AuthError(f"Failed to get access token: {err}", 503) from err

        token_data = response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            raise AuthError("Failed to retrieve access token from Microsoft", 400)

        return str(access_token)

    @staticmethod
    async def get_user_info(client: httpx.AsyncClient, access_token: str) -> UserInfo:
        try:
            response = await client.get(
                config.MICROSOFT_GRAPH_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
        except Exception as err:
            raise AuthError(f"Failed to get user info: {err}", 503) from err

        result = response.json()
        email = result.get("mail")
        if not email:
            other_mails = result.get("otherMails")
            email = (
                other_mails[0]
                if other_mails and len(other_mails) > 0
                else result.get("userPrincipalName")
            )

        return UserInfo(
            email=email,
            full_name=result.get("displayName", email),
            photo_url=None,
        )
