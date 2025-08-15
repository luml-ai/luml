from abc import ABC, abstractmethod
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any

from .._types import BucketSecret
from .._utils import find_by_name

if TYPE_CHECKING:
    from .._client import AsyncDataForceClient, DataForceClient


class BucketSecretResourceBase(ABC):
    @abstractmethod
    def get(
        self, secret_value: int | str
    ) -> BucketSecret | None | Coroutine[Any, Any, BucketSecret | None]:
        raise NotImplementedError()

    @abstractmethod
    def _get_by_id(
        self, secret_id: int
    ) -> BucketSecret | Coroutine[Any, Any, BucketSecret]:
        raise NotImplementedError()

    @abstractmethod
    def _get_by_name(
        self, name: str
    ) -> BucketSecret | None | Coroutine[Any, Any, BucketSecret | None]:
        raise NotImplementedError()

    @abstractmethod
    def list(self) -> list[BucketSecret] | Coroutine[Any, Any, list[BucketSecret]]:
        raise NotImplementedError()

    @abstractmethod
    def create(
        self,
        endpoint: str,
        bucket_name: str,
        access_key: str | None = None,
        secret_key: str | None = None,
        session_token: str | None = None,
        secure: bool | None = None,
        region: str | None = None,
        cert_check: bool | None = None,
    ) -> BucketSecret | Coroutine[Any, Any, BucketSecret]:
        raise NotImplementedError()

    @abstractmethod
    def update(
        self,
        secret_id: int,
        endpoint: str | None = None,
        bucket_name: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        session_token: str | None = None,
        secure: bool | None = None,
        region: str | None = None,
        cert_check: bool | None = None,
    ) -> BucketSecret | Coroutine[Any, Any, BucketSecret]:
        raise NotImplementedError()

    @abstractmethod
    def delete(self, secret_id: int) -> None | Coroutine[Any, Any, None]:
        raise NotImplementedError()


class BucketSecretResource(BucketSecretResourceBase):
    def __init__(self, client: "DataForceClient") -> None:
        self._client = client

    def get(self, secret_value: int | str) -> BucketSecret | None:
        if isinstance(secret_value, int):
            return self._get_by_id(secret_value)
        if isinstance(secret_value, str):
            return self._get_by_name(secret_value)
        return None

    def _get_by_id(self, secret_id: int) -> BucketSecret:
        response = self._client.get(
            f"/organizations/{self._client.organization}/bucket-secrets/{secret_id}"
        )
        return BucketSecret.model_validate(response)

    def _get_by_name(self, name: str) -> BucketSecret | None:
        return find_by_name(self.list(), name, lambda b: b.bucket_name == name)

    def list(self) -> list[BucketSecret]:
        response = self._client.get(
            f"/organizations/{self._client.organization}/bucket-secrets"
        )
        if response is None:
            return []
        return [BucketSecret.model_validate(secret) for secret in response]

    def create(
        self,
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
            f"/organizations/{self._client.organization}/bucket-secrets",
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

    def update(
        self,
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
            f"/organizations/{self._client.organization}/bucket-secrets/{secret_id}",
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

    def delete(self, secret_id: int) -> None:
        return self._client.delete(
            f"/organizations/{self._client.organization}/bucket-secrets/{secret_id}"
        )


class AsyncBucketSecretResource(BucketSecretResourceBase):
    def __init__(self, client: "AsyncDataForceClient") -> None:
        self._client = client

    async def get(self, secret_value: int | str) -> BucketSecret | None:
        if isinstance(secret_value, int):
            return await self._get_by_id(secret_value)
        if isinstance(secret_value, str):
            return await self._get_by_name(secret_value)
        return None

    async def _get_by_id(self, secret_id: int) -> BucketSecret:
        response = await self._client.get(
            f"/organizations/{self._client.organization}/bucket-secrets/{secret_id}"
        )
        return BucketSecret.model_validate(response)

    async def _get_by_name(self, name: str) -> BucketSecret | None:
        return find_by_name(await self.list(), name, lambda b: b.bucket_name == name)

    async def list(self) -> list[BucketSecret]:
        response = await self._client.get(
            f"/organizations/{self._client.organization}/bucket-secrets"
        )
        if response is None:
            return []
        return [BucketSecret.model_validate(secret) for secret in response]

    async def create(
        self,
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
            f"/organizations/{self._client.organization}/bucket-secrets",
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

    async def update(
        self,
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
            f"/organizations/{self._client.organization}/bucket-secrets/{secret_id}",
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

    async def delete(self, secret_id: int) -> None:
        return await self._client.delete(
            f"/organizations/{self._client.organization}/bucket-secrets/{secret_id}"
        )
