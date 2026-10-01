from unittest.mock import AsyncMock, Mock, call
from uuid import UUID, uuid7

import pytest
from luml.handlers.artifacts import ArtifactHandler
from luml.infra.exceptions import (
    BucketConnectionError,
    BucketSecretNotFoundError,
    CollectionNotFoundError,
    DatabaseConstraintError,
    InsufficientPermissionsError,
    OrbitNotFoundError,
)
from luml.repositories.artifacts import ArtifactDeletionRecord
from luml.schemas.artifacts import (
    Artifact,
    ArtifactDeleteDeployment,
    ArtifactDeleteReason,
    ArtifactDeleteTrack,
    ArtifactStatus,
)
from luml.schemas.deployment import DeploymentStatus
from luml.schemas.permissions import Action, Resource

from tests.support.ids import COLLECTION_ID, ORBIT_ID, ORGANIZATION_ID, USER_ID
from tests.support.mocks import CollaboratorMocks


def _record(
    artifact_id: UUID,
    *,
    name: str | None,
    file_name: str | None = None,
    status: ArtifactStatus = ArtifactStatus.UPLOADED,
    deployments: list[ArtifactDeleteDeployment] | None = None,
    tracks: list[ArtifactDeleteTrack] | None = None,
) -> ArtifactDeletionRecord:
    artifact = Artifact.model_construct(
        id=artifact_id,
        name=name,
        file_name=file_name or f"{name}.luml",
        bucket_location=f"objects/{artifact_id}",
        status=status,
    )
    return ArtifactDeletionRecord(
        artifact=artifact,
        deployments=deployments or [],
        tracks=tracks or [],
    )


