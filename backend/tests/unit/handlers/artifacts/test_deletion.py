from datetime import datetime
from unittest.mock import AsyncMock, Mock, call
from uuid import UUID, uuid7

import pytest
from luml.handlers.artifacts import ArtifactHandler
from luml.infra.exceptions import (
    ApplicationError,
    ArtifactDeployedError,
    ArtifactNotFoundError,
    ArtifactTrackedError,
    OrbitNotFoundError,
)
from luml.schemas.artifacts import (
    Artifact,
    ArtifactDetails,
    ArtifactStatus,
    ArtifactType,
    Manifest,
)
from luml.schemas.collections import Collection, CollectionType
from luml.schemas.deployment import Deployment, DeploymentStatus
from luml.schemas.permissions import Action, Resource

from tests.support.ids import (
    ARTIFACT_ID,
    COLLECTION_ID,
    DEPLOYMENT_ID,
    ORBIT_ID,
    ORGANIZATION_ID,
    SATELLITE_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks


class TestArtifactDeletion:
    async def test_request_delete_url_returns_url_and_marks_artifact_pending_deletion(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        monkeypatch: pytest.MonkeyPatch,
        manifest: Manifest,
    ) -> None:
        bucket_secret_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8621")

        now = datetime.now()

        artifact = ArtifactDetails(
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
            created_at=now,
            updated_at=None,
            deployments=None,
            type=ArtifactType.MODEL,
            collection=Collection(
                id=COLLECTION_ID,
                orbit_id=ORBIT_ID,
                name="Test Collection",
                description="Test Description",
                type=CollectionType.MODEL,
                tags=[],
                total_artifacts=1,
                created_at=now,
                updated_at=None,
            ),
        )

        mocks.repository.get_artifact.return_value = artifact
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            bucket_secret_id=bucket_secret_id, organization_id=ORGANIZATION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            id=COLLECTION_ID, orbit_id=ORBIT_ID
        )
        storage_client = AsyncMock()
        storage_client.get_delete_url.return_value = "url"
        get_storage_client = AsyncMock(return_value=storage_client)
        monkeypatch.setattr(mocks.handler, "_get_storage_client", get_storage_client)
        mocks.repository.request_deletion.return_value = artifact

        url = await mocks.handler.request_delete_url(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
        )

        assert url == "url"
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.DELETE, ORBIT_ID
        )
        mocks.repository.request_deletion.assert_awaited_once_with(
            ARTIFACT_ID, COLLECTION_ID
        )
        get_storage_client.assert_awaited_once()
        storage_client.get_delete_url.assert_awaited_once_with(artifact.bucket_location)

    async def test_request_delete_url_raises_conflict_when_artifact_is_deployed(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        monkeypatch: pytest.MonkeyPatch,
        manifest: Manifest,
    ) -> None:
        bucket_secret_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8621")

        now = datetime.now()

        artifact = ArtifactDetails(
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
            created_at=now,
            updated_at=None,
            type=ArtifactType.MODEL,
            deployments=[
                Deployment(
                    id=DEPLOYMENT_ID,
                    orbit_id=ORBIT_ID,
                    satellite_id=SATELLITE_ID,
                    satellite_name="Test Satellite",
                    name="deployment-1",
                    artifact_id=ARTIFACT_ID,
                    artifact_name="model",
                    collection_id=COLLECTION_ID,
                    status=DeploymentStatus.ACTIVE,
                    created_by_user="Test User",
                    created_at=now,
                    updated_at=None,
                )
            ],
            collection=Collection(
                id=COLLECTION_ID,
                orbit_id=ORBIT_ID,
                name="Test Collection",
                description="Test Description",
                type=CollectionType.MODEL,
                tags=[],
                total_artifacts=1,
                created_at=now,
                updated_at=None,
            ),
        )

        mocks.repository.get_artifact.return_value = artifact
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            bucket_secret_id=bucket_secret_id, organization_id=ORGANIZATION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            id=COLLECTION_ID, orbit_id=ORBIT_ID
        )
        storage_client = AsyncMock()
        storage_client.get_delete_url.return_value = "url"
        monkeypatch.setattr(
            mocks.handler,
            "_get_storage_client",
            AsyncMock(return_value=storage_client),
        )
        mocks.repository.request_deletion.side_effect = ArtifactDeployedError()

        with pytest.raises(ApplicationError) as error:
            await mocks.handler.request_delete_url(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
            )

        assert error.value.status_code == 409
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.ARTIFACT,
            Action.DELETE,
            ORBIT_ID,
        )
        mocks.repository.get_artifact.assert_awaited_once_with(ARTIFACT_ID)
        mocks.repository.request_deletion.assert_awaited_once_with(
            ARTIFACT_ID, COLLECTION_ID
        )

    async def test_request_delete_url_raises_not_found_when_artifact_is_missing(
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
            await mocks.handler.request_delete_url(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
            )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.DELETE, ORBIT_ID
        )

    async def test_request_delete_url_raises_orbit_not_found_when_orbit_is_missing(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        monkeypatch: pytest.MonkeyPatch,
        manifest: Manifest,
    ) -> None:
        now = datetime.now()

        artifact = ArtifactDetails(
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
            created_at=now,
            updated_at=None,
            deployments=None,
            type=ArtifactType.MODEL,
            collection=Collection(
                id=COLLECTION_ID,
                orbit_id=ORBIT_ID,
                name="Test Collection",
                description="Test Description",
                type=CollectionType.MODEL,
                tags=[],
                total_artifacts=1,
                created_at=now,
                updated_at=None,
            ),
        )

        check_access = AsyncMock(
            return_value=(Mock(id=ORBIT_ID), Mock(id=COLLECTION_ID))
        )
        monkeypatch.setattr(
            mocks.handler, "_check_orbit_and_collection_access", check_access
        )
        mocks.repository.get_artifact.return_value = artifact
        mocks.orbit_repository.get_orbit_simple.return_value = None

        with pytest.raises(OrbitNotFoundError):
            await mocks.handler.request_delete_url(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
            )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.DELETE, ORBIT_ID
        )

    async def test_request_delete_url_raises_conflict_when_artifact_is_tracked(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            mocks.handler,
            "_check_orbit_and_collection_access",
            AsyncMock(return_value=None),
        )
        artifact = Mock(
            id=ARTIFACT_ID, collection_id=COLLECTION_ID, bucket_location="loc"
        )
        mocks.repository.get_artifact.return_value = artifact
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            id=ORBIT_ID, bucket_secret_id=uuid7()
        )
        monkeypatch.setattr(
            mocks.handler,
            "_get_storage_client",
            AsyncMock(
                return_value=AsyncMock(get_delete_url=AsyncMock(return_value="url"))
            ),
        )
        mocks.repository.request_deletion.side_effect = ArtifactTrackedError()

        with pytest.raises(
            ApplicationError, match="referenced by one or more tracks"
        ) as exc:
            await mocks.handler.request_delete_url(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
            )
        assert exc.value.status_code == 409
        mocks.repository.request_deletion.assert_awaited_once_with(
            ARTIFACT_ID, COLLECTION_ID
        )

    async def test_request_delete_url_raises_not_found_when_artifact_is_gone_at_lock(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            mocks.handler,
            "_check_orbit_and_collection_access",
            AsyncMock(return_value=None),
        )
        mocks.repository.get_artifact.return_value = Mock(
            id=ARTIFACT_ID, collection_id=COLLECTION_ID, bucket_location="loc"
        )
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            id=ORBIT_ID, bucket_secret_id=uuid7()
        )
        monkeypatch.setattr(
            mocks.handler,
            "_get_storage_client",
            AsyncMock(
                return_value=AsyncMock(get_delete_url=AsyncMock(return_value="url"))
            ),
        )
        mocks.repository.request_deletion.return_value = None

        with pytest.raises(ArtifactNotFoundError):
            await mocks.handler.request_delete_url(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
            )

    async def test_confirm_deletion_deletes_artifact_and_lineage_node_when_pending(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        artifact = Mock(
            collection_id=COLLECTION_ID,
            status=ArtifactStatus.PENDING_DELETION,
            deployments=[],
        )

        mocks.track_entry_repository.has_entries_for_artifact.return_value = False
        mocks.repository.get_artifact_details.return_value = artifact
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            bucket_secret_id=1, organization_id=ORGANIZATION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            id=COLLECTION_ID, orbit_id=ORBIT_ID
        )

        await mocks.handler.confirm_deletion(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
        )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.DELETE, ORBIT_ID
        )
        mocks.repository.get_artifact_details.assert_awaited_once_with(ARTIFACT_ID)
        mocks.lineage_repository.refresh_node_copy.assert_awaited_once_with(
            ARTIFACT_ID, mocks.session
        )
        mocks.repository.delete_artifact.assert_awaited_once_with(
            ARTIFACT_ID, mocks.session
        )
        mocks.lineage_repository.delete_unreachable_deleted_nodes.assert_awaited_once_with(
            ORBIT_ID, mocks.session
        )

    async def test_confirm_deletion_raises_conflict_when_artifact_is_deployed(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        mocks.track_entry_repository.has_entries_for_artifact.return_value = False
        mocks.repository.get_artifact_details.return_value = Mock(
            collection_id=COLLECTION_ID,
            status=ArtifactStatus.PENDING_DELETION,
            deployments=[Mock()],
        )
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            organization_id=ORGANIZATION_ID,
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            orbit_id=ORBIT_ID
        )

        with pytest.raises(ArtifactDeployedError) as error:
            await mocks.handler.confirm_deletion(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                COLLECTION_ID,
                ARTIFACT_ID,
            )

        assert error.value.status_code == 409
        assert error.value.message == (
            "Cannot delete artifact because it is used in deployments."
        )
        mocks.track_entry_repository.has_entries_for_artifact.assert_awaited_once_with(
            ARTIFACT_ID
        )
        mocks.repository.delete_artifact.assert_not_awaited()

    async def test_confirm_deletion_raises_when_artifact_is_not_pending_deletion(
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

        mocks.track_entry_repository.has_entries_for_artifact.return_value = False
        mocks.repository.get_artifact_details.return_value = artifact
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            bucket_secret_id=1, organization_id=ORGANIZATION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            id=COLLECTION_ID, orbit_id=ORBIT_ID
        )

        with pytest.raises(ApplicationError):
            await mocks.handler.confirm_deletion(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                COLLECTION_ID,
                ARTIFACT_ID,
            )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.DELETE, ORBIT_ID
        )
        mocks.repository.get_artifact_details.assert_awaited_once_with(ARTIFACT_ID)
        mocks.repository.delete_artifact.assert_not_called()

    async def test_delete_artifact_updates_lineage_in_order(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        calls = Mock()
        calls.attach_mock(mocks.lineage_repository.lock_orbit, "lock")
        calls.attach_mock(mocks.lineage_repository.refresh_node_copy, "refresh")
        calls.attach_mock(mocks.repository.delete_artifact, "delete")
        calls.attach_mock(
            mocks.lineage_repository.delete_unreachable_deleted_nodes, "cleanup"
        )

        await mocks.handler._delete_artifact(ORBIT_ID, ARTIFACT_ID)

        assert calls.mock_calls == [
            call.lock(ORBIT_ID, mocks.session),
            call.refresh(ARTIFACT_ID, mocks.session),
            call.delete(ARTIFACT_ID, mocks.session),
            call.cleanup(ORBIT_ID, mocks.session),
        ]

    async def test_delete_artifact_skips_lineage_cleanup_when_artifact_delete_fails(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        mocks.repository.delete_artifact.side_effect = RuntimeError("delete failed")

        with pytest.raises(RuntimeError, match="delete failed"):
            await mocks.handler._delete_artifact(uuid7(), ARTIFACT_ID)

        mocks.lineage_repository.refresh_node_copy.assert_awaited_once_with(
            ARTIFACT_ID, mocks.session
        )
        mocks.repository.delete_artifact.assert_awaited_once_with(
            ARTIFACT_ID, mocks.session
        )
        mocks.lineage_repository.delete_unreachable_deleted_nodes.assert_not_awaited()

    async def test_delete_artifact_rolls_back_deletion_when_lineage_cleanup_fails(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        mocks.lineage_repository.delete_unreachable_deleted_nodes.side_effect = (
            RuntimeError("cleanup failed")
        )

        with pytest.raises(RuntimeError, match="cleanup failed"):
            await mocks.handler._delete_artifact(ORBIT_ID, ARTIFACT_ID)

        mocks.repository.delete_artifact.assert_awaited_once_with(
            ARTIFACT_ID, mocks.session
        )
        mocks.lineage_repository.delete_unreachable_deleted_nodes.assert_awaited_once_with(
            ORBIT_ID, mocks.session
        )
        assert [type(error) for error in mocks.transaction_errors] == [RuntimeError]

    async def test_artifact_deletion_checks_raises_not_found_when_artifact_is_missing(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        mocks.repository.get_artifact_details.return_value = None
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            id=ORBIT_ID, organization_id=ORGANIZATION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            id=COLLECTION_ID, orbit_id=ORBIT_ID
        )

        with pytest.raises(ArtifactNotFoundError) as error:
            await mocks.handler._artifact_deletion_checks(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
            )

        assert error.value.status_code == 404
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.DELETE, ORBIT_ID
        )
        mocks.repository.get_artifact_details.assert_awaited_once_with(ARTIFACT_ID)

    async def test_force_delete_artifact_deletes_artifact_when_not_deployed(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        mocks.track_entry_repository.has_entries_for_artifact.return_value = False
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            id=ORBIT_ID, organization_id=ORGANIZATION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            id=COLLECTION_ID, orbit_id=ORBIT_ID
        )
        mocks.repository.get_artifact_details.return_value = Mock(
            id=ARTIFACT_ID, collection_id=COLLECTION_ID, deployments=None
        )

        await mocks.handler.force_delete_artifact(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
        )
        mocks.lineage_repository.refresh_node_copy.assert_awaited_once_with(
            ARTIFACT_ID, mocks.session
        )
        mocks.repository.delete_artifact.assert_awaited_once_with(
            ARTIFACT_ID, mocks.session
        )
        mocks.lineage_repository.delete_unreachable_deleted_nodes.assert_awaited_once_with(
            ORBIT_ID, mocks.session
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.DELETE, ORBIT_ID
        )

    async def test_force_delete_artifact_deletes_deployments_and_artifact_when_deployed(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        mocks.track_entry_repository.has_entries_for_artifact.return_value = False
        mocks.orbit_repository.get_orbit_simple.return_value = Mock(
            id=ORBIT_ID, organization_id=ORGANIZATION_ID
        )
        mocks.collection_repository.get_collection.return_value = Mock(
            id=COLLECTION_ID, orbit_id=ORBIT_ID
        )
        mocks.repository.get_artifact_details.return_value = Mock(
            id=ARTIFACT_ID,
            collection_id=COLLECTION_ID,
            deployments=[Mock(id=DEPLOYMENT_ID)],
        )

        await mocks.handler.force_delete_artifact(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID, ARTIFACT_ID
        )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.DELETE, ORBIT_ID
        )
        mocks.deployment_repository.delete_deployments_by_artifact_id.assert_awaited_once_with(
            ARTIFACT_ID
        )
        mocks.lineage_repository.refresh_node_copy.assert_awaited_once_with(
            ARTIFACT_ID, mocks.session
        )
        mocks.repository.delete_artifact.assert_awaited_once_with(
            ARTIFACT_ID, mocks.session
        )
        mocks.lineage_repository.delete_unreachable_deleted_nodes.assert_awaited_once_with(
            ORBIT_ID, mocks.session
        )
