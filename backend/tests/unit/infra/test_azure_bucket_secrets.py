from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid7

import pytest
from luml.clients.azure_storage_client import AzureBlobClient
from luml.infra.encryption import decrypt
from luml.models import BucketSecretOrm
from luml.schemas.bucket_secrets import (
    AzureBucketSecretCreate,
    AzureBucketSecretOut,
    validate_bucket_secret_out,
)
from pydantic import ValidationError

from tests.support.bucket_secrets import CONNECTION_STRING, PUBLIC_ENDPOINT


@pytest.mark.parametrize(
    "endpoint",
    [
        "",
        "AccountName=testaccount",
        f"{CONNECTION_STRING};malformed",
        f"{CONNECTION_STRING};AccountName=duplicate",
    ],
)
def test_azure_creation_rejects_invalid_connection_strings(endpoint: str) -> None:
    with pytest.raises(ValidationError):
        AzureBucketSecretCreate(
            organization_id=uuid7(), endpoint=endpoint, bucket_name="container"
        )


def test_azure_connection_string_is_encrypted_and_usable_by_storage_client() -> None:
    secret = AzureBucketSecretCreate(
        organization_id=uuid7(), endpoint=CONNECTION_STRING, bucket_name="container"
    )
    stored = BucketSecretOrm.from_bucket_secret(secret)
    stored.id = uuid7()
    stored.created_at = datetime.now(UTC)

    assert stored.endpoint == PUBLIC_ENDPOINT
    assert stored.connection_string != CONNECTION_STRING
    assert stored.connection_string is not None
    assert decrypt(stored.connection_string) == CONNECTION_STRING
    assert "AccountKey" not in repr(stored)

    internal = stored.to_bucket_secret()
    assert internal.endpoint == CONNECTION_STRING
    assert validate_bucket_secret_out(internal).endpoint == PUBLIC_ENDPOINT
    assert validate_bucket_secret_out(stored).endpoint == PUBLIC_ENDPOINT

    with patch("luml.clients.azure_storage_client.BlobServiceClient") as service:
        AzureBlobClient(internal)  # type: ignore[arg-type]
    service.from_connection_string.assert_called_once_with(CONNECTION_STRING)


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        (CONNECTION_STRING, PUBLIC_ENDPOINT),
        (PUBLIC_ENDPOINT, PUBLIC_ENDPOINT),
        (
            "AccountKey=private; AccountName=testaccount ;"
            "SharedAccessSignature=private;EndpointSuffix=core.windows.net;",
            PUBLIC_ENDPOINT,
        ),
        (
            "AccountName=testaccount;AccountKey=private;"
            "BlobEndpoint=https://custom.example/?sig=private",
            "AccountName=testaccount",
        ),
        ("unrecognized-private-value", ""),
    ],
)
def test_azure_output_exposes_only_account_name_and_suffix(
    endpoint: str, expected: str
) -> None:
    output = AzureBucketSecretOut(
        id=uuid7(),
        organization_id=uuid7(),
        endpoint=endpoint,
        bucket_name="container",
        created_at=datetime.now(UTC),
    )

    assert output.endpoint == expected
    assert "AccountKey" not in output.model_dump_json()
    assert "private" not in output.model_dump_json()
