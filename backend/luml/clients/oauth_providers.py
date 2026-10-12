from abc import ABC, abstractmethod
from urllib.parse import urlencode
from uuid import UUID

import httpx
import jwt

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
    async def get_user_info(client: httpx.AsyncClient, token: str) -> UserInfo:
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
    async def exchange_code_for_token(
        client: httpx.AsyncClient,
        code: str,
        redirect_uri: str = config.GOOGLE_REDIRECT_URI,
    ) -> str:
        data = {
            "code": code,
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
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
    async def get_user_info(client: httpx.AsyncClient, token: str) -> UserInfo:
        try:
            response = await client.get(
                config.GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
        except Exception as err:
            raise AuthError(f"Failed to get user info: {err}", 503) from err

        result = response.json()

        return UserInfo(
            email=result.get("email"),
            full_name=result.get("name"),
            photo_url=result.get("picture"),
            email_verified=result.get("verified_email") is True,
            hosted_domain=result.get("hd"),
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
            "scope": "openid email profile",
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
        id_token = token_data.get("id_token")

        if not isinstance(id_token, str) or not id_token:
            raise AuthError("Failed to retrieve ID token from Microsoft", 400)

        return id_token

    @staticmethod
    async def get_user_info(client: httpx.AsyncClient, token: str) -> UserInfo:
        try:
            header = jwt.get_unverified_header(token)
            unverified = jwt.decode(token, options={"verify_signature": False})
            tenant_id = str(UUID(unverified["tid"]))
            authority = config.MICROSOFT_AUTH_URL.rstrip("/")
            expected_issuer = f"{authority}/{tenant_id}/v2.0"
            if (
                config.MICROSOFT_TENANT.lower() == "organizations"
                and tenant_id == "9188040d-6c67-4c5b-b112-36a304b66dad"
            ):
                raise jwt.InvalidIssuerError("Consumer account is not allowed")

            response = await client.get(
                f"{authority}/{config.MICROSOFT_TENANT}"
                "/v2.0/.well-known/openid-configuration"
            )
            response.raise_for_status()
            metadata = response.json()
            issuer = metadata["issuer"].replace("{tenantid}", tenant_id)
            if issuer != expected_issuer:
                raise jwt.InvalidIssuerError("Tenant does not match configured issuer")

            response = await client.get(metadata["jwks_uri"])
            response.raise_for_status()
            signing_key = next(
                key for key in response.json()["keys"] if key["kid"] == header["kid"]
            )
            if signing_key["issuer"].replace("{tenantid}", tenant_id) != issuer:
                raise jwt.InvalidIssuerError("Signing key issuer does not match")

            result = jwt.decode(
                token,
                jwt.PyJWK.from_dict(signing_key, algorithm="RS256"),
                algorithms=["RS256"],
                audience=config.MICROSOFT_CLIENT_ID,
                issuer=issuer,
                options={"require": ["iss", "aud", "exp", "iat", "sub", "tid"]},
            )

            return UserInfo(
                email=result.get("email"),
                full_name=result.get("name") or result.get("email") or "",
                photo_url=None,
                email_verified=(
                    result.get("email_verified") is True
                    or result.get("xms_edov") is True
                ),
            )
        except httpx.HTTPError as err:
            raise AuthError("Failed to verify Microsoft ID token", 503) from err
        except (
            jwt.PyJWTError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            StopIteration,
        ) as err:
            raise AuthError("Invalid Microsoft ID token", 403) from err
