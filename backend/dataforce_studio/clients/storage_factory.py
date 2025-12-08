from dataforce_studio.clients.azure_storage_client import AzureBlobClient
from dataforce_studio.clients.s3_storage_client import S3Client
from dataforce_studio.schemas.bucket_secrets import (
    BucketType,
)


def create_storage_client(
    secret_type: BucketType,
) -> type[AzureBlobClient | S3Client]:
    match secret_type:
        case BucketType.S3:
            return S3Client
        case BucketType.AZURE:
            return AzureBlobClient
        case _:
            raise ValueError(f"Unsupported bucket secret type: {secret_type}")
