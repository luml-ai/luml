from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid7

import pytest
from luml.infra.exceptions import DatabaseConstraintError
from luml.models import BucketSecretOrm, OrbitOrm
from luml.repositories.bucket_secrets import BucketSecretRepository

from tests.support.ids import ORGANIZATION_ID


class TestBucketSecretRepository:
    async def test_delete_used_secret_rejects_before_attempting_deletion(self) -> None:
        repository = BucketSecretRepository(Mock())
        secret = BucketSecretOrm(id=uuid7(), orbits=[OrbitOrm()])
        session = AsyncMock()
        session.__aenter__.return_value = session

        with (
            patch.object(repository, "_get_session", return_value=session),
            patch.object(
                repository,
                "get_model_where",
                new_callable=AsyncMock,
                return_value=secret,
            ),
            pytest.raises(DatabaseConstraintError),
        ):
            await repository.delete_bucket_secret(secret.id, ORGANIZATION_ID)

        session.delete.assert_not_awaited()
        session.commit.assert_not_awaited()
