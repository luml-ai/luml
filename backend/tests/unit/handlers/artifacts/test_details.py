from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from luml.handlers.artifacts import ArtifactHandler
from luml.infra.exceptions import (
    ArtifactNotFoundError,
    InvalidStatusTransitionError,
    NotFoundError,
    OrbitNotFoundError,
)
from luml.schemas.artifacts import (
    Artifact,
    ArtifactStatus,
    ArtifactType,
    ArtifactUpdate,
    ArtifactUpdateIn,
    Manifest,
)
from luml.schemas.bucket_secrets import S3BucketSecret
from luml.schemas.permissions import Action, Resource

from tests.support.ids import (
    ARTIFACT_ID,
    COLLECTION_ID,
    ORBIT_ID,
    ORGANIZATION_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks


class TestArtifactDetails:
    async def test_get_artifact_returns_details_with_artifact_tracks_attached(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        artifact = Mock(collection_id=COLLECTION_ID)
        mocks.repository.get_artifact_details.return_value = artifact
        tracks = [Mock()]
        mocks.track_repository.get_tracks_for_artifact.return_value = tracks
        check_access = AsyncMock(
            return_value=(
                Mock(id=ORBIT_ID, organization_id=ORGANIZATION_ID),
                Mock(id=COLLECTION_ID, orbit_id=ORBIT_ID),
            )
        )
        monkeypatch.setattr(
            mocks.handler, "_check_orbit_and_collection_access", check_access
        )

        result_artifact = await mocks.handler.get_artifact(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
        )

        assert result_artifact == artifact
        assert result_artifact.tracks == tracks
        mocks.track_repository.get_tracks_for_artifact.assert_awaited_once_with(
            ARTIFACT_ID
        )
        mocks.repository.get_artifact_details.assert_awaited_once_with(ARTIFACT_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.READ, ORBIT_ID
        )

    async def test_get_artifact_raises_not_found_when_artifact_is_missing(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mocks.repository.get_artifact_details.return_value = None
        check_access = AsyncMock(
            return_value=(
                Mock(id=ORBIT_ID, organization_id=ORGANIZATION_ID),
                Mock(id=COLLECTION_ID, orbit_id=ORBIT_ID),
            )
        )
        monkeypatch.setattr(
            mocks.handler, "_check_orbit_and_collection_access", check_access
        )

        with pytest.raises(NotFoundError) as error:
            await mocks.handler.get_artifact(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
            )

        assert error.value.status_code == 404
        mocks.repository.get_artifact_details.assert_awaited_once_with(ARTIFACT_ID)

    async def test_request_download_url_returns_storage_url(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        monkeypatch: pytest.MonkeyPatch,
        manifest: Manifest,
    ) -> None:
        artifact = Artifact(
            id=ARTIFACT_ID,
            collection_id=COLLECTION_ID,
            file_name="model.luml",
            name=None,
            extra_values={},
            manifest=manifest,
            file_hash="hash",
            file_index={},
            bucket_location="loc",
            size=1,
            unique_identifier="uid",
            status=ArtifactStatus.UPLOADED,
            created_at=datetime.now(),
            updated_at=None,
            type=ArtifactType.MODEL,
        )

        mocks.repository.get_artifact.return_value = artifact
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            bucket_secret_id=1, organization_id=ORGANIZATION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            id=COLLECTION_ID, orbit_id=ORBIT_ID
        )
        storage_client = AsyncMock()
        storage_client.get_download_url.return_value = "url"
        get_storage_client = AsyncMock(return_value=storage_client)
        monkeypatch.setattr(mocks.handler, "_get_storage_client", get_storage_client)

        url = await mocks.handler.request_download_url(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
        )

        assert url == "url"
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.READ, ORBIT_ID
        )
        get_storage_client.assert_awaited_once()
        storage_client.get_download_url.assert_awaited_once_with(
            artifact.bucket_location
        )

    async def test_request_download_url_raises_not_found_when_artifact_is_missing(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        check_access = AsyncMock(
            return_value=(Mock(id=ORBIT_ID), Mock(id=COLLECTION_ID))
        )
        monkeypatch.setattr(
            mocks.handler, "_check_orbit_and_collection_access", check_access
        )
        mocks.repository.get_artifact.return_value = None

        with pytest.raises(ArtifactNotFoundError):
            await mocks.handler.request_download_url(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
            )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.READ, ORBIT_ID
        )

    async def test_update_artifact_returns_updated_artifact(
        self, mocks: CollaboratorMocks[ArtifactHandler], manifest: Manifest
    ) -> None:
        artifact = Artifact(
            id=ARTIFACT_ID,
            collection_id=COLLECTION_ID,
            file_name="model.luml",
            name=None,
            extra_values={},
            manifest=manifest,
            file_hash="hash",
            file_index={},
            bucket_location="loc",
            size=1,
            unique_identifier="uid",
            status=ArtifactStatus.UPLOADED,
            created_at=datetime.now(),
            updated_at=None,
            type=ArtifactType.MODEL,
        )

        mocks.repository.get_artifact.return_value = artifact

        tags = ["t1", "t2"]
        expected = Artifact(
            id=ARTIFACT_ID,
            collection_id=COLLECTION_ID,
            file_name="model.luml",
            name=None,
            extra_values={},
            manifest=manifest,
            file_hash="hash",
            file_index={},
            bucket_location="loc",
            size=1,
            unique_identifier="uid",
            tags=tags,
            status=ArtifactStatus.UPLOADED,
            created_at=datetime.now(),
            updated_at=None,
            type=ArtifactType.MODEL,
        )

        mocks.repository.update_artifact.return_value = expected
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            bucket_secret_id=1, organization_id=ORGANIZATION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            id=COLLECTION_ID, orbit_id=ORBIT_ID
        )

        update_in = ArtifactUpdateIn(tags=tags)
        result = await mocks.handler.update_artifact(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID, update_in
        )

        assert result == expected
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.UPDATE, ORBIT_ID
        )
        expected_update = ArtifactUpdate(id=ARTIFACT_ID, name=None, tags=tags)
        mocks.repository.update_artifact.assert_awaited_once_with(
            ARTIFACT_ID,
            COLLECTION_ID,
            expected_update,
        )

    async def test_update_artifact_raises_not_found_when_artifact_is_missing(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        mocks.repository.update_artifact.return_value = None
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            bucket_secret_id=1, organization_id=ORGANIZATION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            id=COLLECTION_ID, orbit_id=ORBIT_ID
        )
        mocks.repository.get_artifact.return_value = None

        update_in = ArtifactUpdateIn(tags=["t1"])
        with pytest.raises(ArtifactNotFoundError):
            await mocks.handler.update_artifact(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                COLLECTION_ID,
                ARTIFACT_ID,
                update_in,
            )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.UPDATE, ORBIT_ID
        )
        mocks.repository.update_artifact.assert_not_awaited()

    async def test_update_artifact_raises_invalid_transition_when_status_is_not_allowed(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        monkeypatch: pytest.MonkeyPatch,
        manifest: Manifest,
    ) -> None:
        existing_artifact = Artifact(
            id=ARTIFACT_ID,
            collection_id=COLLECTION_ID,
            file_name="test.tar.gz",
            name="test",
            extra_values={},
            manifest=manifest,
            file_hash="hash",
            file_index={},
            bucket_location="test.tar.gz",
            size=100,
            unique_identifier="uid",
            tags=None,
            status=ArtifactStatus.UPLOADED,
            created_at=datetime.now(),
            updated_at=None,
            type=ArtifactType.MODEL,
        )

        check_access = AsyncMock(
            return_value=(Mock(id=ORBIT_ID), Mock(id=COLLECTION_ID))
        )
        monkeypatch.setattr(
            mocks.handler, "_check_orbit_and_collection_access", check_access
        )
        mocks.repository.get_artifact.return_value = existing_artifact

        with pytest.raises(InvalidStatusTransitionError):
            await mocks.handler.update_artifact(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                COLLECTION_ID,
                ARTIFACT_ID,
                ArtifactUpdateIn(status=ArtifactStatus.UPLOAD_FAILED),
            )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.UPDATE, ORBIT_ID
        )
        mocks.repository.update_artifact.assert_not_awaited()

    async def test_update_artifact_raises_not_found_when_update_finds_no_row(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        monkeypatch: pytest.MonkeyPatch,
        manifest: Manifest,
    ) -> None:
        existing_artifact = Artifact(
            id=ARTIFACT_ID,
            collection_id=COLLECTION_ID,
            file_name="test.tar.gz",
            name="test",
            extra_values={},
            manifest=manifest,
            file_hash="hash",
            file_index={},
            bucket_location="test.tar.gz",
            size=100,
            unique_identifier="uid",
            tags=None,
            status=ArtifactStatus.UPLOADED,
            created_at=datetime.now(),
            updated_at=None,
            type=ArtifactType.MODEL,
        )

        check_access = AsyncMock(
            return_value=(Mock(id=ORBIT_ID), Mock(id=COLLECTION_ID))
        )
        monkeypatch.setattr(
            mocks.handler, "_check_orbit_and_collection_access", check_access
        )
        mocks.repository.get_artifact.return_value = existing_artifact
        mocks.repository.update_artifact.return_value = None

        with pytest.raises(ArtifactNotFoundError):
            await mocks.handler.update_artifact(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                COLLECTION_ID,
                ARTIFACT_ID,
                ArtifactUpdateIn(tags=["new_tag"]),
            )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.UPDATE, ORBIT_ID
        )
        mocks.repository.update_artifact.assert_awaited_once()

    async def test_request_satellite_download_url_returns_storage_url(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        bucket_secret: S3BucketSecret,
    ) -> None:
        bucket_location = "orbit-123/collection-456/model.onnx"

        mocks.repository.get_artifact.return_value = Mock(
            id=ARTIFACT_ID,
            collection_id=COLLECTION_ID,
            bucket_location=bucket_location,
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            orbit_id=ORBIT_ID
        )
        mocks.orbit_repository.get_orbit_by_id.return_value = Mock(
            id=ORBIT_ID, bucket_secret_id=bucket_secret.id
        )
        mocks.secret_repository.get_bucket_secret.return_value = bucket_secret

        expected_url = "https://s3.example.com/download/url"

        storage_instance = AsyncMock()
        storage_instance.get_download_url.return_value = expected_url
        service_class = Mock(return_value=storage_instance)

        with patch(
            "luml.handlers.artifacts.create_storage_client",
            return_value=service_class,
        ):
            result = await mocks.handler.request_satellite_download_url(
                ORBIT_ID, ARTIFACT_ID
            )

        assert result == expected_url
        mocks.repository.get_artifact.assert_awaited_once_with(ARTIFACT_ID)
        mocks.collection_repository.get_collection.assert_awaited_once_with(
            COLLECTION_ID
        )
        mocks.orbit_repository.get_orbit_by_id.assert_awaited_once_with(ORBIT_ID)
        mocks.secret_repository.get_bucket_secret.assert_awaited_once_with(
            bucket_secret.id
        )
        storage_instance.get_download_url.assert_awaited_once_with(bucket_location)

    async def test_request_satellite_download_url_raises_when_artifact_is_missing(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        mocks.repository.get_artifact.return_value = None

        with pytest.raises(ArtifactNotFoundError) as error:
            await mocks.handler.request_satellite_download_url(ORBIT_ID, ARTIFACT_ID)

        assert error.value.status_code == 404
        mocks.repository.get_artifact.assert_awaited_once_with(ARTIFACT_ID)

    async def test_request_satellite_download_url_raises_when_collection_is_missing(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        mocks.repository.get_artifact.return_value = Mock(
            id=ARTIFACT_ID, collection_id=COLLECTION_ID
        )
        mocks.collection_repository.get_collection.return_value = None

        with pytest.raises(ArtifactNotFoundError) as error:
            await mocks.handler.request_satellite_download_url(ORBIT_ID, ARTIFACT_ID)

        assert error.value.status_code == 404
        mocks.repository.get_artifact.assert_awaited_once_with(ARTIFACT_ID)
        mocks.collection_repository.get_collection.assert_awaited_once_with(
            COLLECTION_ID
        )

    async def test_request_satellite_download_url_raises_when_orbit_is_missing(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        mocks.repository.get_artifact.return_value = Mock(
            id=ARTIFACT_ID, collection_id=COLLECTION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            id=COLLECTION_ID, orbit_id=ORBIT_ID
        )
        mocks.orbit_repository.get_orbit_by_id.return_value = None

        with pytest.raises(OrbitNotFoundError) as error:
            await mocks.handler.request_satellite_download_url(ORBIT_ID, ARTIFACT_ID)

        assert error.value.status_code == 404
        mocks.repository.get_artifact.assert_awaited_once_with(ARTIFACT_ID)
        mocks.collection_repository.get_collection.assert_awaited_once_with(
            COLLECTION_ID
        )
        mocks.orbit_repository.get_orbit_by_id.assert_awaited_once_with(ORBIT_ID)

    async def test_get_satellite_artifact_returns_artifact_with_download_url(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        bucket_secret: S3BucketSecret,
        manifest: Manifest,
    ) -> None:
        bucket_location = "test.tar.gz"

        artifact = Artifact(
            id=ARTIFACT_ID,
            collection_id=COLLECTION_ID,
            file_name="test.tar.gz",
            name="test",
            extra_values={},
            manifest=manifest,
            file_hash="hash",
            file_index={},
            bucket_location="test.tar.gz",
            size=100,
            unique_identifier="uid",
            tags=None,
            status=ArtifactStatus.UPLOADED,
            created_at=datetime.now(),
            updated_at=None,
            type=ArtifactType.MODEL,
        )

        mocks.repository.get_artifact.return_value = artifact
        mocks.collection_repository.get_collection.return_value = Mock(
            id=COLLECTION_ID, orbit_id=ORBIT_ID
        )
        mocks.orbit_repository.get_orbit_by_id.return_value = Mock(
            id=ORBIT_ID, bucket_secret_id=bucket_secret.id
        )
        mocks.secret_repository.get_bucket_secret.return_value = bucket_secret

        expected_url = "https://s3.example.com/download/url"
        storage_instance = Mock()
        storage_instance.get_download_url = AsyncMock(return_value=expected_url)
        service_class = Mock(return_value=storage_instance)

        with patch(
            "luml.handlers.artifacts.create_storage_client",
            return_value=service_class,
        ):
            result = await mocks.handler.get_satellite_artifact(ORBIT_ID, ARTIFACT_ID)

        assert result.artifact == artifact
        assert result.url == expected_url
        mocks.repository.get_artifact.assert_awaited_once_with(ARTIFACT_ID)
        mocks.collection_repository.get_collection.assert_awaited_once_with(
            COLLECTION_ID
        )
        mocks.orbit_repository.get_orbit_by_id.assert_awaited_once_with(ORBIT_ID)
        mocks.secret_repository.get_bucket_secret.assert_awaited_once_with(
            bucket_secret.id
        )
        storage_instance.get_download_url.assert_awaited_once_with(bucket_location)

    async def test_get_satellite_artifact_raises_not_found_when_artifact_is_missing(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        mocks.repository.get_artifact.return_value = None

        with pytest.raises(ArtifactNotFoundError) as error:
            await mocks.handler.get_satellite_artifact(ORBIT_ID, ARTIFACT_ID)

        assert error.value.status_code == 404
        mocks.repository.get_artifact.assert_awaited_once_with(ARTIFACT_ID)

    async def test_get_satellite_artifact_raises_orbit_not_found_when_orbit_is_missing(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        mocks.repository.get_artifact.return_value = Mock(
            id=ARTIFACT_ID, collection_id=COLLECTION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            id=COLLECTION_ID, orbit_id=ORBIT_ID
        )
        mocks.orbit_repository.get_orbit_by_id.return_value = None

        with pytest.raises(OrbitNotFoundError) as error:
            await mocks.handler.get_satellite_artifact(ORBIT_ID, ARTIFACT_ID)

        assert error.value.status_code == 404
        mocks.repository.get_artifact.assert_awaited_once_with(ARTIFACT_ID)
        mocks.orbit_repository.get_orbit_by_id.assert_awaited_once_with(ORBIT_ID)
