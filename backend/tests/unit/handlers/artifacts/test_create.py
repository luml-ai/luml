from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid7

import pytest
from luml.handlers.artifacts import ArtifactHandler
from luml.infra.exceptions import (
    ApplicationError,
    ArtifactNotFoundError,
    ArtifactTypeMismatchError,
    BucketSecretNotFoundError,
    NotFoundError,
    OrganizationLimitReachedError,
)
from luml.schemas.artifacts import (
    Artifact,
    ArtifactCreate,
    ArtifactCreateIn,
    ArtifactStatus,
    ArtifactType,
    LumlArtifactManifest,
    Manifest,
)
from luml.schemas.bucket_secrets import S3BucketSecret
from luml.schemas.collections import CollectionType
from luml.schemas.permissions import Action, Resource
from luml.schemas.storage import S3UploadDetails

from tests.support.ids import (
    ARTIFACT_ID,
    COLLECTION_ID,
    ORBIT_ID,
    ORGANIZATION_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.artifacts.conftest import (
    _artifact_create_input,
    _pending_artifact,
)

API_KEY_SCOPES = ("authenticated", "api_key")
JWT_SCOPES = ("authenticated", "jwt")


class TestArtifactCreation:
    @pytest.fixture
    def stubs(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        monkeypatch: pytest.MonkeyPatch,
    ) -> SimpleNamespace:
        stubs = SimpleNamespace(
            check_access=AsyncMock(),
            define_artifact_type=Mock(return_value=ArtifactType.MODEL),
            get_storage_client=AsyncMock(),
        )
        monkeypatch.setattr(
            mocks.handler, "_check_orbit_and_collection_access", stubs.check_access
        )
        monkeypatch.setattr(
            mocks.handler, "_define_artifact_type", stubs.define_artifact_type
        )
        mocks.user_repository.get_organization_details.return_value = Mock(
            total_artifacts=0, artifacts_limit=1
        )
        monkeypatch.setattr(
            mocks.handler, "_get_storage_client", stubs.get_storage_client
        )
        return stubs

    async def test_create_artifact_raises_type_mismatch_when_declared_type_differs(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        stubs: SimpleNamespace,
        manifest: Manifest,
    ) -> None:
        bucket_secret_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8345")

        artifact_in = ArtifactCreateIn(
            extra_values={},
            manifest=manifest,
            file_hash="hash",
            file_index={},
            size=1,
            file_name="file.txt",
            name=None,
            tags=["tag"],
            type=ArtifactType.DATASET,
        )
        stubs.check_access.return_value = (
            Mock(bucket_secret_id=bucket_secret_id, organization_id=ORGANIZATION_ID),
            Mock(orbit_id=ORBIT_ID, type=CollectionType.MODEL),
        )
        stubs.define_artifact_type.return_value = ArtifactType.MODEL
        with pytest.raises(ArtifactTypeMismatchError) as error:
            await mocks.handler.create_artifact(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                COLLECTION_ID,
                artifact_in,
                API_KEY_SCOPES,
            )

        assert error.value.status_code == 400
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.CREATE, ORBIT_ID
        )

    async def test_create_artifact_returns_pending_artifact_with_upload_details(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        stubs: SimpleNamespace,
        manifest: Manifest,
    ) -> None:
        bucket_secret_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8345")
        bucket_location = "orbit/collection/file_name"

        artifact = Artifact(
            id=ARTIFACT_ID,
            collection_id=COLLECTION_ID,
            file_name="model.luml",
            name=None,
            extra_values={},
            manifest=manifest,
            file_hash="hash",
            file_index={},
            bucket_location=bucket_location,
            size=1,
            unique_identifier="uid",
            tags=["tag"],
            status=ArtifactStatus.PENDING_UPLOAD,
            created_at=datetime.now(),
            updated_at=None,
            created_by_user="user_full_name,",
            type=ArtifactType.MODEL,
        )

        mocks.repository.create_artifact.return_value = artifact
        stubs.check_access.return_value = (
            Mock(bucket_secret_id=bucket_secret_id, organization_id=ORGANIZATION_ID),
            Mock(orbit_id=ORBIT_ID, type=CollectionType.MODEL),
        )
        storage_client = AsyncMock()
        upload_data = S3UploadDetails(
            url=" https://dfs-models.s3.eu-north-1.amazonaws.com/orbit/collection/my_llm.pyfnx",
            multipart=False,
            bucket_location=bucket_location,
            bucket_secret_id=bucket_secret_id,
        )
        storage_client.create_upload.return_value = upload_data
        stubs.get_storage_client.return_value = storage_client
        mocks.user_repository.get_public_user_by_id.return_value = Mock(
            full_name="user_full_name"
        )

        artifact_in = ArtifactCreateIn(
            extra_values={},
            manifest=manifest,
            file_hash="hash",
            file_index={},
            size=1,
            file_name="file.txt",
            name=None,
            tags=["tag"],
        )
        result = await mocks.handler.create_artifact(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            COLLECTION_ID,
            artifact_in,
            API_KEY_SCOPES,
        )

        assert result.artifact == artifact
        assert "lineage_inputs" not in result.model_dump()["artifact"]
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.CREATE, ORBIT_ID
        )
        mocks.repository.create_artifact.assert_awaited_once()
        assert mocks.repository.create_artifact.await_args is not None
        create_model = mocks.repository.create_artifact.await_args.args[0]
        assert isinstance(create_model, ArtifactCreate)
        assert "lineage_inputs" not in create_model.model_dump()
        mocks.repository.get_artifacts_by_ids_in_orbit.assert_not_awaited()
        mocks.lineage_handler.link_inputs.assert_not_awaited()
        stubs.get_storage_client.assert_awaited_once()
        storage_client.create_upload.assert_awaited_once()
        mocks.user_repository.get_organization_details.assert_awaited_once_with(
            ORGANIZATION_ID
        )

    async def test_create_artifact_links_deduplicated_lineage_inputs(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        stubs: SimpleNamespace,
        manifest: Manifest,
    ) -> None:
        experiment_id = uuid7()
        dataset_id = uuid7()
        bucket_secret_id = uuid7()
        created_artifact = _pending_artifact(manifest, ARTIFACT_ID, COLLECTION_ID)
        stubs.check_access.return_value = (
            Mock(bucket_secret_id=bucket_secret_id),
            Mock(type=CollectionType.MODEL),
        )
        mocks.user_repository.get_public_user_by_id.return_value = Mock(
            full_name="Artifact User"
        )
        mocks.repository.get_artifacts_by_ids_in_orbit.return_value = [
            Mock(id=experiment_id),
            Mock(id=dataset_id),
        ]
        mocks.repository.create_artifact.return_value = created_artifact
        upload_details = S3UploadDetails(
            url="https://storage.example/upload",
            multipart=False,
            bucket_location=created_artifact.bucket_location,
            bucket_secret_id=bucket_secret_id,
        )
        stubs.get_storage_client.return_value.create_upload.return_value = (
            upload_details
        )
        artifact_in = _artifact_create_input(
            manifest, [experiment_id, dataset_id, experiment_id]
        )

        result = await mocks.handler.create_artifact(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            COLLECTION_ID,
            artifact_in,
            JWT_SCOPES,
        )

        assert result.artifact == created_artifact
        assert result.artifact.status == ArtifactStatus.PENDING_UPLOAD
        assert "lineage_inputs" not in result.model_dump()["artifact"]
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.ARTIFACT,
            Action.CREATE,
            ORBIT_ID,
        )
        mocks.repository.get_artifacts_by_ids_in_orbit.assert_awaited_once_with(
            ORBIT_ID, [experiment_id, dataset_id]
        )
        assert mocks.repository.create_artifact.await_args is not None
        create_model = mocks.repository.create_artifact.await_args.args[0]
        assert isinstance(create_model, ArtifactCreate)
        assert "lineage_inputs" not in create_model.model_dump()
        mocks.lineage_handler.link_inputs.assert_awaited_once_with(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            ARTIFACT_ID,
            [experiment_id, dataset_id],
            JWT_SCOPES,
            check_access=False,
        )

    @pytest.mark.parametrize(
        "lineage_input",
        [
            UUID("0199c337-0b01-7c1e-8a3b-3f0e1a6d95c4"),
            UUID("0199c337-0b02-7c1e-8a3b-3f0e1a6d95c4"),
        ],
        ids=["another-orbit", "missing"],
    )
    async def test_create_artifact_raises_not_found_when_lineage_input_is_outside_orbit(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        stubs: SimpleNamespace,
        lineage_input: UUID,
        manifest: Manifest,
    ) -> None:
        stubs.check_access.return_value = (
            Mock(bucket_secret_id=uuid7()),
            Mock(type=CollectionType.MODEL),
        )
        mocks.user_repository.get_public_user_by_id.return_value = Mock(
            full_name="Artifact User"
        )
        mocks.repository.get_artifacts_by_ids_in_orbit.return_value = []

        with pytest.raises(ArtifactNotFoundError) as error:
            await mocks.handler.create_artifact(
                uuid7(),
                uuid7(),
                ORBIT_ID,
                uuid7(),
                _artifact_create_input(manifest, [lineage_input]),
                API_KEY_SCOPES,
            )

        assert error.value.status_code == 404
        assert error.value.message == "Artifact not found"
        mocks.repository.get_artifacts_by_ids_in_orbit.assert_awaited_once_with(
            ORBIT_ID, [lineage_input]
        )
        mocks.repository.create_artifact.assert_not_awaited()
        mocks.lineage_handler.link_inputs.assert_not_awaited()
        stubs.get_storage_client.assert_not_awaited()

    async def test_create_artifact_records_nothing_when_upload_initialization_fails(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        stubs: SimpleNamespace,
        manifest: Manifest,
    ) -> None:
        lineage_input = uuid7()
        stubs.check_access.return_value = (
            Mock(bucket_secret_id=uuid7()),
            Mock(type=CollectionType.MODEL),
        )
        mocks.user_repository.get_public_user_by_id.return_value = Mock(
            full_name="Artifact User"
        )
        mocks.repository.get_artifacts_by_ids_in_orbit.return_value = [
            Mock(id=lineage_input)
        ]
        stubs.get_storage_client.return_value = Mock(
            create_upload=AsyncMock(side_effect=RuntimeError("storage unavailable"))
        )

        with pytest.raises(RuntimeError, match="storage unavailable"):
            await mocks.handler.create_artifact(
                uuid7(),
                uuid7(),
                uuid7(),
                uuid7(),
                _artifact_create_input(manifest, [lineage_input]),
                API_KEY_SCOPES,
            )

        mocks.repository.create_artifact.assert_not_awaited()
        mocks.lineage_handler.link_inputs.assert_not_awaited()
        mocks.repository.delete_artifact.assert_not_awaited()

    async def test_create_artifact_deletes_row_when_lineage_linking_fails(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        stubs: SimpleNamespace,
        manifest: Manifest,
    ) -> None:
        lineage_input = uuid7()
        created_artifact = _pending_artifact(manifest, ARTIFACT_ID, COLLECTION_ID)
        stubs.check_access.return_value = (
            Mock(bucket_secret_id=uuid7()),
            Mock(type=CollectionType.MODEL),
        )
        mocks.user_repository.get_public_user_by_id.return_value = Mock(
            full_name="Artifact User"
        )
        mocks.repository.get_artifacts_by_ids_in_orbit.return_value = [
            Mock(id=lineage_input)
        ]
        mocks.repository.create_artifact.return_value = created_artifact
        stubs.get_storage_client.return_value = Mock(create_upload=AsyncMock())
        linking_error = ApplicationError("Lineage failed", 409)
        mocks.lineage_handler.link_inputs.side_effect = linking_error

        with pytest.raises(ApplicationError) as error:
            await mocks.handler.create_artifact(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                COLLECTION_ID,
                _artifact_create_input(manifest, [lineage_input]),
                API_KEY_SCOPES,
            )

        assert error.value is linking_error
        mocks.repository.delete_artifact.assert_awaited_once_with(ARTIFACT_ID)
        stubs.get_storage_client.assert_awaited_once()

    async def test_create_artifact_raises_type_mismatch_when_collection_disallows_type(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        stubs: SimpleNamespace,
        manifest: Manifest,
    ) -> None:
        bucket_secret_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8345")

        stubs.check_access.return_value = (
            Mock(bucket_secret_id=bucket_secret_id, organization_id=ORGANIZATION_ID),
            Mock(orbit_id=ORBIT_ID, type=CollectionType.DATASET),
        )

        artifact_in = ArtifactCreateIn(
            extra_values={},
            manifest=manifest,
            file_hash="hash",
            file_index={},
            size=1,
            file_name="file.txt",
            name=None,
            tags=["tag"],
        )

        with pytest.raises(ArtifactTypeMismatchError):
            await mocks.handler.create_artifact(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                COLLECTION_ID,
                artifact_in,
                API_KEY_SCOPES,
            )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.CREATE, ORBIT_ID
        )
        stubs.check_access.assert_awaited_once_with(
            ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID
        )
        mocks.user_repository.get_organization_details.assert_not_awaited()

    async def test_create_artifact_raises_not_found_when_user_is_missing(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        stubs: SimpleNamespace,
        manifest: Manifest,
    ) -> None:
        bucket_secret_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8345")

        stubs.check_access.return_value = (
            Mock(bucket_secret_id=bucket_secret_id, organization_id=ORGANIZATION_ID),
            Mock(orbit_id=ORBIT_ID, type=CollectionType.MODEL),
        )
        mocks.user_repository.get_public_user_by_id.return_value = None

        artifact_in = ArtifactCreateIn(
            extra_values={},
            manifest=manifest,
            file_hash="hash",
            file_index={},
            size=1,
            file_name="file.txt",
            name=None,
            tags=["tag"],
        )

        with pytest.raises(NotFoundError, match="User not found"):
            await mocks.handler.create_artifact(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                COLLECTION_ID,
                artifact_in,
                API_KEY_SCOPES,
            )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.CREATE, ORBIT_ID
        )
        stubs.check_access.assert_awaited_once_with(
            ORGANIZATION_ID, ORBIT_ID, COLLECTION_ID
        )
        mocks.user_repository.get_organization_details.assert_awaited_once_with(
            ORGANIZATION_ID
        )
        mocks.user_repository.get_public_user_by_id.assert_awaited_once_with(USER_ID)

    async def test_check_organization_artifacts_limit_raises_when_organization_missing(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        mocks.user_repository.get_organization_details.return_value = None

        with pytest.raises(NotFoundError) as error:
            await mocks.handler._check_organization_artifacts_limit(ORGANIZATION_ID)

        assert error.value.status_code == 404
        mocks.user_repository.get_organization_details.assert_awaited_once_with(
            ORGANIZATION_ID
        )

    async def test_check_organization_artifacts_limit_raises_when_limit_is_reached(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        mocks.user_repository.get_organization_details.return_value = Mock(
            total_artifacts=100,
            artifacts_limit=100,
        )

        with pytest.raises(OrganizationLimitReachedError) as error:
            await mocks.handler._check_organization_artifacts_limit(ORGANIZATION_ID)

        assert error.value.status_code == 409
        mocks.user_repository.get_organization_details.assert_awaited_once_with(
            ORGANIZATION_ID
        )

    def test_define_artifact_type_returns_manifest_type_when_manifest_is_luml(
        self,
    ) -> None:
        artifact = Mock(
            manifest=LumlArtifactManifest(
                artifact_type="model",
                variant="pipeline",
                producer_name="test",
                producer_version="1.0",
                producer_tags=[],
                payload={},
            ),
            file_index={},
        )

        result = ArtifactHandler._define_artifact_type(artifact)

        assert result == ArtifactType.MODEL

    def test_define_artifact_type_raises_type_mismatch_when_luml_type_is_unsupported(
        self,
    ) -> None:
        artifact = Mock(
            manifest=LumlArtifactManifest(
                artifact_type="unsupported_type",
                variant="pipeline",
                producer_name="test",
                producer_version="1.0",
                producer_tags=[],
                payload={},
            ),
            file_index={},
        )

        with pytest.raises(
            ArtifactTypeMismatchError, match="Unsupported LUML Artifact type"
        ):
            ArtifactHandler._define_artifact_type(artifact)

    def test_define_artifact_type_returns_model_when_file_index_has_model_files(
        self,
    ) -> None:
        model_files = {
            "dtypes.json": "content",
            "env.json": "content",
            "manifest.json": "content",
            "meta.json": "content",
            "ops.json": "content",
            "variant_config.json": "content",
        }
        artifact = Mock(
            manifest=Mock(spec=[]),
            file_index=model_files,
        )

        result = ArtifactHandler._define_artifact_type(artifact)

        assert result == ArtifactType.MODEL

    def test_define_artifact_type_raises_type_mismatch_when_type_is_undetectable(
        self,
    ) -> None:
        artifact = Mock(
            manifest=Mock(spec=[]),
            file_index={"random_file.txt": "content"},
        )

        with pytest.raises(
            ArtifactTypeMismatchError, match="Could not define artifact type"
        ):
            ArtifactHandler._define_artifact_type(artifact)

    async def test_get_secret_or_raise_returns_secret(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        bucket_secret: S3BucketSecret,
    ) -> None:
        expected = bucket_secret.model_copy()
        mocks.secret_repository.get_bucket_secret.return_value = expected

        secret = await mocks.handler._get_secret_or_raise(expected.id)

        assert secret == expected
        assert isinstance(expected, S3BucketSecret)
        mocks.secret_repository.get_bucket_secret.assert_awaited_once()

    async def test_get_secret_or_raise_raises_not_found_when_secret_is_missing(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        secret_id = UUID("0199c3f7-f040-7f63-9bef-a1f380ae9eeb")

        mocks.secret_repository.get_bucket_secret.return_value = None

        with pytest.raises(BucketSecretNotFoundError) as error:
            await mocks.handler._get_secret_or_raise(secret_id)

        assert error.value.status_code == 404
        mocks.secret_repository.get_bucket_secret.assert_awaited_once_with(secret_id)

    async def test_get_storage_client_builds_client_for_secret_type(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        bucket_secret: S3BucketSecret,
    ) -> None:
        secret_id = UUID("0199c3f7-f040-7f63-9bef-a1f380ae9eeb")

        mocks.secret_repository.get_bucket_secret.return_value = bucket_secret

        storage_instance = Mock()
        service_class = Mock(return_value=storage_instance)

        with patch(
            "luml.handlers.artifacts.create_storage_client",
            return_value=service_class,
        ) as create_storage_client:
            result = await mocks.handler._get_storage_client(secret_id)

        mocks.secret_repository.get_bucket_secret.assert_awaited_once_with(secret_id)
        create_storage_client.assert_called_once_with(bucket_secret.type)
        service_class.assert_called_once_with(bucket_secret)
        assert result == storage_instance
