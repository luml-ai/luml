from api.luml_api._types import BucketType
from api.luml_api.handlers.azure_file_handler import AzureFileHandler
from api.luml_api.handlers.base_file_handler import BaseFileHandler
from api.luml_api.handlers.s3_file_handler import S3FileHandler


def create_file_handler(bucket_type: BucketType) -> BaseFileHandler:
    if bucket_type == BucketType.S3:
        return S3FileHandler()
    if bucket_type == BucketType.AZURE:
        return AzureFileHandler()
    raise ValueError(
        f"Unsupported bucket type: {bucket_type}. "
        f"Supported types: {[t.value for t in BucketType]}"
    )
