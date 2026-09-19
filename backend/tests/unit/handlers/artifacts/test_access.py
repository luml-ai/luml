from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid7

import pytest
from luml.handlers.artifacts import ArtifactHandler
from luml.infra.exceptions import (
    ArtifactNotFoundError,
    CollectionNotFoundError,
    OrbitNotFoundError,
)
from luml.schemas.artifacts import ArtifactStatus, ArtifactUpdateIn, Manifest

from tests.support.ids import (
    ARTIFACT_ID,
    COLLECTION_ID,
    ORBIT_ID,
    ORGANIZATION_ID,
    OTHER_ORBIT_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.artifacts.conftest import _make_artifact


class TestArtifactAccess:
    async def test_check_orbit_and_collection_access_returns_orbit_and_collection(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        orbit = Mock(organization_id=ORGANIZATION_ID)
        collection = Mock(orbit_id=ORBIT_ID)

        mocks.orbit_repository.get_orbit_simple.return_value = orbit
        mocks.collection_repository.get_collection.return_value = collection

        result = await mocks.handler._check_orbit_and_collection_access(
            ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID
        )

        assert result == (orbit, collection)
        mocks.orbit_repository.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.collection_repository.get_collection.assert_awaited_once_with(
            COLLECTION_ID
        )

    async def test_check_orbit_and_collection_access_raises_when_orbit_is_missing(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        mocks.orbit_repository.get_orbit_simple.return_value = None

        with pytest.raises(OrbitNotFoundError) as error:
            await mocks.handler._check_orbit_and_collection_access(
                ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID
            )

        assert error.value.status_code == 404
        mocks.orbit_repository.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )

    async def test_check_orbit_and_collection_access_raises_when_collection_is_missing(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        orbit = Mock(organization_id=ORGANIZATION_ID)

        mocks.orbit_repository.get_orbit_simple.return_value = orbit
        mocks.collection_repository.get_collection.return_value = None

        with pytest.raises(CollectionNotFoundError) as error:
            await mocks.handler._check_orbit_and_collection_access(
                ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID
            )

        assert error.value.status_code == 404
        mocks.orbit_repository.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.collection_repository.get_collection.assert_awaited_once_with(
            COLLECTION_ID
        )

    async def test_check_orbit_and_collections_access_returns_orbit_when_all_accessible(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        second_collection_id = UUID("0199c337-09f5-7a01-9f5f-5f68db62cf71")
        collection_ids = [COLLECTION_ID, second_collection_id]

        orbit = Mock(organization_id=ORGANIZATION_ID)
        mocks.orbit_repository.get_orbit_simple.return_value = orbit
        mocks.collection_repository.get_collections_by_ids.return_value = [
            Mock(id=collection_ids[0]),
            Mock(id=collection_ids[1]),
        ]

        result = await mocks.handler._check_orbit_and_collections_access(
            ORGANIZATION_ID, ORBIT_ID, collection_ids
        )

        assert result == orbit
        mocks.collection_repository.get_collections_by_ids.assert_awaited_once_with(
            collection_ids, orbit_id=ORBIT_ID
        )

    async def test_check_orbit_and_collections_access_reports_only_missing_collections(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        outside_collection_id = UUID("0199c337-09f5-7a01-9f5f-5f68db62cf71")

        orbit = Mock(organization_id=ORGANIZATION_ID)
        mocks.orbit_repository.get_orbit_simple.return_value = orbit
        mocks.collection_repository.get_collections_by_ids.return_value = [
            Mock(id=COLLECTION_ID)
        ]

        with pytest.raises(CollectionNotFoundError) as error:
            await mocks.handler._check_orbit_and_collections_access(
                ORGANIZATION_ID, ORBIT_ID, [COLLECTION_ID, outside_collection_id]
            )

        assert error.value.status_code == 404
        assert str(outside_collection_id) in str(error.value)
        assert str(COLLECTION_ID) not in str(error.value)

    async def test_check_orbit_and_collections_access_skips_lookup_when_ids_are_absent(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        orbit = Mock(organization_id=ORGANIZATION_ID)
        mocks.orbit_repository.get_orbit_simple.return_value = orbit

        result = await mocks.handler._check_orbit_and_collections_access(
            ORGANIZATION_ID, ORBIT_ID, None
        )

        assert result == orbit
        mocks.collection_repository.get_collections_by_ids.assert_not_awaited()

    async def test_check_orbit_and_collections_access_raises_when_orbit_is_missing(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        mocks.orbit_repository.get_orbit_simple.return_value = None

        with pytest.raises(OrbitNotFoundError) as error:
            await mocks.handler._check_orbit_and_collections_access(
                ORGANIZATION_ID, ORBIT_ID, [uuid7()]
            )

        assert error.value.status_code == 404

    async def test_request_download_url_rejects_artifact_from_another_collection(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        foreign_collection_id = UUID("0199c337-09f5-7c3d-8a11-4e2b9d7c6f01")
        monkeypatch.setattr(
            mocks.handler,
            "_check_orbit_and_collection_access",
            AsyncMock(return_value=(Mock(id=ORBIT_ID), Mock(id=COLLECTION_ID))),
        )
        get_storage_client = AsyncMock()
        monkeypatch.setattr(mocks.handler, "_get_storage_client", get_storage_client)
        mocks.repository.get_artifact.return_value = Mock(
            id=ARTIFACT_ID,
            collection_id=foreign_collection_id,
            bucket_location="foreign/loc",
        )

        with pytest.raises(ArtifactNotFoundError) as error:
            await mocks.handler.request_download_url(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
            )

        assert error.value.status_code == 404
        get_storage_client.assert_not_awaited()

    async def test_request_delete_url_rejects_artifact_from_another_collection(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        foreign_collection_id = UUID("0199c337-09f5-7c3d-8a11-4e2b9d7c6f01")
        monkeypatch.setattr(
            mocks.handler,
            "_check_orbit_and_collection_access",
            AsyncMock(return_value=(Mock(id=ORBIT_ID), Mock(id=COLLECTION_ID))),
        )
        get_storage_client = AsyncMock()
        monkeypatch.setattr(mocks.handler, "_get_storage_client", get_storage_client)
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            id=ORBIT_ID, bucket_secret_id=uuid7()
        )
        mocks.repository.get_artifact.return_value = Mock(
            id=ARTIFACT_ID,
            collection_id=foreign_collection_id,
            bucket_location="foreign/loc",
            deployments=None,
        )

        with pytest.raises(ArtifactNotFoundError) as error:
            await mocks.handler.request_delete_url(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
            )

        assert error.value.status_code == 404
        get_storage_client.assert_not_awaited()
        mocks.repository.request_deletion.assert_not_awaited()

    async def test_update_artifact_rejects_foreign_artifact_before_status_check(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        foreign_collection_id = UUID("0199c337-09f5-7c3d-8a11-4e2b9d7c6f01")
        monkeypatch.setattr(
            mocks.handler,
            "_check_orbit_and_collection_access",
            AsyncMock(return_value=(Mock(id=ORBIT_ID), Mock(id=COLLECTION_ID))),
        )
        mocks.repository.get_artifact.return_value = Mock(
            id=ARTIFACT_ID,
            collection_id=foreign_collection_id,
            status=ArtifactStatus.UPLOADED,
        )

        with pytest.raises(ArtifactNotFoundError) as error:
            await mocks.handler.update_artifact(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                COLLECTION_ID,
                ARTIFACT_ID,
                ArtifactUpdateIn(status=ArtifactStatus.UPLOADED),
            )

        assert error.value.status_code == 404
        mocks.repository.update_artifact.assert_not_awaited()

    async def test_artifact_deletion_checks_rejects_artifact_from_another_collection(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        foreign_collection_id = UUID("0199c337-09f5-7c3d-8a11-4e2b9d7c6f01")
        monkeypatch.setattr(
            mocks.handler,
            "_check_orbit_and_collection_access",
            AsyncMock(return_value=(Mock(id=ORBIT_ID), Mock(id=COLLECTION_ID))),
        )
        mocks.track_entry_repository.has_entries_for_artifact.return_value = False
        mocks.repository.get_artifact_details.return_value = Mock(
            id=ARTIFACT_ID, collection_id=foreign_collection_id, deployments=None
        )

        with pytest.raises(ArtifactNotFoundError) as error:
            await mocks.handler._artifact_deletion_checks(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
            )

        assert error.value.status_code == 404
        mocks.track_entry_repository.has_entries_for_artifact.assert_not_awaited()

    async def test_force_delete_artifact_rejects_artifact_from_another_collection(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        foreign_collection_id = UUID("0199c337-09f5-7c3d-8a11-4e2b9d7c6f01")
        monkeypatch.setattr(
            mocks.handler,
            "_check_orbit_and_collection_access",
            AsyncMock(return_value=(Mock(id=ORBIT_ID), Mock(id=COLLECTION_ID))),
        )
        mocks.track_entry_repository.has_entries_for_artifact.return_value = False
        mocks.repository.get_artifact_details.return_value = Mock(
            id=ARTIFACT_ID,
            collection_id=foreign_collection_id,
            deployments=[Mock(id=uuid7())],
        )

        with pytest.raises(ArtifactNotFoundError) as error:
            await mocks.handler.force_delete_artifact(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
            )

        assert error.value.status_code == 404
        mocks.repository.delete_artifact.assert_not_awaited()

    async def test_get_satellite_artifact_rejects_artifact_outside_orbit(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        monkeypatch: pytest.MonkeyPatch,
        manifest: Manifest,
    ) -> None:
        foreign_collection_id = UUID("0199c337-09f5-7c3d-8a11-4e2b9d7c6f01")
        get_storage_client = AsyncMock()
        get_storage_client.return_value.get_download_url.return_value = "url"
        monkeypatch.setattr(mocks.handler, "_get_storage_client", get_storage_client)
        mocks.repository.get_artifact.return_value = _make_artifact(
            manifest, foreign_collection_id
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            id=foreign_collection_id, orbit_id=OTHER_ORBIT_ID
        )
        mocks.orbit_repository.get_orbit_by_id.return_value = Mock(
            id=ORBIT_ID, bucket_secret_id=uuid7()
        )

        with pytest.raises(ArtifactNotFoundError) as error:
            await mocks.handler.get_satellite_artifact(ORBIT_ID, ARTIFACT_ID)

        assert error.value.status_code == 404
        mocks.collection_repository.get_collection.assert_awaited_once_with(
            foreign_collection_id
        )
        mocks.orbit_repository.get_orbit_by_id.assert_not_awaited()
        get_storage_client.assert_not_awaited()

    async def test_get_satellite_artifact_raises_not_found_when_collection_is_missing(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        monkeypatch: pytest.MonkeyPatch,
        manifest: Manifest,
    ) -> None:
        foreign_collection_id = UUID("0199c337-09f5-7c3d-8a11-4e2b9d7c6f01")
        get_storage_client = AsyncMock()
        get_storage_client.return_value.get_download_url.return_value = "url"
        monkeypatch.setattr(mocks.handler, "_get_storage_client", get_storage_client)
        mocks.repository.get_artifact.return_value = _make_artifact(
            manifest, foreign_collection_id
        )
        mocks.collection_repository.get_collection.return_value = None
        mocks.orbit_repository.get_orbit_by_id.return_value = Mock(
            id=ORBIT_ID, bucket_secret_id=uuid7()
        )

        with pytest.raises(ArtifactNotFoundError) as error:
            await mocks.handler.get_satellite_artifact(ORBIT_ID, ARTIFACT_ID)

        assert error.value.status_code == 404
        get_storage_client.assert_not_awaited()
