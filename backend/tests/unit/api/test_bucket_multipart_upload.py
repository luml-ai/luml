from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from luml.constants import MAX_FILE_SIZE_BYTES

from tests.unit.handlers.bucket_secrets.conftest import SECRET_ID


@pytest.mark.parametrize("size", [-1, 0, MAX_FILE_SIZE_BYTES + 1, 10**18])
def test_multipart_endpoint_rejects_invalid_size(client: TestClient, size: int) -> None:
    with patch(
        "luml.handlers.bucket_secrets.BucketSecretHandler.get_bucket_multipart_urls",
        new_callable=AsyncMock,
    ) as get_urls:
        response = client.post(
            "/v1/bucket-secrets/upload/multipart",
            json={
                "bucket_id": str(SECRET_ID),
                "bucket_location": "orbit/collection/model.luml",
                "size": size,
                "upload_id": "upload_id",
            },
        )

    assert response.status_code == 422
    get_urls.assert_not_awaited()
