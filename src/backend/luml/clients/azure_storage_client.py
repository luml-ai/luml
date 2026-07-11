import base64
from datetime import UTC, datetime, timedelta
from uuid import UUID

from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    ContainerClient,
    ContentSettings,
    generate_blob_sas,
)

from luml.clients.base_storage_client import BaseStorageClient
from luml.infra.exceptions import BucketConnectionError
from luml.schemas.bucket_secrets import (
    AzureBucketSecret,
    AzureBucketSecretCreateIn,
    BucketType,
)
from luml.schemas.storage import (
    AzureMultiPartUploadDetails,
    AzureUploadDetails,
)


class AzureBlobClient(BaseStorageClient):
    def __init__(self, secret: AzureBucketSecret | AzureBucketSecretCreateIn) -> None:
        self._bucket_id: UUID | None = getattr(secret, "id", None)
        self._container_name = secret.bucket_name
        self._client = self._create_client(secret)
        self._account_name = self._extract_account_name(secret)
        self._account_key = self._extract_account_key(secret)

    @staticmethod
    def _create_client(  # type: ignore[override]
        secret: AzureBucketSecret | AzureBucketSecretCreateIn,
    ) -> ContainerClient:
        try:
            if secret.endpoint and "AccountName=" in secret.endpoint:
                account_client = BlobServiceClient.from_connection_string(
                    secret.endpoint
                )
                return account_client.get_container_client(secret.bucket_name)
            raise ValueError("Invalid Azure credentials. Provide Connection string.")
        except Exception as error:
            raise BucketConnectionError(
                "Failed to create Azure Blob Service client."
            ) from error

    @staticmethod
    def _extract_field_from_connection_string(
        connection_string: str, field: str
    ) -> str:
        if f"{field}=" in connection_string:
            for part in connection_string.split(";"):
                if part.startswith(f"{field}="):
                    return part.split("=", 1)[1]
        raise ValueError(f"Could not extract {field} from connection string")

    def _extract_account_name(
        self, secret: AzureBucketSecret | AzureBucketSecretCreateIn
    ) -> str:
        return self._extract_field_from_connection_string(
            secret.endpoint, "AccountName"
        )

    def _extract_account_key(
        self, secret: AzureBucketSecret | AzureBucketSecretCreateIn
    ) -> str:
        return self._extract_field_from_connection_string(secret.endpoint, "AccountKey")

    @staticmethod
    def _get_part_id(part_number: int) -> str:
        return base64.b64encode(f"block-{part_number:08d}".encode()).decode()

    def _generate_sas_url(
        self,
        blob_name: str,
        permission: BlobSasPermissions,
        content_settings: ContentSettings | None = None,
    ) -> str:
        try:
            sas_token = generate_blob_sas(
                account_name=self._account_name,
                container_name=self._container_name,
                blob_name=blob_name,
                account_key=self._account_key,
                permission=permission,
                expiry=datetime.now(UTC) + timedelta(hours=self._url_expire),
                content_settings=content_settings,
            )

            blob_client = self._client.get_blob_client(blob_name)
            return f"{blob_client.url}?{sas_token}"

        except Exception as error:
            raise BucketConnectionError("Failed to generate SAS URL.") from error

    async def get_upload_url(self, object_name: str) -> str:
        return self._generate_sas_url(
            object_name,
            BlobSasPermissions(write=True, create=True),
        )

    async def get_download_url(self, object_name: str) -> str:
        return self._generate_sas_url(
            object_name,
            BlobSasPermissions(read=True),
        )

    async def get_delete_url(self, object_name: str) -> str:
        return self._generate_sas_url(
            object_name,
            BlobSasPermissions(delete=True),
        )

    async def get_complete_url(self, object_name: str) -> str:
        url = self._generate_sas_url(
            object_name,
            BlobSasPermissions(write=True, create=True),
        )

        separator = "&" if "?" in url else "?"
        return f"{url}{separator}comp=blocklist"

    async def _get_multipart_upload_urls(
        self, object_name: str, parts_count: int
    ) -> list[str]:
        try:
            urls = []
            for part_number in range(1, parts_count + 1):
                url = self._generate_sas_url(
                    object_name,
                    BlobSasPermissions(write=True, create=True),
                )
                separator = "&" if "?" in url else "?"
                urls.append(
                    f"{url}{separator}comp=block&blockid={self._get_part_id(part_number)}"
                )

            return urls
        except Exception as error:
            raise BucketConnectionError(
                "Failed to generate multipart upload URLs."
            ) from error

    async def create_multipart_upload(
        self, bucket_location: str, size: int, upload_id: str | None = None
    ) -> AzureMultiPartUploadDetails:
        parts_count, part_size = self._calculate_multipart_params(size)

        urls = await self._get_multipart_upload_urls(bucket_location, parts_count)
        return AzureMultiPartUploadDetails(
            parts=self._parts_upload_details(urls, size, part_size),
            complete_url=await self.get_complete_url(bucket_location),
        )

    async def create_upload(
        self, bucket_location: str, size: int
    ) -> AzureUploadDetails:
        if self._bucket_id is None:
            raise ValueError("Bucket secret ID is required for creating upload URLs")

        self.validate_size(size)

        if self._should_use_multipart(size):
            return AzureUploadDetails(
                type=BucketType.AZURE,
                multipart=True,
                bucket_location=bucket_location,
                bucket_secret_id=self._bucket_id,
            )
        return AzureUploadDetails(
            type=BucketType.AZURE,
            url=await self.get_upload_url(bucket_location),
            bucket_location=bucket_location,
            bucket_secret_id=self._bucket_id,
        )