class TestArtifactBatchDeletion:
    @pytest.fixture
    def storage_client(self) -> Mock:
        return Mock(get_delete_url=AsyncMock())

    @pytest.fixture
    def check_access(self) -> AsyncMock:
        return AsyncMock(return_value=(Mock(bucket_secret_id=uuid7()), Mock()))

    @pytest.fixture
    def get_storage_client(self, storage_client: Mock) -> AsyncMock:
        return AsyncMock(return_value=storage_client)

    @pytest.fixture(autouse=True)
    def stubbed_handler(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        monkeypatch: pytest.MonkeyPatch,
        check_access: AsyncMock,
        get_storage_client: AsyncMock,
    ) -> None:
        mocks.repository.request_batch_deletion.return_value = []
        mocks.repository.get_batch_deletion_records.return_value = []
        mocks.repository.delete_artifact_record.return_value = True
        monkeypatch.setattr(
            mocks.handler, "_check_orbit_and_collection_access", check_access
        )
        monkeypatch.setattr(mocks.handler, "_get_storage_client", get_storage_client)

    async def test_request_delete_urls_accepts_every_status_and_collapses_duplicates(
        self, mocks: CollaboratorMocks[ArtifactHandler], storage_client: Mock
    ) -> None:
        records = [
            _record(uuid7(), name=artifact_status.value, status=artifact_status)
            for artifact_status in ArtifactStatus
        ]
        mocks.repository.request_batch_deletion.return_value = records
        storage_client.get_delete_url.side_effect = [
            f"https://bucket/{record.artifact.id}" for record in records
        ]
        requested_ids = [record.artifact.id for record in records]

        result = await mocks.handler.request_delete_urls(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            COLLECTION_ID,
            [*requested_ids, requested_ids[0], requested_ids[0]],
        )

        assert [entry.artifact_id for entry in result.urls] == requested_ids
        assert result.failed == []
        mocks.repository.request_batch_deletion.assert_awaited_once_with(
            COLLECTION_ID, requested_ids
        )
        assert storage_client.get_delete_url.await_args_list == [
            call(record.artifact.bucket_location) for record in records
        ]
        mocks.repository.mark_deletion_failed.assert_not_awaited()

    async def test_request_delete_urls_classifies_mixed_selection_by_precedence(
        self, mocks: CollaboratorMocks[ArtifactHandler], storage_client: Mock
    ) -> None:
        eligible_id = uuid7()
        deployment_id = uuid7()
        tracked_id = uuid7()
        both_id = uuid7()
        foreign_id = uuid7()
        unknown_id = uuid7()
        deployment = ArtifactDeleteDeployment(
            id=uuid7(),
            name="failed deployment",
            status=DeploymentStatus.FAILED,
        )
        active_deployment = ArtifactDeleteDeployment(
            id=uuid7(),
            name="active deployment",
            status=DeploymentStatus.ACTIVE,
        )
        tracks = [
            ArtifactDeleteTrack(id=uuid7(), name="release"),
            ArtifactDeleteTrack(id=uuid7(), name="latest"),
        ]
        records = [
            _record(eligible_id, name="eligible"),
            _record(deployment_id, name="deployed", deployments=[deployment]),
            _record(tracked_id, name="tracked", tracks=tracks),
            _record(
                both_id,
                name="both",
                deployments=[active_deployment],
                tracks=tracks,
            ),
        ]
        mocks.repository.request_batch_deletion.return_value = records
        storage_client.get_delete_url.return_value = "https://bucket/delete"

        result = await mocks.handler.request_delete_urls(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            COLLECTION_ID,
            [
                eligible_id,
                deployment_id,
                tracked_id,
                both_id,
                foreign_id,
                unknown_id,
            ],
        )

        assert [entry.artifact_id for entry in result.urls] == [eligible_id]
        assert [entry.reason for entry in result.failed] == [
            ArtifactDeleteReason.DEPLOYMENTS,
            ArtifactDeleteReason.TRACKS,
            ArtifactDeleteReason.DEPLOYMENTS,
            ArtifactDeleteReason.NOT_FOUND,
            ArtifactDeleteReason.NOT_FOUND,
        ]
        assert result.failed[0].deployments == [deployment]
        assert result.failed[1].tracks == tracks
        assert result.failed[2].deployments == [active_deployment]
        assert result.failed[2].tracks == []
        assert result.failed[3].name is None
        assert result.failed[4].name is None
        mocks.repository.delete_artifact_record.assert_not_awaited()

    async def test_request_delete_urls_marks_only_signing_failures_as_failed(
        self, mocks: CollaboratorMocks[ArtifactHandler], storage_client: Mock
    ) -> None:
        first = _record(uuid7(), name="first")
        second = _record(uuid7(), name="second")
        mocks.repository.request_batch_deletion.return_value = [first, second]

        async def sign_delete_url(bucket_location: str) -> str:
            if bucket_location == second.artifact.bucket_location:
                raise BucketConnectionError("cannot sign")
            return "https://bucket/delete"

        storage_client.get_delete_url.side_effect = sign_delete_url

        result = await mocks.handler.request_delete_urls(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            COLLECTION_ID,
            [first.artifact.id, second.artifact.id],
        )

        assert [entry.artifact_id for entry in result.urls] == [first.artifact.id]
        assert len(result.failed) == 1
        assert result.failed[0].artifact_id == second.artifact.id
        assert result.failed[0].name == "second"
        assert result.failed[0].reason == ArtifactDeleteReason.STORAGE_ERROR
        mocks.repository.mark_deletion_failed.assert_awaited_once_with(
            COLLECTION_ID, [second.artifact.id]
        )

    async def test_request_delete_urls_propagates_unexpected_signing_errors(
        self, mocks: CollaboratorMocks[ArtifactHandler], storage_client: Mock
    ) -> None:
        record = _record(uuid7(), name="first")
        mocks.repository.request_batch_deletion.return_value = [record]
        storage_client.get_delete_url.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await mocks.handler.request_delete_urls(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                COLLECTION_ID,
                [record.artifact.id],
            )

        mocks.repository.mark_deletion_failed.assert_not_awaited()

    async def test_deletion_results_name_artifact_by_file_name_when_name_is_missing(
        self, mocks: CollaboratorMocks[ArtifactHandler], storage_client: Mock
    ) -> None:
        eligible = _record(uuid7(), name=None, file_name="eligible.luml")
        deployed = _record(
            uuid7(),
            name=None,
            file_name="deployed.luml",
            deployments=[
                ArtifactDeleteDeployment(
                    id=uuid7(), name="deployment", status=DeploymentStatus.ACTIVE
                )
            ],
        )
        mocks.repository.request_batch_deletion.return_value = [eligible, deployed]
        storage_client.get_delete_url.return_value = "https://bucket/delete"

        requested = await mocks.handler.request_delete_urls(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            COLLECTION_ID,
            [eligible.artifact.id, deployed.artifact.id],
        )

        assert [entry.name for entry in requested.urls] == ["eligible.luml"]
        assert [entry.name for entry in requested.failed] == ["deployed.luml"]

        mocks.repository.get_batch_deletion_records.return_value = [eligible]
        confirmed = await mocks.handler.confirm_deletions(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            COLLECTION_ID,
            [eligible.artifact.id],
        )

        assert [entry.reason for entry in confirmed.failed] == [
            ArtifactDeleteReason.NOT_PENDING_DELETION
        ]
        assert [entry.name for entry in confirmed.failed] == ["eligible.luml"]

    @pytest.mark.parametrize(
        ("failure", "failing_mock"),
        [
            (InsufficientPermissionsError(), "permissions"),
            (OrbitNotFoundError(), "access"),
            (CollectionNotFoundError(), "access"),
            (BucketSecretNotFoundError(), "storage"),
        ],
    )
    async def test_request_delete_urls_changes_nothing_when_request_check_fails(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        failure: Exception,
        failing_mock: str,
        check_access: AsyncMock,
        get_storage_client: AsyncMock,
    ) -> None:
        if failing_mock == "permissions":
            mocks.permissions_handler.check_permissions.side_effect = failure
        elif failing_mock == "access":
            check_access.side_effect = failure
        else:
            get_storage_client.side_effect = failure

        with pytest.raises(type(failure)):
            await mocks.handler.request_delete_urls(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                COLLECTION_ID,
                [uuid7()],
            )

        mocks.repository.request_batch_deletion.assert_not_awaited()
        mocks.repository.mark_deletion_failed.assert_not_awaited()

    async def test_confirm_deletions_deletes_only_pending_artifacts_without_force(
        self, mocks: CollaboratorMocks[ArtifactHandler], get_storage_client: AsyncMock
    ) -> None:
        deletable = _record(
            uuid7(), name="deletable", status=ArtifactStatus.PENDING_DELETION
        )
        uploaded = _record(uuid7(), name="uploaded")
        deployed = _record(
            uuid7(),
            name="deployed",
            status=ArtifactStatus.PENDING_DELETION,
            deployments=[
                ArtifactDeleteDeployment(
                    id=uuid7(),
                    name="deployment",
                    status=DeploymentStatus.DELETION_FAILED,
                )
            ],
        )
        tracked = _record(
            uuid7(),
            name="tracked",
            status=ArtifactStatus.PENDING_DELETION,
            tracks=[ArtifactDeleteTrack(id=uuid7(), name="track")],
        )
        unknown_id = uuid7()
        records = [deletable, uploaded, deployed, tracked]
        mocks.repository.get_batch_deletion_records.return_value = records

        result = await mocks.handler.confirm_deletions(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            COLLECTION_ID,
            [
                deletable.artifact.id,
                uploaded.artifact.id,
                deployed.artifact.id,
                tracked.artifact.id,
                unknown_id,
                deletable.artifact.id,
            ],
        )

        assert result.deleted == [deletable.artifact.id]
        assert [entry.reason for entry in result.failed] == [
            ArtifactDeleteReason.NOT_PENDING_DELETION,
            ArtifactDeleteReason.DEPLOYMENTS,
            ArtifactDeleteReason.TRACKS,
            ArtifactDeleteReason.NOT_FOUND,
        ]
        mocks.repository.delete_artifact_record.assert_awaited_once_with(
            deletable.artifact.id, COLLECTION_ID
        )
        get_storage_client.assert_not_awaited()

    async def test_confirm_deletions_deletes_every_pending_artifact(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        records = [
            _record(
                uuid7(),
                name=f"artifact-{index}",
                status=ArtifactStatus.PENDING_DELETION,
            )
            for index in range(3)
        ]
        mocks.repository.get_batch_deletion_records.return_value = records
        artifact_ids = [record.artifact.id for record in records]

        result = await mocks.handler.confirm_deletions(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            COLLECTION_ID,
            artifact_ids,
        )

        assert result.deleted == artifact_ids
        assert result.failed == []
        assert mocks.repository.delete_artifact_record.await_args_list == [
            call(artifact_id, COLLECTION_ID) for artifact_id in artifact_ids
        ]

    async def test_confirm_deletions_with_force_deletes_every_status_without_storage(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        get_storage_client: AsyncMock,
        storage_client: Mock,
    ) -> None:
        records = [
            _record(uuid7(), name=artifact_status.value, status=artifact_status)
            for artifact_status in ArtifactStatus
        ]
        mocks.repository.get_batch_deletion_records.return_value = records
        ids = [record.artifact.id for record in records]

        result = await mocks.handler.confirm_deletions(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            COLLECTION_ID,
            ids,
            force=True,
        )

        assert result.deleted == ids
        assert result.failed == []
        assert mocks.repository.delete_artifact_record.await_args_list == [
            call(artifact_id, COLLECTION_ID) for artifact_id in ids
        ]
        get_storage_client.assert_not_awaited()
        storage_client.get_delete_url.assert_not_awaited()

    async def test_confirm_deletions_with_force_reports_references_and_unknown_ids(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        deployed = _record(
            uuid7(),
            name="deployed",
            status=ArtifactStatus.DELETION_FAILED,
            deployments=[
                ArtifactDeleteDeployment(
                    id=uuid7(),
                    name="deployment",
                    status=DeploymentStatus.FAILED,
                )
            ],
        )
        tracked = _record(
            uuid7(),
            name="tracked",
            status=ArtifactStatus.DELETION_FAILED,
            tracks=[ArtifactDeleteTrack(id=uuid7(), name="track")],
        )
        unknown_id = uuid7()
        mocks.repository.get_batch_deletion_records.return_value = [
            deployed,
            tracked,
        ]

        result = await mocks.handler.confirm_deletions(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            COLLECTION_ID,
            [deployed.artifact.id, tracked.artifact.id, unknown_id],
            force=True,
        )

        assert result.deleted == []
        assert [entry.reason for entry in result.failed] == [
            ArtifactDeleteReason.DEPLOYMENTS,
            ArtifactDeleteReason.TRACKS,
            ArtifactDeleteReason.NOT_FOUND,
        ]
        assert result.failed[0].deployments == deployed.deployments
        assert result.failed[0].tracks == []
        assert result.failed[1].deployments == []
        assert result.failed[1].tracks == tracked.tracks
        assert result.failed[2].name is None
        mocks.repository.delete_artifact_record.assert_not_awaited()

    @pytest.mark.parametrize("race_reason", ["deployments", "tracks"])
    async def test_confirm_deletions_reports_current_reference_after_constraint_race(
        self, mocks: CollaboratorMocks[ArtifactHandler], race_reason: str
    ) -> None:
        artifact_id = uuid7()
        initial = _record(
            artifact_id,
            name="artifact",
            status=ArtifactStatus.PENDING_DELETION,
        )
        deployment = ArtifactDeleteDeployment(
            id=uuid7(),
            name="deployment",
            status=DeploymentStatus.PENDING,
        )
        track = ArtifactDeleteTrack(id=uuid7(), name="track")
        blocked = _record(
            artifact_id,
            name="artifact",
            status=ArtifactStatus.PENDING_DELETION,
            deployments=[deployment] if race_reason == "deployments" else [],
            tracks=[track] if race_reason == "tracks" else [],
        )
        mocks.repository.get_batch_deletion_records.side_effect = [
            [initial],
            [blocked],
        ]
        mocks.repository.delete_artifact_record.side_effect = DatabaseConstraintError()

        result = await mocks.handler.confirm_deletions(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            COLLECTION_ID,
            [artifact_id],
        )

        assert result.deleted == []
        assert result.failed[0].reason.value == race_reason
        assert result.failed[0].deployments == (
            [deployment] if race_reason == "deployments" else []
        )
        assert result.failed[0].tracks == ([track] if race_reason == "tracks" else [])

    async def test_confirm_deletions_checks_permission_and_access_once(
        self, mocks: CollaboratorMocks[ArtifactHandler], check_access: AsyncMock
    ) -> None:
        mocks.repository.get_batch_deletion_records.return_value = []
        artifact_id = uuid7()

        await mocks.handler.confirm_deletions(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            COLLECTION_ID,
            [artifact_id],
        )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.ARTIFACT,
            Action.DELETE,
            ORBIT_ID,
        )
        check_access.assert_awaited_once_with(
            ORGANIZATION_ID,
            ORBIT_ID,
            COLLECTION_ID,
        )
