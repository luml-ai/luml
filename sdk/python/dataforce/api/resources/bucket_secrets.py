from abc import ABC, abstractmethod
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any

from .._types import BucketSecret, is_uuid
from .._utils import find_by_value

if TYPE_CHECKING:
    from .._client import AsyncDataForceClient, DataForceClient


class BucketSecretResourceBase(ABC):
    """Abstract base class for bucket secret resource operations."""

    @abstractmethod
    def get(
        self, secret_value: str
    ) -> BucketSecret | None | Coroutine[Any, Any, BucketSecret | None]:
        raise NotImplementedError()

    @abstractmethod
    def _get_by_id(
        self, secret_id: str
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
        secret_id: str,
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
    def delete(self, secret_id: str) -> None | Coroutine[Any, Any, None]:
        raise NotImplementedError()


class BucketSecretResource(BucketSecretResourceBase):
    """Resource for managing Bucket Secrets."""

    def __init__(self, client: "DataForceClient") -> None:
        self._client = client

    def get(self, secret_value: str) -> BucketSecret | None:
        """
        Get BucketSecret by ID or bucket name.

        Retrieves BucketSecret details by its ID or bucket name.
        Search by name is case-sensitive and matches exact bucket name.

        Args:
            secret_value: The ID or exact bucket name of the bucket secret to retrieve.

        Returns:
            BucketSecret object.

            Returns None if bucket secret with the specified id or name is not found.

        Raises:
            MultipleResourcesFoundError: if there are several
                BucketSecret with that bucket name.

        Example:
            >>> dfs = DataForceClient(
            ...     api_key="dfs_your_key",
            ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
            ... )
            ... bucket_by_name = dfs.bucket_secrets.get("default-bucket")
            ... bucket_by_id = dfs.bucket_secrets.get(
            ...     "0199c455-21ef-79d9-9dfc-fec3d72bf4b5"
            ...)

        Example response:
            >>> BucketSecret(
            ...    id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
            ...    endpoint='default-endpoint',
            ...    bucket_name='default-bucket',
            ...    secure=None,
            ...    region=None,
            ...    cert_check=None,
            ...    organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
            ...    created_at='2025-05-21T19:35:17.340408Z',
            ...    updated_at='2025-08-13T22:44:58.035731Z'
            ...)
        """
        if is_uuid(secret_value):
            return self._get_by_id(secret_value)
        return self._get_by_name(secret_value)

    def _get_by_id(self, secret_id: str) -> BucketSecret:
        response = self._client.get(
            f"/organizations/{self._client.organization}/bucket-secrets/{secret_id}"
        )
        return BucketSecret.model_validate(response)

    def _get_by_name(self, name: str) -> BucketSecret | None:
        return find_by_value(self.list(), name, lambda b: b.bucket_name == name)

    def list(self) -> list[BucketSecret]:
        """
        List all bucket secrets in the default organization.

        Returns:
            List of BucketSecret objects.

        Example:
            >>> dfs = DataForceClient(
            ...     api_key="dfs_your_key",
            ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
            ... )
            >>> secrets = dfs.bucket_secrets.list()

        Example response:
            >>> [
            ...     BucketSecret(
            ...         id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
            ...         endpoint='default-endpoint',
            ...         bucket_name='default-bucket',
            ...         secure=None,
            ...         region=None,
            ...         cert_check=None,
            ...         organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
            ...         created_at='2025-06-18T12:44:54.443715Z',
            ...         updated_at=None
            ...     )
            ...]
        """
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
        """
        Create new bucket secret in the default organization.

        Args:
            endpoint: S3-compatible storage endpoint URL (e.g., 's3.amazonaws.com').
            bucket_name: Name of the storage bucket.
            access_key: Access key for bucket authentication.
                Optional for some providers.
            secret_key: Secret key for bucket authentication.
                Optional for some providers.
            session_token: Temporary session token for authentication. Optional.
            secure: Use HTTPS for connections.Optional.
            region: Storage region identifier (e.g., 'us-east-1'). Optional.
            cert_check: Verify SSL certificates.Optional.

        Returns:
            BucketSecret: Сreated bucket secret object.

        Example:
            >>> dfs = DataForceClient(
            ...     api_key="dfs_your_key",
            ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
            ... )
            >>> bucket_secret = dfs.bucket_secrets.create(
            ...     endpoint="s3.amazonaws.com",
            ...     bucket_name="my-data-bucket",
            ...     access_key="AKIAIOSFODNN7EXAMPLE",
            ...     secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            ...     region="us-east-1",
            ...     secure=True
            ... )

        Response object:
            >>> BucketSecret(
            ...     id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
            ...     endpoint="s3.amazonaws.com",
            ...     bucket_name="my-data-bucket",
            ...     secure=True,
            ...     region="us-east-1",
            ...     cert_check=True,
            ...     organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
            ...     created_at='2025-01-15T10:30:00.123456Z',
            ...     updated_at=None
            ... )
        """
        response = self._client.post(
            f"/organizations/{self._client.organization}/bucket-secrets",
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

    def update(
        self,
        secret_id: str,
        endpoint: str | None = None,
        bucket_name: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        session_token: str | None = None,
        secure: bool | None = None,
        region: str | None = None,
        cert_check: bool | None = None,
    ) -> BucketSecret:
        """
        Update existing bucket secret.

        Updates the bucket secret's. Only provided parameters will be
        updated, others remain unchanged.

        Args:
            secret_id: ID of the bucket secret to update.
            endpoint: S3-compatible storage endpoint URL (e.g., 's3.amazonaws.com').
            bucket_name: Name of the storage bucket.
            access_key: Access key for bucket authentication.
            secret_key: Secret key for bucket authentication.
            session_token: Temporary session token for authentication.
            secure: Use HTTPS for connections.
            region: Storage region identifier (e.g., 'us-east-1').
            cert_check: Verify SSL certificates.

        Returns:
            BucketSecret: Updated bucket secret object.

        Example:
            >>> dfs = DataForceClient(
            ...     api_key="dfs_your_key",
            ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
            ... )
            >>> bucket_secret = dfs.bucket_secrets.update(
            ...     secret_id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
            ...     endpoint="s3.amazonaws.com",
            ...     bucket_name="updated-bucket",
            ...     region="us-west-2",
            ...     secure=True
            ... )

        Response object:
            >>> BucketSecret(
            ...     id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
            ...     endpoint="s3.amazonaws.com",
            ...     bucket_name="updated-bucket",
            ...     secure=True,
            ...     region="us-west-2",
            ...     cert_check=True,
            ...     organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
            ...     created_at='2025-01-15T10:30:00.123456Z',
            ...     updated_at='2025-01-15T14:22:30.987654Z'
            ... )
        """
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

    def delete(self, secret_id: str) -> None:
        """
        Delete bucket secret permanently.

        Permanently removes the bucket secret from the organization. This action
        cannot be undone. Any orbits using this bucket secret will lose access
        to their storage.

        Args:
            secret_id: ID of the bucket secret to delete.

        Returns:
            None: No return value on successful deletion.

        Example:
            >>> dfs = DataForceClient(
            ...     api_key="dfs_your_key",
            ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
            ... )
            >>> dfs.bucket_secrets.delete("0199c455-21f2-7131-9a20-da66246845c7")

        Warning:
            This operation is irreversible. Orbits using this bucket secret
            will lose access to their storage. Ensure no active orbits depend
            on this bucket secret before deletion.
        """
        return self._client.delete(
            f"/organizations/{self._client.organization}/bucket-secrets/{secret_id}"
        )


class AsyncBucketSecretResource(BucketSecretResourceBase):
    """Resource for managing Bucket Secrets for async client."""

    def __init__(self, client: "AsyncDataForceClient") -> None:
        self._client = client

    async def get(self, secret_value: str) -> BucketSecret | None:
        """
        Get BucketSecret by ID or bucket name.

        Retrieves BucketSecret details by its ID or bucket name.
        Search by name is case-sensitive and matches exact bucket name.

        Args:
            secret_value: The ID or exact bucket name of the bucket secret to retrieve.

        Returns:
            BucketSecret object.

            Returns None if bucket secret with the specified id or name is not found.

        Raises:
            MultipleResourcesFoundError: if there are several
                BucketSecret with that bucket name.

        Example:
            >>> dfs = AsyncDataForceClient(
            ...     api_key="dfs_your_key",
            ... )
            ... dfs.setup_config(
            ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
            ... )
            >>> async def main():
            ...     bucket_by_name = await dfs.bucket_secrets.get("default-bucket")
            ...     bucket_by_id = await dfs.bucket_secrets.get(
            ...         "0199c45c-1b0b-7c82-890d-e31ab10d1e5d"
            ...     )

        Example response:
            >>> BucketSecret(
            ...         id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
            ...         endpoint='default-endpoint',
            ...         bucket_name='default-bucket',
            ...         secure=None,
            ...         region=None,
            ...         cert_check=None,
            ...         organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
            ...         created_at='2025-05-21T19:35:17.340408Z',
            ...         updated_at='2025-08-13T22:44:58.035731Z'
            ... )
        """
        if is_uuid(secret_value):
            return await self._get_by_id(secret_value)
        return await self._get_by_name(secret_value)

    async def _get_by_id(self, secret_id: str) -> BucketSecret:
        response = await self._client.get(
            f"/organizations/{self._client.organization}/bucket-secrets/{secret_id}"
        )
        return BucketSecret.model_validate(response)

    async def _get_by_name(self, name: str) -> BucketSecret | None:
        return find_by_value(await self.list(), name, lambda b: b.bucket_name == name)

    async def list(self) -> list[BucketSecret]:
        """
        List all bucket secrets in the default organization.

        Returns:
            List of BucketSecret objects.

        Example:
            >>> dfs = AsyncDataForceClient(
            ...     api_key="dfs_your_key",
            ... )
            ... dfs.setup_config(
            ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
            ... )
            >>> async def main():
            ...     secrets = await dfs.bucket_secrets.list()

        Example response:
            >>> [
            ...     BucketSecret(
            ...         id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
            ...         endpoint='default-endpoint',
            ...         bucket_name='default-bucket',
            ...         secure=None,
            ...         region=None,
            ...         cert_check=None,
            ...         organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
            ...         created_at='2025-06-18T12:44:54.443715Z',
            ...         updated_at=None
            ...     )
            ...]
        """
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
        """
        Create new bucket secret in the default organization.

        Args:
            endpoint: S3-compatible storage endpoint URL (e.g., 's3.amazonaws.com').
            bucket_name: Name of the storage bucket.
            access_key: Access key for bucket authentication.
                Optional for some providers.
            secret_key: Secret key for bucket authentication.
                Optional for some providers.
            session_token: Temporary session token for authentication. Optional.
            secure: Use HTTPS for connections.Optional.
            region: Storage region identifier (e.g., 'us-east-1'). Optional.
            cert_check: Verify SSL certificates.Optional.

        Returns:
            BucketSecret: Сreated bucket secret object.

        Example:
            >>> dfs = AsyncDataForceClient(
            ...     api_key="dfs_your_key",
            ... )
            ... dfs.setup_config(
            ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
            ... )
            >>> async def main():
            ...     bucket_secret = await dfs.bucket_secrets.create(
            ...         endpoint="s3.amazonaws.com",
            ...         bucket_name="my-data-bucket",
            ...         access_key="AKIAIOSFODNN7EXAMPLE",
            ...         secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            ...         region="us-east-1",
            ...         secure=True
            ...     )

        Response object:
            >>> BucketSecret(
            ...     id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
            ...     endpoint="s3.amazonaws.com",
            ...     bucket_name="my-data-bucket",
            ...     secure=True,
            ...     region="us-east-1",
            ...     cert_check=True,
            ...     organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
            ...     created_at='2025-01-15T10:30:00.123456Z',
            ...     updated_at=None
            ... )
        """
        response = await self._client.post(
            f"/organizations/{self._client.organization}/bucket-secrets",
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

    async def update(
        self,
        secret_id: str,
        endpoint: str | None = None,
        bucket_name: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        session_token: str | None = None,
        secure: bool | None = None,
        region: str | None = None,
        cert_check: bool | None = None,
    ) -> BucketSecret:
        """
        Update existing bucket secret.

        Updates the bucket secret's. Only provided parameters will be
        updated, others remain unchanged.

        Args:
            secret_id: ID of the bucket secret to update.
            endpoint: S3-compatible storage endpoint URL (e.g., 's3.amazonaws.com').
            bucket_name: Name of the storage bucket.
            access_key: Access key for bucket authentication.
            secret_key: Secret key for bucket authentication.
            session_token: Temporary session token for authentication.
            secure: Use HTTPS for connections.
            region: Storage region identifier (e.g., 'us-east-1').
            cert_check: Verify SSL certificates.

        Returns:
            BucketSecret: Updated bucket secret object.

        Example:
            >>> dfs = AsyncDataForceClient(
            ...     api_key="dfs_your_key",
            ... )
            ... dfs.setup_config(
            ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
            ... )
            >>> async def main():
            ...     bucket_secret = await dfs.bucket_secrets.update(
            ...         id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
            ...         endpoint="s3.amazonaws.com",
            ...         bucket_name="updated-bucket",
            ...         region="us-west-2",
            ...         secure=True
            ...     )

        Response object:
            >>> BucketSecret(
            ...     id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
            ...     endpoint="s3.amazonaws.com",
            ...     bucket_name="updated-bucket",
            ...     secure=True,
            ...     region="us-west-2",
            ...     cert_check=True,
            ...     organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
            ...     created_at='2025-01-15T10:30:00.123456Z',
            ...     updated_at='2025-01-15T14:22:30.987654Z'
            ... )
        """
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

    async def delete(self, secret_id: str) -> None:
        """
        Delete bucket secret permanently.

        Permanently removes the bucket secret from the organization. This action
        cannot be undone. Any orbits using this bucket secret will lose access
        to their storage.

        Args:
            secret_id: ID of the bucket secret to delete.

        Returns:
            None: No return value on successful deletion.

        Example:
            >>> dfs = AsyncDataForceClient(
            ...     api_key="dfs_your_key",
            ... )
            ... dfs.setup_config(
            ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
            ... )
            >>> async def main():
            ...     await dfs.bucket_secrets.delete(
            ...         "0199c455-21ef-79d9-9dfc-fec3d72bf4b5"
            ...     )

        Warning:
            This operation is irreversible. Orbits using this bucket secret
            will lose access to their storage. Ensure no active orbits depend
            on this bucket secret before deletion.
        """
        return await self._client.delete(
            f"/organizations/{self._client.organization}/bucket-secrets/{secret_id}"
        )
