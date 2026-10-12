from datetime import UTC, datetime
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
from tests.support.bucket_secrets import CONNECTION_STRING, PUBLIC_ENDPOINT
from tests.support.ids import ORGANIZATION_ID, USER_ID

SECRET_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")

URLS_PATH = f"/v1/organizations/{ORGANIZATION_ID}/bucket-secrets/{SECRET_ID}/urls"


class TestOrganizationBucketSecrets:
    @pytest.mark.parametrize(
        "payload",
        [
            {"type": "azure", "endpoint": CONNECTION_STRING},
            {
                "type": "invalid",
                "endpoint": CONNECTION_STRING,
                "bucket_name": "container",
            },
            {
                "type": CONNECTION_STRING,
                "endpoint": CONNECTION_STRING,
                "bucket_name": "container",
            },
            {
                "type": "azure",
                "endpoint": f"{CONNECTION_STRING};invalid",
                "bucket_name": "container",
            },
        ],
    )
    def test_azure_validation_errors_do_not_echo_connection_string(
        self, client: TestClient, payload: dict[str, str]
    ) -> None:
        response = client.post(
            f"/v1/organizations/{ORGANIZATION_ID}/bucket-secrets", json=payload
        )

        assert response.status_code == 422
        assert "AccountKey" not in response.text
        assert "dGVzdC1vbmx5LWtleQ==" not in response.text

    @pytest.mark.parametrize(
        ("method", "suffix", "handler_method"),
        [
            ("post", "", "create_bucket_secret"),
            ("get", f"/{SECRET_ID}", "get_bucket_secret"),
            ("get", "", "get_organization_bucket_secrets"),
            ("patch", f"/{SECRET_ID}", "update_bucket_secret"),
        ],
    )
    def test_azure_responses_do_not_expose_credentials(
        self, client: TestClient, method: str, suffix: str, handler_method: str
    ) -> None:
        secret = {
            "id": str(SECRET_ID),
            "organization_id": str(ORGANIZATION_ID),
            "type": "azure",
            "endpoint": CONNECTION_STRING,
            "bucket_name": "container",
            "created_at": datetime.now(UTC).isoformat(),
        }
        result = (
            [secret] if handler_method == "get_organization_bucket_secrets" else secret
        )
        with patch(
            f"luml.handlers.bucket_secrets.BucketSecretHandler.{handler_method}",
            new=AsyncMock(return_value=result),
        ):
            response = client.request(
                method,
                f"/v1/organizations/{ORGANIZATION_ID}/bucket-secrets{suffix}",
                json={
                    "type": "azure",
                    "endpoint": CONNECTION_STRING,
                    "bucket_name": "container",
                },
            )

        assert response.status_code == 200
        body = response.json()
        if isinstance(body, list):
            body = body[0]
        assert body["endpoint"] == PUBLIC_ENDPOINT
        assert "AccountKey" not in response.text
        assert "connection_string" not in body

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
