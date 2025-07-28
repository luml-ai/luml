from .._resource import APIResource
from .._types import BucketSecret


class BucketSecretResource(APIResource):
    async def list(self, organization_id: int) -> list[BucketSecret]:
        response = await self._get(f"/organizations/{organization_id}/bucket-secrets")
        if response is None:
            return []
        return [BucketSecret(**secret) for secret in response]

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
        response = await self._post(
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
        return BucketSecret(**response)

    async def get(self, organization_id: int, secret_id: int) -> BucketSecret:
        response = await self._get(
            f"/organizations/{organization_id}/bucket-secrets/{secret_id}"
        )
        return BucketSecret(**response)

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
        response = await self._patch(
            f"/organizations/{organization_id}/bucket-secrets/{secret_id}",
            json=self._filter_none(
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
        return BucketSecret(**response)

    async def delete(self, organization_id: int, secret_id: int) -> None:
        return await self._delete(
            f"/organizations/{organization_id}/bucket-secrets/{secret_id}"
        )
