import pytest

from luml_api._types import BucketType
from luml_api.handlers.azure_file_handler import AzureFileHandler
from luml_api.handlers.file_handler_factory import create_file_handler
from luml_api.handlers.s3_file_handler import S3FileHandler


def test_create_file_handler_s3() -> None:
    handler = create_file_handler(BucketType.S3)
    assert isinstance(handler, S3FileHandler)


def test_create_file_handler_azure() -> None:
    handler = create_file_handler(BucketType.AZURE)
    assert isinstance(handler, AzureFileHandler)


def test_create_file_handler_unsupported() -> None:
    with pytest.raises(ValueError, match="Unsupported bucket type"):
        create_file_handler("gcs")  # type: ignore[arg-type]
