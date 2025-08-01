from typing import TYPE_CHECKING

from .._types import BucketSecret
from .._utils import find_by_name
from ._validators import validate_organization

if TYPE_CHECKING:
    from .._client import AsyncDataForceClient, DataForceClient


class BucketSecretResource:
    def __init__(self, client: "DataForceClient") -> None:
        self._client = client

    @validate_organization
    def get(self, organization_id: int, secret_id: int) -> BucketSecret:
        response = self._client.get(
            f"/organizations/{organization_id}/bucket-secrets/{secret_id}"
        )
        return BucketSecret.model_validate(response)

    @validate_organization
    def get_by_name(self, organization_id: int, name: str) -> BucketSecret | None:
        return find_by_name(
            self.list(organization_id), name, lambda b: b.bucket_name == name
        )

    @validate_organization
    def list(self, organization_id: int) -> list[BucketSecret]:
        response = self._client.get(f"/organizations/{organization_id}/bucket-secrets")
        if response is None:
            return []
        return [BucketSecret.model_validate(secret) for secret in response]

    @validate_organization
    def create(
        self,
        organization_id: int,
        endpoint: str,
        bucket_name: str,
        access_key: str | None = None,
        secret_key: str | None = None,
        session_token: str | None = None,
        secure: bool | None = None,
        region: str | None = None,
        cert_check: bool | None = None,
    ) -> BucketSecret:
        response = self._client.post(
            f"/organizations/{organization_id}/bucket-secrets",
            json={
                "endpoint": endpoint,
                "bucket_name": bucket_name,
                "access_key": access_key,
                "secret_key": secret_key,
                "session_token": session_token,
                "secure": secure,
                "region": region,
                "cert_check": cert_check,
            },
        )
        return BucketSecret.model_validate(response)

    @validate_organization
    def update(
        self,
        organization_id: int,
        secret_id: int,
        endpoint: str | None = None,
        bucket_name: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        session_token: str | None = None,
        secure: bool | None = None,
        region: str | None = None,
        cert_check: bool | None = None,
    ) -> BucketSecret:
        response = self._client.patch(
            f"/organizations/{organization_id}/bucket-secrets/{secret_id}",
            json=self._client.filter_none(
                {
                    "endpoint": endpoint,
                    "bucket_name": bucket_name,
                    "access_key": access_key,
                    "secret_key": secret_key,
                    "session_token": session_token,
                    "secure": secure,
                    "region": region,
                    "cert_check": cert_check,
                }
            ),
        )
        return BucketSecret.model_validate(response)

    @validate_organization
    def delete(self, organization_id: int, secret_id: int) -> None:
        return self._client.delete(
            f"/organizations/{organization_id}/bucket-secrets/{secret_id}"
        )


class AsyncBucketSecretResource:
    def __init__(self, client: "AsyncDataForceClient") -> None:
        self._client = client

    @validate_organization
    async def get(self, organization_id: int, secret_id: int) -> BucketSecret:
        response = await self._client.get(
            f"/organizations/{organization_id}/bucket-secrets/{secret_id}"
        )
        return BucketSecret.model_validate(response)

    @validate_organization
    async def get_by_name(self, organization_id: int, name: str) -> BucketSecret | None:
        return find_by_name(
            await self.list(organization_id), name, lambda b: b.bucket_name == name
        )

    @validate_organization
    async def list(self, organization_id: int) -> list[BucketSecret]:
        response = await self._client.get(
            f"/organizations/{organization_id}/bucket-secrets"
        )
        if response is None:
            return []
        return [BucketSecret.model_validate(secret) for secret in response]

    @validate_organization
    async def create(
        self,
        organization_id: int,
        endpoint: str,
        bucket_name: str,
        access_key: str | None = None,
        secret_key: str | None = None,
        session_token: str | None = None,
        secure: bool | None = None,
        region: str | None = None,
        cert_check: bool | None = None,
    ) -> BucketSecret:
        response = await self._client.post(
            f"/organizations/{organization_id}/bucket-secrets",
            json={
                "endpoint": endpoint,
                "bucket_name": bucket_name,
                "access_key": access_key,
                "secret_key": secret_key,
                "session_token": session_token,
                "secure": secure,
                "region": region,
                "cert_check": cert_check,
            },
        )
        return BucketSecret.model_validate(response)

    @validate_organization
    async def update(
        self,
        organization_id: int,
        secret_id: int,
        endpoint: str | None = None,
        bucket_name: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        session_token: str | None = None,
        secure: bool | None = None,
        region: str | None = None,
        cert_check: bool | None = None,
    ) -> BucketSecret:
        response = await self._client.patch(
            f"/organizations/{organization_id}/bucket-secrets/{secret_id}",
            json=self._client.filter_none(
                {
                    "endpoint": endpoint,
                    "bucket_name": bucket_name,
                    "access_key": access_key,
                    "secret_key": secret_key,
                    "session_token": session_token,
                    "secure": secure,
                    "region": region,
                    "cert_check": cert_check,
                }
            ),
        )
        return BucketSecret.model_validate(response)

    @validate_organization
    async def delete(self, organization_id: int, secret_id: int) -> None:
        return await self._client.delete(
            f"/organizations/{organization_id}/bucket-secrets/{secret_id}"
        )
