from types import SimpleNamespace
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


class TestArtifactsBatchDeletion:
    @pytest.fixture
    def context(self) -> SimpleNamespace:
        handler = ArtifactHandler()
        repository = Mock()
        repository.request_batch_deletion = AsyncMock(return_value=[])
        repository.get_batch_deletion_records = AsyncMock(return_value=[])
        repository.mark_deletion_failed = AsyncMock()
        repository.delete_artifact_record = AsyncMock(return_value=True)
        permissions = Mock(check_permissions=AsyncMock())
        storage_client = Mock(get_delete_url=AsyncMock())
        orbit = Mock(bucket_secret_id=uuid7())
        check_access = AsyncMock(return_value=(orbit, Mock()))
        get_storage_client = AsyncMock(return_value=storage_client)

        handler._ArtifactHandler__repository = repository
        handler._ArtifactHandler__permissions_handler = permissions
        handler._check_orbit_and_collection_access = check_access
        handler._get_storage_client = get_storage_client

        return SimpleNamespace(
            handler=handler,
            repository=repository,
            permissions=permissions,
            check_access=check_access,
            get_storage_client=get_storage_client,
            storage_client=storage_client,
            user_id=uuid7(),
            organization_id=uuid7(),
            orbit_id=uuid7(),
            collection_id=uuid7(),
        )

    @pytest.mark.asyncio
    async def test_request_accepts_every_status_and_collapses_duplicates(
        self, context: SimpleNamespace
    ) -> None:
        records = [
            _record(uuid7(), name=artifact_status.value, status=artifact_status)
            for artifact_status in ArtifactStatus
        ]
        context.repository.request_batch_deletion.return_value = records
        context.storage_client.get_delete_url.side_effect = [
            f"https://bucket/{record.artifact.id}" for record in records
        ]
        requested_ids = [record.artifact.id for record in records]

        result = await context.handler.request_delete_urls(
            context.user_id,
            context.organization_id,
            context.orbit_id,
            context.collection_id,
            [*requested_ids, requested_ids[0], requested_ids[0]],
        )

        assert [entry.artifact_id for entry in result.urls] == requested_ids
        assert result.failed == []
        context.repository.request_batch_deletion.assert_awaited_once_with(
            context.collection_id, requested_ids
        )
        assert context.storage_client.get_delete_url.await_args_list == [
            call(record.artifact.bucket_location) for record in records
        ]
        context.repository.mark_deletion_failed.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_request_classifies_mixed_selection_in_precedence_order(
        self, context: SimpleNamespace
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
        context.repository.request_batch_deletion.return_value = records
        context.storage_client.get_delete_url.return_value = "https://bucket/delete"

        result = await context.handler.request_delete_urls(
            context.user_id,
            context.organization_id,
            context.orbit_id,
            context.collection_id,
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
        context.repository.delete_artifact_record.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_request_marks_only_signing_failures(
        self, context: SimpleNamespace
    ) -> None:
        first = _record(uuid7(), name="first")
        second = _record(uuid7(), name="second")
        context.repository.request_batch_deletion.return_value = [first, second]

        async def sign_delete_url(bucket_location: str) -> str:
            if bucket_location == second.artifact.bucket_location:
                raise BucketConnectionError("cannot sign")
            return "https://bucket/delete"

        context.storage_client.get_delete_url.side_effect = sign_delete_url

        result = await context.handler.request_delete_urls(
            context.user_id,
            context.organization_id,
            context.orbit_id,
            context.collection_id,
            [first.artifact.id, second.artifact.id],
        )

        assert [entry.artifact_id for entry in result.urls] == [first.artifact.id]
        assert len(result.failed) == 1
        assert result.failed[0].artifact_id == second.artifact.id
        assert result.failed[0].name == "second"
        assert result.failed[0].reason == ArtifactDeleteReason.STORAGE_ERROR
        context.repository.mark_deletion_failed.assert_awaited_once_with(
            context.collection_id, [second.artifact.id]
        )

    @pytest.mark.asyncio
    async def test_request_propagates_unexpected_signing_errors(
        self, context: SimpleNamespace
    ) -> None:
        record = _record(uuid7(), name="first")
        context.repository.request_batch_deletion.return_value = [record]
        context.storage_client.get_delete_url.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await context.handler.request_delete_urls(
                context.user_id,
                context.organization_id,
                context.orbit_id,
                context.collection_id,
                [record.artifact.id],
            )

        context.repository.mark_deletion_failed.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_names_fall_back_to_file_name(self, context: SimpleNamespace) -> None:
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
        context.repository.request_batch_deletion.return_value = [eligible, deployed]
        context.storage_client.get_delete_url.return_value = "https://bucket/delete"

        requested = await context.handler.request_delete_urls(
            context.user_id,
            context.organization_id,
            context.orbit_id,
            context.collection_id,
            [eligible.artifact.id, deployed.artifact.id],
        )

        assert [entry.name for entry in requested.urls] == ["eligible.luml"]
        assert [entry.name for entry in requested.failed] == ["deployed.luml"]

        context.repository.get_batch_deletion_records.return_value = [eligible]
        confirmed = await context.handler.confirm_deletions(
            context.user_id,
            context.organization_id,
            context.orbit_id,
            context.collection_id,
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
    @pytest.mark.asyncio
    async def test_request_level_checks_change_nothing(
        self,
        context: SimpleNamespace,
        failure: Exception,
        failing_mock: str,
    ) -> None:
        if failing_mock == "permissions":
            context.permissions.check_permissions.side_effect = failure
        elif failing_mock == "access":
            context.check_access.side_effect = failure
        else:
            context.get_storage_client.side_effect = failure

        with pytest.raises(type(failure)):
            await context.handler.request_delete_urls(
                context.user_id,
                context.organization_id,
                context.orbit_id,
                context.collection_id,
                [uuid7()],
            )

        context.repository.request_batch_deletion.assert_not_awaited()
        context.repository.mark_deletion_failed.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_confirm_has_partial_success_and_defaults_force_to_false(
        self, context: SimpleNamespace
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
        context.repository.get_batch_deletion_records.return_value = records

        result = await context.handler.confirm_deletions(
            context.user_id,
            context.organization_id,
            context.orbit_id,
            context.collection_id,
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
        context.repository.delete_artifact_record.assert_awaited_once_with(
            deletable.artifact.id, context.collection_id
        )
        context.get_storage_client.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_confirm_deletes_every_pending_artifact(
        self, context: SimpleNamespace
    ) -> None:
        records = [
            _record(
                uuid7(),
                name=f"artifact-{index}",
                status=ArtifactStatus.PENDING_DELETION,
            )
            for index in range(3)
        ]
        context.repository.get_batch_deletion_records.return_value = records
        artifact_ids = [record.artifact.id for record in records]

        result = await context.handler.confirm_deletions(
            context.user_id,
            context.organization_id,
            context.orbit_id,
            context.collection_id,
            artifact_ids,
        )

        assert result.deleted == artifact_ids
        assert result.failed == []
        assert context.repository.delete_artifact_record.await_args_list == [
            call(artifact_id, context.collection_id) for artifact_id in artifact_ids
        ]

    @pytest.mark.asyncio
    async def test_force_deletes_artifacts_in_every_status_without_storage(
        self, context: SimpleNamespace
    ) -> None:
        records = [
            _record(uuid7(), name=artifact_status.value, status=artifact_status)
            for artifact_status in ArtifactStatus
        ]
        context.repository.get_batch_deletion_records.return_value = records
        ids = [record.artifact.id for record in records]

        result = await context.handler.confirm_deletions(
            context.user_id,
            context.organization_id,
            context.orbit_id,
            context.collection_id,
            ids,
            force=True,
        )

        assert result.deleted == ids
        assert result.failed == []
        assert context.repository.delete_artifact_record.await_args_list == [
            call(artifact_id, context.collection_id) for artifact_id in ids
        ]
        context.get_storage_client.assert_not_awaited()
        context.storage_client.get_delete_url.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_force_still_reports_references_and_unknown_ids(
        self, context: SimpleNamespace
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
        context.repository.get_batch_deletion_records.return_value = [
            deployed,
            tracked,
        ]

        result = await context.handler.confirm_deletions(
            context.user_id,
            context.organization_id,
            context.orbit_id,
            context.collection_id,
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
        context.repository.delete_artifact_record.assert_not_awaited()

    @pytest.mark.parametrize("race_reason", ["deployments", "tracks"])
    @pytest.mark.asyncio
    async def test_confirm_maps_constraint_race_to_current_reference(
        self, context: SimpleNamespace, race_reason: str
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
        context.repository.get_batch_deletion_records.side_effect = [
            [initial],
            [blocked],
        ]
        context.repository.delete_artifact_record.side_effect = (
            DatabaseConstraintError()
        )

        result = await context.handler.confirm_deletions(
            context.user_id,
            context.organization_id,
            context.orbit_id,
            context.collection_id,
            [artifact_id],
        )

        assert result.deleted == []
        assert result.failed[0].reason.value == race_reason
        assert result.failed[0].deployments == (
            [deployment] if race_reason == "deployments" else []
        )
        assert result.failed[0].tracks == ([track] if race_reason == "tracks" else [])

    @pytest.mark.asyncio
    async def test_confirm_checks_permission_and_access_once(
        self, context: SimpleNamespace
    ) -> None:
        context.repository.get_batch_deletion_records.return_value = []
        artifact_id = uuid7()

        await context.handler.confirm_deletions(
            context.user_id,
            context.organization_id,
            context.orbit_id,
            context.collection_id,
            [artifact_id],
        )

        context.permissions.check_permissions.assert_awaited_once_with(
            context.organization_id,
            context.user_id,
            Resource.ARTIFACT,
            Action.DELETE,
            context.orbit_id,
        )
        context.check_access.assert_awaited_once_with(
            context.organization_id,
            context.orbit_id,
            context.collection_id,
        )
