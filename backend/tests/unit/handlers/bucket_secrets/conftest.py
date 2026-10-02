import datetime
from uuid import UUID

import pytest
from luml.handlers.bucket_secrets import BucketSecretHandler
from luml.schemas.bucket_secrets import S3BucketSecret

from tests.support.ids import ORGANIZATION_ID, OTHER_ORGANIZATION_ID
from tests.support.mocks import CollaboratorMocks, mock_collaborators

SECRET_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")
FOREIGN_SECRET_ID = UUID("0199c337-0aa2-7b44-9d21-7e5b3c8f0a12")


@pytest.fixture
def mocks() -> CollaboratorMocks[BucketSecretHandler]:
    return mock_collaborators(BucketSecretHandler())


def _owner_s3_secret() -> S3BucketSecret:
    return S3BucketSecret(
        id=FOREIGN_SECRET_ID,
        organization_id=OTHER_ORGANIZATION_ID,
        endpoint="owner.s3.amazonaws.com",
        bucket_name="owner-bucket",
        access_key="owner-access-key",
        secret_key="owner-secret-key",
        region="eu-west-1",
        created_at=datetime.datetime.now(),
        updated_at=None,
    )


async def _scoped_get_bucket_secret(
    secret_id: UUID, organization_id: UUID | None = None
) -> S3BucketSecret | None:
    stored = {
        FOREIGN_SECRET_ID: _owner_s3_secret(),
        SECRET_ID: _owner_s3_secret().model_copy(
            update={
                "id": SECRET_ID,
                "organization_id": ORGANIZATION_ID,
            }
        ),
    }
    secret = stored.get(secret_id)
    if not secret:
        return None
    if organization_id is not None and secret.organization_id != organization_id:
        return None
    return secret
