from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from luml.schemas.bucket_secrets import (
    BucketSecretUpdate,
    BucketSecretUrls,
    BucketType,
)

from tests.support.auth import ANONYMOUS
from tests.support.ids import ORGANIZATION_ID, USER_ID

SECRET_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")

URLS_PATH = f"/v1/organizations/{ORGANIZATION_ID}/bucket-secrets/{SECRET_ID}/urls"


class TestOrganizationBucketSecrets:
    @pytest.mark.parametrize("principal", [ANONYMOUS], indirect=True)
    @patch(
        "luml.handlers.bucket_secrets.BucketSecretHandler.get_existing_bucket_urls",
        new_callable=AsyncMock,
    )
    def test_existing_bucket_urls_requires_authentication(
        self, mock_get_existing_bucket_urls: AsyncMock, client: TestClient
    ) -> None:
        response = client.post(URLS_PATH, json={"id": str(SECRET_ID), "type": "s3"})

        assert response.status_code == 401
        mock_get_existing_bucket_urls.assert_not_awaited()

    @patch(
        "luml.handlers.bucket_secrets.BucketSecretHandler.get_existing_bucket_urls",
        new_callable=AsyncMock,
    )
    def test_existing_bucket_urls_forwards_path_parameters(
        self, mock_get_existing_bucket_urls: AsyncMock, client: TestClient
    ) -> None:
        mock_get_existing_bucket_urls.return_value = BucketSecretUrls(
            presigned_url="https://bucket/put",
            download_url="https://bucket/get",
            delete_url="https://bucket/delete",
        )

        response = client.post(
            URLS_PATH,
            json={"id": str(SECRET_ID), "type": "s3", "bucket_name": "unsaved"},
        )

        assert response.status_code == 200
        mock_get_existing_bucket_urls.assert_awaited_once_with(
            USER_ID,
            ORGANIZATION_ID,
            SECRET_ID,
            BucketSecretUpdate(id=SECRET_ID, type=BucketType.S3, bucket_name="unsaved"),
        )
