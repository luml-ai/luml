from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import cast
from unittest.mock import AsyncMock, Mock, call, patch
from uuid import UUID, uuid7

import pytest
from luml.handlers.artifacts import ArtifactHandler
from luml.infra.exceptions import (
    ApplicationError,
    ArtifactDeployedError,
    ArtifactNotFoundError,
    ArtifactTrackedError,
    ArtifactTypeMismatchError,
    BucketSecretNotFoundError,
    CollectionNotFoundError,
    InvalidSortingError,
    InvalidStatusTransitionError,
    NotFoundError,
    OrbitNotFoundError,
    OrganizationLimitReachedError,
)
from luml.repositories.lineage import LineageRepository
from luml.schemas.artifacts import (
    Artifact,
    ArtifactCreate,
    ArtifactCreateIn,
    ArtifactDetails,
    ArtifactListed,
    ArtifactsList,
    ArtifactStatus,
    ArtifactType,
    ArtifactUpdate,
    ArtifactUpdateIn,
    LumlArtifactManifest,
    Manifest,
)
from luml.schemas.bucket_secrets import S3BucketSecret
from luml.schemas.collections import Collection, CollectionType
from luml.schemas.deployment import Deployment, DeploymentBase, DeploymentStatus
from luml.schemas.general import Cursor, PaginationParams, SortOrder
from luml.schemas.permissions import Action, Resource
from luml.schemas.storage import S3UploadDetails
from luml.utils.pagination import build_scope_id, encode_cursor
from sqlalchemy.ext.asyncio import AsyncSession

handler = ArtifactHandler()

API_KEY_SCOPES = ["authenticated", "api_key"]
JWT_SCOPES = ["authenticated", "jwt"]

# Physical deletion runs in one lineage transaction; the stub hands every
# repository call the same session and records an error that reaches it.
DELETION_SESSION = cast(AsyncSession, Mock(spec=AsyncSession))
DELETION_TRANSACTION_ERRORS: list[BaseException] = []


@asynccontextmanager
async def _deletion_transaction(
    repository: LineageRepository,
) -> AsyncIterator[AsyncSession]:
    try:
        yield DELETION_SESSION
    except BaseException as error:
        DELETION_TRANSACTION_ERRORS.append(error)
        raise


@patch(
    "luml.handlers.artifacts.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_secret_or_raise(
    mock_get_bucket_secret: AsyncMock, test_bucket: S3BucketSecret
) -> None:
    expected = test_bucket.model_copy()
    mock_get_bucket_secret.return_value = expected

    secret = await handler._get_secret_or_raise(expected.id)

    assert secret == expected
    assert isinstance(expected, S3BucketSecret)
    mock_get_bucket_secret.assert_awaited_once()


@patch(
    "luml.handlers.artifacts.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_secret_or_raise_not_found(mock_get_bucket_secret: AsyncMock) -> None:
    secret_id = UUID("0199c3f7-f040-7f63-9bef-a1f380ae9eeb")

    mock_get_bucket_secret.return_value = None

    with pytest.raises(BucketSecretNotFoundError) as error:
        await handler._get_secret_or_raise(secret_id)

    assert error.value.status_code == 404
    mock_get_bucket_secret.assert_awaited_once_with(secret_id)


@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_orbit_and_collection_access(
    mock_get_orbit_simple: AsyncMock, mock_get_collection: AsyncMock
) -> None:
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    orbit = Mock(organization_id=organization_id)
    collection = Mock(orbit_id=orbit_id)

    mock_get_orbit_simple.return_value = orbit
    mock_get_collection.return_value = collection

    result = await handler._check_orbit_and_collection_access(
        organization_id, orbit_id, collection_id
    )

    assert result == (orbit, collection)
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_collection.assert_awaited_once_with(collection_id)


@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_orbit_and_collection_access_orbit_not_found(
    mock_get_orbit_simple: AsyncMock,
) -> None:
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    mock_get_orbit_simple.return_value = None

    with pytest.raises(OrbitNotFoundError) as error:
        await handler._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )

    assert error.value.status_code == 404
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)


@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_orbit_and_collection_access_collection_not_found(
    mock_get_orbit_simple: AsyncMock, mock_get_collection: AsyncMock
) -> None:
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    orbit = Mock(organization_id=organization_id)

    mock_get_orbit_simple.return_value = orbit
    mock_get_collection.return_value = None

    with pytest.raises(CollectionNotFoundError) as error:
        await handler._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )

    assert error.value.status_code == 404
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_collection.assert_awaited_once_with(collection_id)


@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collections_by_ids",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_orbit_and_collections_access_all_accessible(
    mock_get_orbit_simple: AsyncMock, mock_get_collections_by_ids: AsyncMock
) -> None:
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_ids = [
        UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70"),
        UUID("0199c337-09f5-7a01-9f5f-5f68db62cf71"),
    ]

    orbit = Mock(organization_id=organization_id)
    mock_get_orbit_simple.return_value = orbit
    mock_get_collections_by_ids.return_value = [
        Mock(id=collection_ids[0]),
        Mock(id=collection_ids[1]),
    ]

    result = await handler._check_orbit_and_collections_access(
        organization_id, orbit_id, collection_ids
    )

    assert result == orbit
    mock_get_collections_by_ids.assert_awaited_once_with(
        collection_ids, orbit_id=orbit_id
    )


@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collections_by_ids",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_orbit_and_collections_access_missing_collection(
    mock_get_orbit_simple: AsyncMock, mock_get_collections_by_ids: AsyncMock
) -> None:
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    accessible_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    forbidden_id = UUID("0199c337-09f5-7a01-9f5f-5f68db62cf71")

    orbit = Mock(organization_id=organization_id)
    mock_get_orbit_simple.return_value = orbit
    # Only one of the two requested collections belongs to the orbit.
    mock_get_collections_by_ids.return_value = [Mock(id=accessible_id)]

    with pytest.raises(CollectionNotFoundError) as error:
        await handler._check_orbit_and_collections_access(
            organization_id, orbit_id, [accessible_id, forbidden_id]
        )

    assert error.value.status_code == 404
    assert str(forbidden_id) in str(error.value)
    assert str(accessible_id) not in str(error.value)


@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collections_by_ids",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_orbit_and_collections_access_no_collection_ids(
    mock_get_orbit_simple: AsyncMock, mock_get_collections_by_ids: AsyncMock
) -> None:
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    orbit = Mock(organization_id=organization_id)
    mock_get_orbit_simple.return_value = orbit

    result = await handler._check_orbit_and_collections_access(
        organization_id, orbit_id, None
    )

    assert result == orbit
    mock_get_collections_by_ids.assert_not_awaited()


@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_orbit_and_collections_access_orbit_not_found(
    mock_get_orbit_simple: AsyncMock,
) -> None:
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_get_orbit_simple.return_value = None

    with pytest.raises(OrbitNotFoundError) as error:
        await handler._check_orbit_and_collections_access(
            organization_id, orbit_id, [uuid7()]
        )

    assert error.value.status_code == 404


@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_collection_artifacts",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collections_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_collection_artifacts(
    mock_check_permissions: AsyncMock,
    mock_check_orbit_and_collections_access: AsyncMock,
    mock_get_collection_artifact: AsyncMock,
    manifest_example: Manifest,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    expected_models_list = [
        ArtifactListed.model_validate(
            {
                "id": artifact_id,
                "collection_id": collection_id,
                "collection": {"name": "model1-collection"},
                "file_name": "model1.pkl",
                "name": "model1",
                "extra_values": {"accuracy": 0.95},
                "manifest": manifest_example,
                "file_hash": "hash1",
                "file_index": {},
                "bucket_location": "loc1",
                "size": 100,
                "unique_identifier": "uid1",
                "tags": ["tag1"],
                "status": ArtifactStatus.UPLOADED,
                "created_at": datetime.now(),
                "updated_at": None,
                "type": ArtifactType.MODEL,
                "deployments": [
                    DeploymentBase(
                        id=UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622"),
                        name="test",
                        status=DeploymentStatus.ACTIVE,
                        orbit_id=orbit_id,
                    )
                ],
            }
        )
    ]
    expected = ArtifactsList(items=expected_models_list, cursor=None)

    mock_get_collection_artifact.return_value = (expected_models_list, None)

    result = await handler.get_collection_artifacts(
        user_id, organization_id, orbit_id, [collection_id]
    )

    assert result == expected
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ARTIFACT, Action.LIST, orbit_id
    )
    mock_check_orbit_and_collections_access.assert_awaited_once_with(
        organization_id, orbit_id, [collection_id]
    )
    mock_get_collection_artifact.assert_awaited_once_with(
        orbit_id=orbit_id,
        pagination=PaginationParams(
            cursor=None,
            sort_by="created_at",
            scope_id=build_scope_id(
                orbit_id=orbit_id,
                collection_ids=[collection_id],
                artifact_types=None,
                search=None,
                excluded_tracks=None,
            ),
            order=SortOrder.DESC,
            limit=100,
            extra_sort_field=None,
        ),
        collection_ids=[collection_id],
        artifact_types=None,
        search=None,
        excluded_tracks=None,
    )


def _make_listed(manifest: Manifest, **overrides: object) -> ArtifactListed:
    base: dict[str, object] = {
        "id": uuid7(),
        "collection_id": uuid7(),
        "collection": {"name": "col"},
        "file_name": "f.pkl",
        "name": "artifact",
        "extra_values": {},
        "manifest": manifest,
        "file_hash": "h",
        "file_index": {},
        "bucket_location": "loc",
        "size": 1,
        "unique_identifier": str(uuid7()),
        "tags": None,
        "status": ArtifactStatus.UPLOADED,
        "created_at": datetime.now(),
        "updated_at": None,
        "type": ArtifactType.MODEL,
        "deployments": [],
    }
    base.update(overrides)
    return ArtifactListed.model_validate(base)


def _pagination_arg(mock: AsyncMock) -> PaginationParams:
    assert mock.await_args is not None
    pagination = mock.await_args.kwargs["pagination"]
    assert isinstance(pagination, PaginationParams)
    return pagination


@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_collection_artifacts",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collections_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_collection_artifacts_forwards_filters(
    mock_check_permissions: AsyncMock,
    mock_check_access: AsyncMock,
    mock_repo: AsyncMock,
) -> None:
    organization_id = uuid7()
    user_id = uuid7()
    orbit_id = uuid7()
    collection_ids = [uuid7(), uuid7()]
    artifact_types = [ArtifactType.MODEL, ArtifactType.DATASET]
    excluded_tracks = [uuid7()]
    mock_repo.return_value = ([], None)

    await handler.get_collection_artifacts(
        user_id,
        organization_id,
        orbit_id,
        collection_ids,
        artifact_types,
        search="resnet",
        excluded_tracks=excluded_tracks,
    )

    expected_scope = build_scope_id(
        orbit_id=orbit_id,
        collection_ids=collection_ids,
        artifact_types=artifact_types,
        search="resnet",
        excluded_tracks=excluded_tracks,
    )
    mock_check_access.assert_awaited_once_with(
        organization_id, orbit_id, collection_ids
    )
    mock_repo.assert_awaited_once_with(
        orbit_id=orbit_id,
        pagination=PaginationParams(
            cursor=None,
            sort_by="created_at",
            order=SortOrder.DESC,
            limit=100,
            scope_id=expected_scope,
        ),
        collection_ids=collection_ids,
        artifact_types=artifact_types,
        search="resnet",
        excluded_tracks=excluded_tracks,
    )


@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._define_artifact_type",
    return_value=ArtifactType.MODEL,
)
@pytest.mark.asyncio
async def test_create_artifact_type_mismatch(
    mock_define_artifact_type: Mock,
    mock_check_orbit_and_collection_access: AsyncMock,
    mock_check_permissions: AsyncMock,
    manifest_example: Manifest,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    bucket_secret_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8345")

    artifact_in = ArtifactCreateIn(
        extra_values={},
        manifest=manifest_example,
        file_hash="hash",
        file_index={},
        size=1,
        file_name="file.txt",
        name=None,
        tags=["tag"],
        type=ArtifactType.DATASET,
    )
    mock_check_orbit_and_collection_access.return_value = (
        Mock(bucket_secret_id=bucket_secret_id, organization_id=organization_id),
        Mock(orbit_id=orbit_id, type=CollectionType.MODEL),
    )
    mock_define_artifact_type.return_value = ArtifactType.MODEL
    with pytest.raises(ArtifactTypeMismatchError) as error:
        await handler.create_artifact(
            user_id,
            organization_id,
            orbit_id,
            collection_id,
            artifact_in,
            API_KEY_SCOPES,
        )

    assert error.value.status_code == 400
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ARTIFACT, Action.CREATE, orbit_id
    )


@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_collection_artifacts",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collections_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_collection_artifacts_reuses_matching_cursor(
    mock_check_permissions: AsyncMock,
    mock_check_access: AsyncMock,
    mock_repo: AsyncMock,
) -> None:
    orbit_id = uuid7()
    cursor_id = uuid7()
    scope = build_scope_id(
        orbit_id=orbit_id,
        collection_ids=None,
        artifact_types=None,
        search=None,
        excluded_tracks=None,
    )
    cursor_str = encode_cursor(
        Cursor(
            id=cursor_id,
            value=datetime.now(),
            sort_by="created_at",
            order=SortOrder.DESC,
            scope_id=scope,
        )
    )
    mock_repo.return_value = ([], None)

    await handler.get_collection_artifacts(
        uuid7(), uuid7(), orbit_id, cursor_str=cursor_str
    )

    pagination = _pagination_arg(mock_repo)
    assert pagination.cursor is not None
    assert pagination.cursor.id == cursor_id


@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_collection_artifacts",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collections_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_collection_artifacts_resets_cursor_on_filter_change(
    mock_check_permissions: AsyncMock,
    mock_check_access: AsyncMock,
    mock_repo: AsyncMock,
) -> None:
    orbit_id = uuid7()
    # Cursor minted for a filtered scope...
    stale_scope = build_scope_id(
        orbit_id=orbit_id,
        collection_ids=[uuid7()],
        artifact_types=None,
        search=None,
        excluded_tracks=None,
    )
    cursor_str = encode_cursor(
        Cursor(
            id=uuid7(),
            value=datetime.now(),
            sort_by="created_at",
            order=SortOrder.DESC,
            scope_id=stale_scope,
        )
    )
    mock_repo.return_value = ([], None)

    # ...but the request now has no collection_ids -> different scope -> reset.
    await handler.get_collection_artifacts(
        uuid7(), uuid7(), orbit_id, cursor_str=cursor_str
    )

    assert _pagination_arg(mock_repo).cursor is None


@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_collection_artifacts",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collections_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_collection_artifacts_resets_cursor_on_sort_change(
    mock_check_permissions: AsyncMock,
    mock_check_access: AsyncMock,
    mock_repo: AsyncMock,
) -> None:
    orbit_id = uuid7()
    scope = build_scope_id(
        orbit_id=orbit_id,
        collection_ids=None,
        artifact_types=None,
        search=None,
        excluded_tracks=None,
    )
    # Scope matches, but the cursor was for a different sort column.
    cursor_str = encode_cursor(
        Cursor(
            id=uuid7(),
            value="some-name",
            sort_by="name",
            order=SortOrder.DESC,
            scope_id=scope,
        )
    )
    mock_repo.return_value = ([], None)

    await handler.get_collection_artifacts(
        uuid7(), uuid7(), orbit_id, cursor_str=cursor_str, sort_by="created_at"
    )

    assert _pagination_arg(mock_repo).cursor is None


@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_collection_artifacts",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collections_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_collection_artifacts_applies_limit(
    mock_check_permissions: AsyncMock,
    mock_check_access: AsyncMock,
    mock_repo: AsyncMock,
    manifest_example: Manifest,
) -> None:
    items = [_make_listed(manifest_example) for _ in range(3)]
    mock_repo.return_value = (items, None)

    result = await handler.get_collection_artifacts(uuid7(), uuid7(), uuid7(), limit=2)

    assert len(result.items) == 2
    assert result.items == items[:2]


@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_collection_artifacts",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collections_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_collection_artifacts_encodes_returned_cursor(
    mock_check_permissions: AsyncMock,
    mock_check_access: AsyncMock,
    mock_repo: AsyncMock,
    manifest_example: Manifest,
) -> None:
    next_cursor = Cursor(
        id=uuid7(),
        value=datetime.now(),
        sort_by="created_at",
        order=SortOrder.DESC,
        scope_id=uuid7(),
    )
    mock_repo.return_value = ([_make_listed(manifest_example)], next_cursor)

    result = await handler.get_collection_artifacts(uuid7(), uuid7(), uuid7())

    assert result.cursor == encode_cursor(next_cursor)


@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifacts_by_ids_in_orbit",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.LineageHandler.link_inputs",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_organization_artifacts_limit",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.UserRepository.get_public_user_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.create_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._get_storage_client",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._define_artifact_type",
    return_value=ArtifactType.MODEL,
)
@pytest.mark.asyncio
async def test_create_artifact(
    mock_define_artifact_type: Mock,
    mock_get_storage_client: AsyncMock,
    mock_create_artifact: AsyncMock,
    mock_check_orbit_and_collection_access: AsyncMock,
    mock_check_permissions: AsyncMock,
    mock_get_public_user_by_id: AsyncMock,
    mock_check_organization_artifacts_limit: AsyncMock,
    mock_link_inputs: AsyncMock,
    mock_get_lineage_inputs: AsyncMock,
    manifest_example: Manifest,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")
    bucket_secret_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8345")
    bucket_location = "orbit/collection/file_name"

    artifact = Artifact(
        id=artifact_id,
        collection_id=collection_id,
        file_name="model.luml",
        name=None,
        extra_values={},
        manifest=manifest_example,
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

    mock_create_artifact.return_value = artifact
    mock_check_orbit_and_collection_access.return_value = (
        Mock(bucket_secret_id=bucket_secret_id, organization_id=organization_id),
        Mock(orbit_id=orbit_id, type=CollectionType.MODEL),
    )
    mock_storage_client = AsyncMock()
    mock_upload_data = S3UploadDetails(
        url=" https://dfs-models.s3.eu-north-1.amazonaws.com/orbit/collection/my_llm.pyfnx",
        multipart=False,
        bucket_location=bucket_location,
        bucket_secret_id=bucket_secret_id,
    )
    mock_storage_client.create_upload.return_value = mock_upload_data
    mock_get_storage_client.return_value = mock_storage_client
    mock_get_public_user_by_id.return_value = Mock(full_name="user_full_name")

    artifact_in = ArtifactCreateIn(
        extra_values={},
        manifest=manifest_example,
        file_hash="hash",
        file_index={},
        size=1,
        file_name="file.txt",
        name=None,
        tags=["tag"],
    )
    result = await handler.create_artifact(
        user_id,
        organization_id,
        orbit_id,
        collection_id,
        artifact_in,
        API_KEY_SCOPES,
    )

    assert result.artifact == artifact
    assert "lineage_inputs" not in result.model_dump()["artifact"]
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ARTIFACT, Action.CREATE, orbit_id
    )
    mock_create_artifact.assert_awaited_once()
    assert mock_create_artifact.await_args is not None
    create_model = mock_create_artifact.await_args.args[0]
    assert isinstance(create_model, ArtifactCreate)
    assert "lineage_inputs" not in create_model.model_dump()
    mock_get_lineage_inputs.assert_not_awaited()
    mock_link_inputs.assert_not_awaited()
    mock_get_storage_client.assert_awaited_once()
    mock_storage_client.create_upload.assert_awaited_once()
    mock_check_organization_artifacts_limit.assert_awaited_once_with(organization_id)


def _artifact_create_input(
    manifest: Manifest, lineage_inputs: list[UUID] | None = None
) -> ArtifactCreateIn:
    return ArtifactCreateIn(
        extra_values={},
        manifest=manifest,
        file_hash="hash",
        file_index={},
        size=1,
        file_name="model.luml",
        name="model",
        tags=["tag"],
        lineage_inputs=lineage_inputs,
    )


def _pending_artifact(
    manifest: Manifest, artifact_id: UUID, collection_id: UUID
) -> Artifact:
    return Artifact(
        id=artifact_id,
        collection_id=collection_id,
        file_name="model.luml",
        name="model",
        extra_values={},
        manifest=manifest,
        file_hash="hash",
        file_index={},
        bucket_location="artifact/location",
        size=1,
        unique_identifier="uid",
        tags=["tag"],
        status=ArtifactStatus.PENDING_UPLOAD,
        created_at=datetime.now(),
        updated_at=None,
        created_by_user="Artifact User",
        type=ArtifactType.MODEL,
    )


@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_organization_artifacts_limit",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.UserRepository.get_public_user_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifacts_by_ids_in_orbit",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.create_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.LineageHandler.link_inputs",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._get_storage_client",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._define_artifact_type",
    return_value=ArtifactType.MODEL,
)
@pytest.mark.asyncio
async def test_create_artifact_with_lineage_inputs(
    mock_define_artifact_type: Mock,
    mock_get_storage_client: AsyncMock,
    mock_link_inputs: AsyncMock,
    mock_create_artifact: AsyncMock,
    mock_get_lineage_inputs: AsyncMock,
    mock_check_access: AsyncMock,
    mock_check_permissions: AsyncMock,
    mock_get_user: AsyncMock,
    mock_check_limit: AsyncMock,
    manifest_example: Manifest,
) -> None:
    user_id = uuid7()
    organization_id = uuid7()
    orbit_id = uuid7()
    collection_id = uuid7()
    artifact_id = uuid7()
    experiment_id = uuid7()
    dataset_id = uuid7()
    bucket_secret_id = uuid7()
    created_artifact = _pending_artifact(manifest_example, artifact_id, collection_id)
    mock_check_access.return_value = (
        Mock(bucket_secret_id=bucket_secret_id),
        Mock(type=CollectionType.MODEL),
    )
    mock_get_user.return_value = Mock(full_name="Artifact User")
    mock_get_lineage_inputs.return_value = [
        Mock(id=experiment_id),
        Mock(id=dataset_id),
    ]
    mock_create_artifact.return_value = created_artifact
    upload_details = S3UploadDetails(
        url="https://storage.example/upload",
        multipart=False,
        bucket_location=created_artifact.bucket_location,
        bucket_secret_id=bucket_secret_id,
    )
    mock_get_storage_client.return_value.create_upload.return_value = upload_details
    artifact_in = _artifact_create_input(
        manifest_example, [experiment_id, dataset_id, experiment_id]
    )

    result = await handler.create_artifact(
        user_id,
        organization_id,
        orbit_id,
        collection_id,
        artifact_in,
        JWT_SCOPES,
    )

    assert result.artifact == created_artifact
    assert result.artifact.status == ArtifactStatus.PENDING_UPLOAD
    assert "lineage_inputs" not in result.model_dump()["artifact"]
    mock_check_permissions.assert_awaited_once_with(
        organization_id,
        user_id,
        Resource.ARTIFACT,
        Action.CREATE,
        orbit_id,
    )
    mock_get_lineage_inputs.assert_awaited_once_with(
        orbit_id, [experiment_id, dataset_id]
    )
    assert mock_create_artifact.await_args is not None
    create_model = mock_create_artifact.await_args.args[0]
    assert isinstance(create_model, ArtifactCreate)
    assert "lineage_inputs" not in create_model.model_dump()
    mock_link_inputs.assert_awaited_once_with(
        user_id,
        organization_id,
        orbit_id,
        artifact_id,
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
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_organization_artifacts_limit",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.UserRepository.get_public_user_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifacts_by_ids_in_orbit",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.create_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.LineageHandler.link_inputs",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._get_storage_client",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._define_artifact_type",
    return_value=ArtifactType.MODEL,
)
@pytest.mark.asyncio
async def test_create_artifact_rejects_lineage_input_outside_orbit(
    mock_define_artifact_type: Mock,
    mock_get_storage_client: AsyncMock,
    mock_link_inputs: AsyncMock,
    mock_create_artifact: AsyncMock,
    mock_get_lineage_inputs: AsyncMock,
    mock_check_access: AsyncMock,
    mock_check_permissions: AsyncMock,
    mock_get_user: AsyncMock,
    mock_check_limit: AsyncMock,
    lineage_input: UUID,
    manifest_example: Manifest,
) -> None:
    orbit_id = uuid7()
    mock_check_access.return_value = (
        Mock(bucket_secret_id=uuid7()),
        Mock(type=CollectionType.MODEL),
    )
    mock_get_user.return_value = Mock(full_name="Artifact User")
    mock_get_lineage_inputs.return_value = []

    with pytest.raises(ArtifactNotFoundError) as error:
        await handler.create_artifact(
            uuid7(),
            uuid7(),
            orbit_id,
            uuid7(),
            _artifact_create_input(manifest_example, [lineage_input]),
            API_KEY_SCOPES,
        )

    assert error.value.status_code == 404
    assert error.value.message == "Artifact not found"
    mock_get_lineage_inputs.assert_awaited_once_with(orbit_id, [lineage_input])
    mock_create_artifact.assert_not_awaited()
    mock_link_inputs.assert_not_awaited()
    mock_get_storage_client.assert_not_awaited()


@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_organization_artifacts_limit",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.UserRepository.get_public_user_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifacts_by_ids_in_orbit",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.create_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.delete_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.LineageHandler.link_inputs",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._get_storage_client",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._define_artifact_type",
    return_value=ArtifactType.MODEL,
)
@pytest.mark.asyncio
async def test_create_artifact_records_nothing_when_upload_initialization_fails(
    mock_define_artifact_type: Mock,
    mock_get_storage_client: AsyncMock,
    mock_link_inputs: AsyncMock,
    mock_delete_artifact: AsyncMock,
    mock_create_artifact: AsyncMock,
    mock_get_lineage_inputs: AsyncMock,
    mock_check_access: AsyncMock,
    mock_check_permissions: AsyncMock,
    mock_get_user: AsyncMock,
    mock_check_limit: AsyncMock,
    manifest_example: Manifest,
) -> None:
    lineage_input = uuid7()
    mock_check_access.return_value = (
        Mock(bucket_secret_id=uuid7()),
        Mock(type=CollectionType.MODEL),
    )
    mock_get_user.return_value = Mock(full_name="Artifact User")
    mock_get_lineage_inputs.return_value = [Mock(id=lineage_input)]
    mock_get_storage_client.return_value = Mock(
        create_upload=AsyncMock(side_effect=RuntimeError("storage unavailable"))
    )

    with pytest.raises(RuntimeError, match="storage unavailable"):
        await handler.create_artifact(
            uuid7(),
            uuid7(),
            uuid7(),
            uuid7(),
            _artifact_create_input(manifest_example, [lineage_input]),
            API_KEY_SCOPES,
        )

    # The upload is prepared before anything is written: neither an artifact
    # row nor lineage edges are left behind for an upload that never started.
    mock_create_artifact.assert_not_awaited()
    mock_link_inputs.assert_not_awaited()
    mock_delete_artifact.assert_not_awaited()


@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_organization_artifacts_limit",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.UserRepository.get_public_user_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifacts_by_ids_in_orbit",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.create_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.delete_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.LineageHandler.link_inputs",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._get_storage_client",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._define_artifact_type",
    return_value=ArtifactType.MODEL,
)
@pytest.mark.asyncio
async def test_create_artifact_deletes_row_when_lineage_linking_fails(
    mock_define_artifact_type: Mock,
    mock_get_storage_client: AsyncMock,
    mock_link_inputs: AsyncMock,
    mock_delete_artifact: AsyncMock,
    mock_create_artifact: AsyncMock,
    mock_get_lineage_inputs: AsyncMock,
    mock_check_access: AsyncMock,
    mock_check_permissions: AsyncMock,
    mock_get_user: AsyncMock,
    mock_check_limit: AsyncMock,
    manifest_example: Manifest,
) -> None:
    user_id = uuid7()
    organization_id = uuid7()
    orbit_id = uuid7()
    collection_id = uuid7()
    artifact_id = uuid7()
    lineage_input = uuid7()
    created_artifact = _pending_artifact(manifest_example, artifact_id, collection_id)
    mock_check_access.return_value = (
        Mock(bucket_secret_id=uuid7()),
        Mock(type=CollectionType.MODEL),
    )
    mock_get_user.return_value = Mock(full_name="Artifact User")
    mock_get_lineage_inputs.return_value = [Mock(id=lineage_input)]
    mock_create_artifact.return_value = created_artifact
    mock_get_storage_client.return_value = Mock(create_upload=AsyncMock())
    linking_error = ApplicationError("Lineage failed", 409)
    mock_link_inputs.side_effect = linking_error

    with pytest.raises(ApplicationError) as error:
        await handler.create_artifact(
            user_id,
            organization_id,
            orbit_id,
            collection_id,
            _artifact_create_input(manifest_example, [lineage_input]),
            API_KEY_SCOPES,
        )

    assert error.value is linking_error
    mock_delete_artifact.assert_awaited_once_with(artifact_id)
    mock_get_storage_client.assert_awaited_once()


@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.TrackRepository.get_tracks_for_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_artifact(
    mock_get_tracks: AsyncMock,
    mock_get_details: AsyncMock,
    mock_check_orbit_and_collection_access: AsyncMock,
    mock_check_permissions: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    artifact = Mock(collection_id=collection_id)
    mock_get_details.return_value = artifact
    tracks = [Mock()]
    mock_get_tracks.return_value = tracks
    mock_check_orbit_and_collection_access.return_value = (
        Mock(id=orbit_id, organization_id=organization_id),
        Mock(id=collection_id, orbit_id=orbit_id),
    )

    result_artifact = await handler.get_artifact(
        user_id, organization_id, orbit_id, collection_id, artifact_id
    )

    assert result_artifact == artifact
    # Tracks for the artifact are attached to the details response.
    assert result_artifact.tracks == tracks
    mock_get_tracks.assert_awaited_once_with(artifact_id)
    mock_get_details.assert_awaited_once_with(artifact_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ARTIFACT, Action.READ, orbit_id
    )


@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact_details",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_artifact_not_found(
    mock_get_details: AsyncMock,
    mock_check_orbit_and_collection_access: AsyncMock,
    mock_check_permissions: AsyncMock,
) -> None:
    from luml.infra.exceptions import NotFoundError

    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    mock_get_details.return_value = None
    mock_check_orbit_and_collection_access.return_value = (
        Mock(id=orbit_id, organization_id=organization_id),
        Mock(id=collection_id, orbit_id=orbit_id),
    )

    with pytest.raises(NotFoundError) as error:
        await handler.get_artifact(
            user_id, organization_id, orbit_id, collection_id, artifact_id
        )

    assert error.value.status_code == 404
    mock_get_details.assert_awaited_once_with(artifact_id)


@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._get_secret_or_raise",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._get_storage_client",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_request_download_url(
    mock_get_storage_client: AsyncMock,
    mock_get_secret_or_raise: AsyncMock,
    mock_get_artifact: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_check_permissions: AsyncMock,
    test_bucket: S3BucketSecret,
    manifest_example: Manifest,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    artifact = Artifact(
        id=artifact_id,
        collection_id=collection_id,
        file_name="model.luml",
        name=None,
        extra_values={},
        manifest=manifest_example,
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

    mock_secret = test_bucket

    mock_get_artifact.return_value = artifact
    mock_get_orbit_simple.return_value = Mock(
        bucket_secret_id=1, organization_id=organization_id
    )
    mock_get_collection.return_value = Mock(id=collection_id, orbit_id=orbit_id)
    mock_get_secret_or_raise.return_value = mock_secret
    mock_storage_client = AsyncMock()
    mock_storage_client.get_download_url.return_value = "url"
    mock_get_storage_client.return_value = mock_storage_client

    url = await handler.request_download_url(
        user_id, organization_id, orbit_id, collection_id, artifact_id
    )

    assert url == "url"
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ARTIFACT, Action.READ, orbit_id
    )
    mock_get_storage_client.assert_awaited_once()
    mock_storage_client.get_download_url.assert_awaited_once_with(
        artifact.bucket_location
    )


@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.request_deletion",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._get_secret_or_raise",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._get_storage_client",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_request_delete_url(
    mock_get_storage_client: AsyncMock,
    mock_get_secret_or_raise: AsyncMock,
    mock_request_deletion: AsyncMock,
    mock_get_artifact: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_check_permissions: AsyncMock,
    test_bucket: S3BucketSecret,
    manifest_example: Manifest,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")
    bucket_secret_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8621")

    now = datetime.now()

    artifact = ArtifactDetails(
        id=artifact_id,
        collection_id=collection_id,
        file_name="model.luml",
        name=None,
        extra_values={},
        manifest=manifest_example,
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
            id=collection_id,
            orbit_id=orbit_id,
            name="Test Collection",
            description="Test Description",
            type=CollectionType.MODEL,
            tags=[],
            total_artifacts=1,
            created_at=now,
            updated_at=None,
        ),
    )

    mock_secret = test_bucket

    mock_get_artifact.return_value = artifact
    mock_get_orbit_simple.return_value = Mock(
        bucket_secret_id=bucket_secret_id, organization_id=organization_id
    )
    mock_get_collection.return_value = Mock(id=collection_id, orbit_id=orbit_id)
    mock_get_secret_or_raise.return_value = mock_secret
    mock_storage_client = AsyncMock()
    mock_storage_client.get_delete_url.return_value = "url"
    mock_get_storage_client.return_value = mock_storage_client
    mock_request_deletion.return_value = artifact

    url = await handler.request_delete_url(
        user_id, organization_id, orbit_id, collection_id, artifact_id
    )

    assert url == "url"
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ARTIFACT, Action.DELETE, orbit_id
    )
    mock_request_deletion.assert_awaited_once_with(artifact_id, collection_id)
    mock_get_storage_client.assert_awaited_once()
    mock_storage_client.get_delete_url.assert_awaited_once_with(
        artifact.bucket_location
    )


@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.request_deletion",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._get_secret_or_raise",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._get_storage_client",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_request_delete_url_with_deployments(
    mock_get_storage_client: AsyncMock,
    mock_get_secret_or_raise: AsyncMock,
    mock_request_deletion: AsyncMock,
    mock_get_artifact: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_check_permissions: AsyncMock,
    test_bucket: S3BucketSecret,
    manifest_example: Manifest,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")
    bucket_secret_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8621")

    deployment1_id = uuid7()
    satellite_id = uuid7()
    now = datetime.now()

    artifact = ArtifactDetails(
        id=artifact_id,
        collection_id=collection_id,
        file_name="model.luml",
        name=None,
        extra_values={},
        manifest=manifest_example,
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
                id=deployment1_id,
                orbit_id=orbit_id,
                satellite_id=satellite_id,
                satellite_name="Test Satellite",
                name="deployment-1",
                artifact_id=artifact_id,
                artifact_name="model",
                collection_id=collection_id,
                status=DeploymentStatus.ACTIVE,
                created_by_user="Test User",
                created_at=now,
                updated_at=None,
            )
        ],
        collection=Collection(
            id=collection_id,
            orbit_id=orbit_id,
            name="Test Collection",
            description="Test Description",
            type=CollectionType.MODEL,
            tags=[],
            total_artifacts=1,
            created_at=now,
            updated_at=None,
        ),
    )

    mock_secret = test_bucket

    mock_get_artifact.return_value = artifact
    mock_get_orbit_simple.return_value = Mock(
        bucket_secret_id=bucket_secret_id, organization_id=organization_id
    )
    mock_get_collection.return_value = Mock(id=collection_id, orbit_id=orbit_id)
    mock_get_secret_or_raise.return_value = mock_secret
    mock_storage_client = AsyncMock()
    mock_storage_client.get_delete_url.return_value = "url"
    mock_get_storage_client.return_value = mock_storage_client
    mock_request_deletion.side_effect = ArtifactDeployedError()

    with pytest.raises(ApplicationError) as error:
        await handler.request_delete_url(
            user_id, organization_id, orbit_id, collection_id, artifact_id
        )

    assert error.value.status_code == 409
    mock_check_permissions.assert_awaited_once_with(
        organization_id,
        user_id,
        Resource.ARTIFACT,
        Action.DELETE,
        orbit_id,
    )
    mock_get_artifact.assert_awaited_once_with(artifact_id)
    mock_request_deletion.assert_awaited_once_with(artifact_id, collection_id)


@patch(
    "luml.handlers.artifacts.LineageRepository.refresh_node_copy",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.LineageRepository.delete_unreachable_deleted_nodes",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.delete_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.TrackEntryRepository.has_entries_for_artifact",
    new_callable=AsyncMock,
    return_value=False,
)
@patch(
    "luml.handlers.artifacts.LineageRepository.lock_orbit",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.LineageRepository.transaction",
    new=_deletion_transaction,
)
@pytest.mark.asyncio
async def test_confirm_deletion_pending(
    mock_lock_orbit: AsyncMock,
    mock_has_track_entries: AsyncMock,
    mock_delete_artifact: AsyncMock,
    mock_get_artifact: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_check_permissions: AsyncMock,
    mock_delete_unreachable_nodes: AsyncMock,
    mock_refresh_node_copy: AsyncMock,
    manifest_example: Manifest,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    artifact = Artifact(
        id=artifact_id,
        collection_id=collection_id,
        file_name="model.luml",
        name=None,
        extra_values={},
        manifest=manifest_example,
        file_hash="hash",
        file_index={},
        bucket_location="loc",
        size=1,
        unique_identifier="uid",
        status=ArtifactStatus.PENDING_DELETION,
        created_at=datetime.now(),
        updated_at=None,
        type=ArtifactType.MODEL,
    )

    mock_get_artifact.return_value = artifact
    mock_get_orbit_simple.return_value = Mock(
        bucket_secret_id=1, organization_id=organization_id
    )
    mock_get_collection.return_value = Mock(id=collection_id, orbit_id=orbit_id)

    await handler.confirm_deletion(
        user_id, organization_id, orbit_id, collection_id, artifact_id
    )

    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ARTIFACT, Action.DELETE, orbit_id
    )
    mock_get_artifact.assert_awaited_once_with(artifact_id)
    mock_refresh_node_copy.assert_awaited_once_with(artifact_id, DELETION_SESSION)
    mock_delete_artifact.assert_awaited_once_with(artifact_id, DELETION_SESSION)
    mock_delete_unreachable_nodes.assert_awaited_once_with(orbit_id, DELETION_SESSION)


@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.delete_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.TrackEntryRepository.has_entries_for_artifact",
    new_callable=AsyncMock,
    return_value=False,
)
@pytest.mark.asyncio
async def test_confirm_deletion_not_pending(
    mock_has_track_entries: AsyncMock,
    mock_delete: AsyncMock,
    mock_get_model: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_check_permissions: AsyncMock,
    manifest_example: Manifest,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    artifact = Artifact(
        id=artifact_id,
        collection_id=collection_id,
        file_name="model.luml",
        name=None,
        extra_values={},
        manifest=manifest_example,
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

    mock_get_model.return_value = artifact
    mock_get_orbit_simple.return_value = Mock(
        bucket_secret_id=1, organization_id=organization_id
    )
    mock_get_collection.return_value = Mock(id=collection_id, orbit_id=orbit_id)

    with pytest.raises(ApplicationError):
        await handler.confirm_deletion(
            user_id,
            organization_id,
            orbit_id,
            collection_id,
            artifact_id,
        )

    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ARTIFACT, Action.DELETE, orbit_id
    )
    mock_get_model.assert_awaited_once_with(artifact_id)
    mock_delete.assert_not_called()


@patch(
    "luml.handlers.artifacts.LineageRepository.delete_unreachable_deleted_nodes",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.delete_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.LineageRepository.refresh_node_copy",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.LineageRepository.lock_orbit",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.LineageRepository.transaction",
    new=_deletion_transaction,
)
@pytest.mark.asyncio
async def test_physical_artifact_deletion_updates_lineage_in_order(
    mock_lock_orbit: AsyncMock,
    mock_refresh_node_copy: AsyncMock,
    mock_delete_artifact: AsyncMock,
    mock_delete_unreachable_nodes: AsyncMock,
) -> None:
    calls = Mock()
    calls.attach_mock(mock_lock_orbit, "lock")
    calls.attach_mock(mock_refresh_node_copy, "refresh")
    calls.attach_mock(mock_delete_artifact, "delete")
    calls.attach_mock(mock_delete_unreachable_nodes, "cleanup")
    orbit_id = uuid7()
    artifact_id = uuid7()

    await handler._delete_artifact(orbit_id, artifact_id)

    assert calls.mock_calls == [
        call.lock(orbit_id, DELETION_SESSION),
        call.refresh(artifact_id, DELETION_SESSION),
        call.delete(artifact_id, DELETION_SESSION),
        call.cleanup(orbit_id, DELETION_SESSION),
    ]


@patch(
    "luml.handlers.artifacts.LineageRepository.delete_unreachable_deleted_nodes",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.delete_artifact",
    new_callable=AsyncMock,
    side_effect=RuntimeError("delete failed"),
)
@patch(
    "luml.handlers.artifacts.LineageRepository.refresh_node_copy",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.LineageRepository.lock_orbit",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.LineageRepository.transaction",
    new=_deletion_transaction,
)
@pytest.mark.asyncio
async def test_failed_artifact_deletion_does_not_cleanup_lineage_node(
    mock_lock_orbit: AsyncMock,
    mock_refresh_node_copy: AsyncMock,
    mock_delete_artifact: AsyncMock,
    mock_delete_unreachable_nodes: AsyncMock,
) -> None:
    artifact_id = uuid7()

    with pytest.raises(RuntimeError, match="delete failed"):
        await handler._delete_artifact(uuid7(), artifact_id)

    mock_refresh_node_copy.assert_awaited_once_with(artifact_id, DELETION_SESSION)
    mock_delete_artifact.assert_awaited_once_with(artifact_id, DELETION_SESSION)
    mock_delete_unreachable_nodes.assert_not_awaited()


@patch(
    "luml.handlers.artifacts.LineageRepository.delete_unreachable_deleted_nodes",
    new_callable=AsyncMock,
    side_effect=RuntimeError("cleanup failed"),
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.delete_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.LineageRepository.refresh_node_copy",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.LineageRepository.lock_orbit",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.LineageRepository.transaction",
    new=_deletion_transaction,
)
@pytest.mark.asyncio
async def test_failed_lineage_cleanup_rolls_back_the_artifact_deletion(
    mock_lock_orbit: AsyncMock,
    mock_refresh_node_copy: AsyncMock,
    mock_delete_artifact: AsyncMock,
    mock_delete_unreachable_nodes: AsyncMock,
) -> None:
    DELETION_TRANSACTION_ERRORS.clear()
    orbit_id = uuid7()
    artifact_id = uuid7()

    with pytest.raises(RuntimeError, match="cleanup failed"):
        await handler._delete_artifact(orbit_id, artifact_id)

    # The delete was flushed into the same transaction the cleanup broke, so
    # the error rolls the artifact row back instead of reporting a failure
    # for a deletion that already happened.
    mock_delete_artifact.assert_awaited_once_with(artifact_id, DELETION_SESSION)
    mock_delete_unreachable_nodes.assert_awaited_once_with(orbit_id, DELETION_SESSION)
    assert [type(error) for error in DELETION_TRANSACTION_ERRORS] == [RuntimeError]


@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.update_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_artifact(
    mock_update_artifact: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_artifact: AsyncMock,
    mock_check_permissions: AsyncMock,
    manifest_example: Manifest,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    artifact = Artifact(
        id=artifact_id,
        collection_id=collection_id,
        file_name="model.luml",
        name=None,
        extra_values={},
        manifest=manifest_example,
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

    mock_get_artifact.return_value = artifact

    tags = ["t1", "t2"]
    expected = Artifact(
        id=artifact_id,
        collection_id=collection_id,
        file_name="model.luml",
        name=None,
        extra_values={},
        manifest=manifest_example,
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

    mock_update_artifact.return_value = expected
    mock_get_orbit_simple.return_value = Mock(
        bucket_secret_id=1, organization_id=organization_id
    )
    mock_get_collection.return_value = Mock(id=collection_id, orbit_id=orbit_id)

    update_in = ArtifactUpdateIn(tags=tags)
    result = await handler.update_artifact(
        user_id, organization_id, orbit_id, collection_id, artifact_id, update_in
    )

    assert result == expected
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ARTIFACT, Action.UPDATE, orbit_id
    )
    expected_update = ArtifactUpdate(id=artifact_id, name=None, tags=tags)
    mock_update_artifact.assert_awaited_once_with(
        artifact_id,
        collection_id,
        expected_update,
    )


@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.update_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_artifact_not_found(
    mock_update_artifact: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_artifact: AsyncMock,
    mock_check_permissions: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    mock_update_artifact.return_value = None
    mock_get_orbit_simple.return_value = Mock(
        bucket_secret_id=1, organization_id=organization_id
    )
    mock_get_collection.return_value = Mock(id=collection_id, orbit_id=orbit_id)
    mock_get_artifact.return_value = None

    update_in = ArtifactUpdateIn(tags=["t1"])
    with pytest.raises(ArtifactNotFoundError):
        await handler.update_artifact(
            user_id,
            organization_id,
            orbit_id,
            collection_id,
            artifact_id,
            update_in,
        )

    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ARTIFACT, Action.UPDATE, orbit_id
    )
    mock_update_artifact.assert_not_awaited()


@patch("luml.handlers.artifacts.create_storage_client")
@patch(
    "luml.handlers.artifacts.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_storage_client(
    mock_get_bucket_secret: AsyncMock,
    mock_create_storage_client: Mock,
    test_bucket: S3BucketSecret,
) -> None:
    secret_id = UUID("0199c3f7-f040-7f63-9bef-a1f380ae9eeb")

    mock_get_bucket_secret.return_value = test_bucket

    mock_storage_instance = Mock()
    mock_service_class = Mock(return_value=mock_storage_instance)
    mock_create_storage_client.return_value = mock_service_class

    result = await handler._get_storage_client(secret_id)

    mock_get_bucket_secret.assert_awaited_once_with(secret_id)
    mock_create_storage_client.assert_called_once_with(test_bucket.type)
    mock_service_class.assert_called_once_with(test_bucket)
    assert result == mock_storage_instance


@patch(
    "luml.handlers.artifacts.ArtifactRepository.update_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_artifact_invalid_status_transition(
    mock_check_permission: AsyncMock,
    mock_check_orbit_and_collection_access: AsyncMock,
    mock_get_artifact: AsyncMock,
    mock_update_artifact: AsyncMock,
    manifest_example: Manifest,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    existing_artifact = Artifact(
        id=artifact_id,
        collection_id=collection_id,
        file_name="test.tar.gz",
        name="test",
        extra_values={},
        manifest=manifest_example,
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

    mock_check_orbit_and_collection_access.return_value = (
        Mock(id=orbit_id),
        Mock(id=collection_id),
    )
    mock_get_artifact.return_value = existing_artifact

    with pytest.raises(InvalidStatusTransitionError):
        await handler.update_artifact(
            user_id,
            organization_id,
            orbit_id,
            collection_id,
            artifact_id,
            ArtifactUpdateIn(status=ArtifactStatus.UPLOAD_FAILED),
        )

    mock_check_permission.assert_awaited_once_with(
        organization_id, user_id, Resource.ARTIFACT, Action.UPDATE, orbit_id
    )
    mock_update_artifact.assert_not_awaited()


@patch(
    "luml.handlers.artifacts.ArtifactRepository.update_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_artifact_update_failed(
    mock_check_permission: AsyncMock,
    mock_check_orbit_and_collection_access: AsyncMock,
    mock_get_artifact: AsyncMock,
    mock_update_artifact: AsyncMock,
    manifest_example: Manifest,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    existing_artifact = Artifact(
        id=artifact_id,
        collection_id=collection_id,
        file_name="test.tar.gz",
        name="test",
        extra_values={},
        manifest=manifest_example,
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

    mock_check_orbit_and_collection_access.return_value = (
        Mock(id=orbit_id),
        Mock(id=collection_id),
    )
    mock_get_artifact.return_value = existing_artifact
    mock_update_artifact.return_value = None

    with pytest.raises(ArtifactNotFoundError):
        await handler.update_artifact(
            user_id,
            organization_id,
            orbit_id,
            collection_id,
            artifact_id,
            ArtifactUpdateIn(tags=["new_tag"]),
        )

    mock_check_permission.assert_awaited_once_with(
        organization_id, user_id, Resource.ARTIFACT, Action.UPDATE, orbit_id
    )
    mock_update_artifact.assert_awaited_once()


@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_request_download_url_artifact_not_found(
    mock_check_permission: AsyncMock,
    mock_check_orbit_and_collection_access: AsyncMock,
    mock_get_artifact: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    mock_check_orbit_and_collection_access.return_value = (
        Mock(id=orbit_id),
        Mock(id=collection_id),
    )
    mock_get_artifact.return_value = None

    with pytest.raises(ArtifactNotFoundError):
        await handler.request_download_url(
            user_id, organization_id, orbit_id, collection_id, artifact_id
        )

    mock_check_permission.assert_awaited_once_with(
        organization_id, user_id, Resource.ARTIFACT, Action.READ, orbit_id
    )


@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_request_delete_url_artifact_not_found(
    mock_check_permission: AsyncMock,
    mock_check_orbit_and_collection_access: AsyncMock,
    mock_get_artifact: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    mock_check_orbit_and_collection_access.return_value = (
        Mock(id=orbit_id),
        Mock(id=collection_id),
    )
    mock_get_artifact.return_value = None

    with pytest.raises(ArtifactNotFoundError):
        await handler.request_delete_url(
            user_id, organization_id, orbit_id, collection_id, artifact_id
        )

    mock_check_permission.assert_awaited_once_with(
        organization_id, user_id, Resource.ARTIFACT, Action.DELETE, orbit_id
    )


@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_request_delete_url_orbit_not_found(
    mock_check_permission: AsyncMock,
    mock_check_orbit_and_collection_access: AsyncMock,
    mock_get_artifact: AsyncMock,
    mock_get_orbit: AsyncMock,
    test_bucket: S3BucketSecret,
    manifest_example: Manifest,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")
    now = datetime.now()

    artifact = ArtifactDetails(
        id=artifact_id,
        collection_id=collection_id,
        file_name="test.tar.gz",
        name="test",
        extra_values={},
        manifest=manifest_example,
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
            id=collection_id,
            orbit_id=orbit_id,
            name="Test Collection",
            description="Test Description",
            type=CollectionType.MODEL,
            tags=[],
            total_artifacts=1,
            created_at=now,
            updated_at=None,
        ),
    )

    mock_check_orbit_and_collection_access.return_value = (
        Mock(id=orbit_id),
        Mock(id=collection_id),
    )
    mock_get_artifact.return_value = artifact
    mock_get_orbit.return_value = None

    with pytest.raises(OrbitNotFoundError):
        await handler.request_delete_url(
            user_id, organization_id, orbit_id, collection_id, artifact_id
        )

    mock_check_permission.assert_awaited_once_with(
        organization_id, user_id, Resource.ARTIFACT, Action.DELETE, orbit_id
    )


@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_artifact_deletion_checks_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_artifact_details: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    artifact_id = UUID("0199c3f7-f040-7f63-9bef-a1f380ae9eeb")

    mock_get_artifact_details.return_value = None
    mock_get_orbit_simple.return_value = Mock(
        id=orbit_id, organization_id=organization_id
    )
    mock_get_collection.return_value = Mock(id=collection_id, orbit_id=orbit_id)

    with pytest.raises(ArtifactNotFoundError) as error:
        await handler._artifact_deletion_checks(
            user_id, organization_id, orbit_id, collection_id, artifact_id
        )

    assert error.value.status_code == 404
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ARTIFACT, Action.DELETE, orbit_id
    )
    mock_get_artifact_details.assert_awaited_once_with(artifact_id)


@patch(
    "luml.handlers.artifacts.create_storage_client",
)
@patch(
    "luml.handlers.artifacts.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_request_satellite_download_url(
    mock_get_artifact: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_orbit_by_id: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
    mock_storage_client: Mock,
    test_bucket: S3BucketSecret,
) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    artifact_id = UUID("0199c3f7-f040-7f63-9bef-a1f380ae9eeb")
    bucket_location = "orbit-123/collection-456/model.onnx"

    mock_get_artifact.return_value = Mock(
        id=artifact_id,
        collection_id=collection_id,
        bucket_location=bucket_location,
    )
    mock_get_collection.return_value = Mock(orbit_id=orbit_id)
    mock_get_orbit_by_id.return_value = Mock(
        id=orbit_id, bucket_secret_id=test_bucket.id
    )
    mock_get_bucket_secret.return_value = test_bucket

    expected_url = "https://s3.example.com/download/url"

    mock_storage_instance = AsyncMock()
    mock_storage_instance.get_download_url.return_value = expected_url
    mock_service_class = Mock(return_value=mock_storage_instance)
    mock_storage_client.return_value = mock_service_class

    result = await handler.request_satellite_download_url(orbit_id, artifact_id)

    assert result == expected_url
    mock_get_artifact.assert_awaited_once_with(artifact_id)
    mock_get_collection.assert_awaited_once_with(collection_id)
    mock_get_orbit_by_id.assert_awaited_once_with(orbit_id)
    mock_get_bucket_secret.assert_awaited_once_with(test_bucket.id)
    mock_storage_instance.get_download_url.assert_awaited_once_with(bucket_location)


@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_request_satellite_download_url_model_not_found(
    mock_get_artifact: AsyncMock,
) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    artifact_id = UUID("0199c3f7-f040-7f63-9bef-a1f380ae9eeb")

    mock_get_artifact.return_value = None

    with pytest.raises(ArtifactNotFoundError) as error:
        await handler.request_satellite_download_url(orbit_id, artifact_id)

    assert error.value.status_code == 404
    mock_get_artifact.assert_awaited_once_with(artifact_id)


@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_request_satellite_download_url_collection_not_found(
    mock_get_artifact: AsyncMock,
    mock_get_collection: AsyncMock,
) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    artifact_id = UUID("0199c3f7-f040-7f63-9bef-a1f380ae9eeb")

    mock_get_artifact.return_value = Mock(id=artifact_id, collection_id=collection_id)
    mock_get_collection.return_value = None

    with pytest.raises(ArtifactNotFoundError) as error:
        await handler.request_satellite_download_url(orbit_id, artifact_id)

    assert error.value.status_code == 404
    mock_get_artifact.assert_awaited_once_with(artifact_id)
    mock_get_collection.assert_awaited_once_with(collection_id)


@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_request_satellite_download_url_orbit_not_found(
    mock_get_artifact: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_orbit_by_id: AsyncMock,
) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    artifact_id = UUID("0199c3f7-f040-7f63-9bef-a1f380ae9eeb")

    mock_get_artifact.return_value = Mock(id=artifact_id, collection_id=collection_id)
    mock_get_collection.return_value = Mock(id=collection_id, orbit_id=orbit_id)
    mock_get_orbit_by_id.return_value = None

    with pytest.raises(OrbitNotFoundError) as error:
        await handler.request_satellite_download_url(orbit_id, artifact_id)

    assert error.value.status_code == 404
    mock_get_artifact.assert_awaited_once_with(artifact_id)
    mock_get_collection.assert_awaited_once_with(collection_id)
    mock_get_orbit_by_id.assert_awaited_once_with(orbit_id)


@patch(
    "luml.handlers.artifacts.LineageRepository.refresh_node_copy",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.LineageRepository.delete_unreachable_deleted_nodes",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.delete_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.TrackEntryRepository.has_entries_for_artifact",
    new_callable=AsyncMock,
    return_value=False,
)
@patch(
    "luml.handlers.artifacts.LineageRepository.lock_orbit",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.LineageRepository.transaction",
    new=_deletion_transaction,
)
@pytest.mark.asyncio
async def test_force_delete_artifact_without_deployments(
    mock_lock_orbit: AsyncMock,
    mock_has_track_entries: AsyncMock,
    mock_delete_artifact: AsyncMock,
    mock_get_artifact: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_permissions: AsyncMock,
    mock_delete_unreachable_nodes: AsyncMock,
    mock_refresh_node_copy: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    artifact_id = UUID("0199c3f7-f040-7f63-9bef-a1f380ae9eeb")

    mock_get_orbit_simple.return_value = Mock(
        id=orbit_id, organization_id=organization_id
    )
    mock_get_collection.return_value = Mock(id=collection_id, orbit_id=orbit_id)
    mock_get_artifact.return_value = Mock(
        id=artifact_id, collection_id=collection_id, deployments=None
    )

    await handler.force_delete_artifact(
        user_id, organization_id, orbit_id, collection_id, artifact_id
    )
    mock_refresh_node_copy.assert_awaited_once_with(artifact_id, DELETION_SESSION)
    mock_delete_artifact.assert_awaited_once_with(artifact_id, DELETION_SESSION)
    mock_delete_unreachable_nodes.assert_awaited_once_with(orbit_id, DELETION_SESSION)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ARTIFACT, Action.DELETE, orbit_id
    )


@patch(
    "luml.handlers.artifacts.LineageRepository.refresh_node_copy",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.LineageRepository.delete_unreachable_deleted_nodes",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.DeploymentRepository.delete_deployments_by_artifact_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.delete_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.TrackEntryRepository.has_entries_for_artifact",
    new_callable=AsyncMock,
    return_value=False,
)
@patch(
    "luml.handlers.artifacts.LineageRepository.lock_orbit",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.LineageRepository.transaction",
    new=_deletion_transaction,
)
@pytest.mark.asyncio
async def test_force_delete_artifact_with_deployments(
    mock_lock_orbit: AsyncMock,
    mock_has_track_entries: AsyncMock,
    mock_delete_artifact: AsyncMock,
    mock_delete_deployments_by_artifact_id: AsyncMock,
    mock_get_artifact: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_permissions: AsyncMock,
    mock_delete_unreachable_nodes: AsyncMock,
    mock_refresh_node_copy: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    artifact_id = UUID("0199c3f7-f040-7f63-9bef-a1f380ae9eeb")
    deployment_id = UUID("0199c337-09f7-751e-add2-d952f0d6cf4e")

    mock_get_orbit_simple.return_value = Mock(
        id=orbit_id, organization_id=organization_id
    )
    mock_get_collection.return_value = Mock(id=collection_id, orbit_id=orbit_id)
    mock_get_artifact.return_value = Mock(
        id=artifact_id,
        collection_id=collection_id,
        deployments=[Mock(id=deployment_id)],
    )

    await handler.force_delete_artifact(
        user_id, organization_id, orbit_id, collection_id, artifact_id
    )

    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ARTIFACT, Action.DELETE, orbit_id
    )
    mock_delete_deployments_by_artifact_id.assert_awaited_once_with(artifact_id)
    mock_refresh_node_copy.assert_awaited_once_with(artifact_id, DELETION_SESSION)
    mock_delete_artifact.assert_awaited_once_with(artifact_id, DELETION_SESSION)
    mock_delete_unreachable_nodes.assert_awaited_once_with(orbit_id, DELETION_SESSION)


@patch(
    "luml.handlers.artifacts.create_storage_client",
)
@patch(
    "luml.handlers.artifacts.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_satellite_artifact(
    mock_get_artifact: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_orbit_by_id: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
    mock_storage_client: Mock,
    test_bucket: S3BucketSecret,
    manifest_example: Manifest,
) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    artifact_id = UUID("0199c3f7-f040-7f63-9bef-a1f380ae9eeb")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    bucket_location = "test.tar.gz"

    artifact = Artifact(
        id=artifact_id,
        collection_id=collection_id,
        file_name="test.tar.gz",
        name="test",
        extra_values={},
        manifest=manifest_example,
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

    mock_get_artifact.return_value = artifact
    mock_get_collection.return_value = Mock(id=collection_id, orbit_id=orbit_id)
    mock_get_orbit_by_id.return_value = Mock(
        id=orbit_id, bucket_secret_id=test_bucket.id
    )
    mock_get_bucket_secret.return_value = test_bucket

    expected_url = "https://s3.example.com/download/url"
    mock_storage_instance = Mock()
    mock_storage_instance.get_download_url = AsyncMock(return_value=expected_url)
    mock_service_class = Mock(return_value=mock_storage_instance)
    mock_storage_client.return_value = mock_service_class

    result = await handler.get_satellite_artifact(orbit_id, artifact_id)

    assert result.artifact == artifact
    assert result.url == expected_url
    mock_get_artifact.assert_awaited_once_with(artifact_id)
    mock_get_collection.assert_awaited_once_with(collection_id)
    mock_get_orbit_by_id.assert_awaited_once_with(orbit_id)
    mock_get_bucket_secret.assert_awaited_once_with(test_bucket.id)
    mock_storage_instance.get_download_url.assert_awaited_once_with(bucket_location)


@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_satellite_artifact_not_found(
    mock_get_artifact: AsyncMock,
) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    artifact_id = UUID("0199c3f7-f040-7f63-9bef-a1f380ae9eeb")

    mock_get_artifact.return_value = None

    with pytest.raises(ArtifactNotFoundError) as error:
        await handler.get_satellite_artifact(orbit_id, artifact_id)

    assert error.value.status_code == 404
    mock_get_artifact.assert_awaited_once_with(artifact_id)


@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_satellite_artifact_orbit_not_found(
    mock_get_artifact: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_orbit_by_id: AsyncMock,
) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    artifact_id = UUID("0199c3f7-f040-7f63-9bef-a1f380ae9eeb")

    mock_get_artifact.return_value = Mock(id=artifact_id, collection_id=collection_id)
    mock_get_collection.return_value = Mock(id=collection_id, orbit_id=orbit_id)
    mock_get_orbit_by_id.return_value = None

    with pytest.raises(OrbitNotFoundError) as error:
        await handler.get_satellite_artifact(orbit_id, artifact_id)

    assert error.value.status_code == 404
    mock_get_artifact.assert_awaited_once_with(artifact_id)
    mock_get_orbit_by_id.assert_awaited_once_with(orbit_id)


@patch(
    "luml.handlers.artifacts.UserRepository.get_organization_details",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_organization_artifacts_limit_organization_not_found(
    mock_get_organization_details: AsyncMock,
) -> None:
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")

    mock_get_organization_details.return_value = None

    with pytest.raises(NotFoundError) as error:
        await handler._check_organization_artifacts_limit(organization_id)

    assert error.value.status_code == 404
    mock_get_organization_details.assert_awaited_once_with(organization_id)


@patch(
    "luml.handlers.artifacts.UserRepository.get_organization_details",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_organization_artifacts_limit_reached(
    mock_get_organization_details: AsyncMock,
) -> None:
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")

    mock_get_organization_details.return_value = Mock(
        total_artifacts=100,
        artifacts_limit=100,
    )

    with pytest.raises(OrganizationLimitReachedError) as error:
        await handler._check_organization_artifacts_limit(organization_id)

    assert error.value.status_code == 409
    mock_get_organization_details.assert_awaited_once_with(organization_id)


@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_collection_artifacts_extra_values",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_is_metric_sort_extra_values_error(
    mock_get_extra_values: AsyncMock,
) -> None:
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    with pytest.raises(InvalidSortingError) as error:
        await handler._is_metric_sort(collection_id, "extra_values")

    assert error.value.status_code == 400
    mock_get_extra_values.assert_not_awaited()


@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_collection_artifacts_extra_values",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_is_metric_sort_custom_metric_found(
    mock_get_extra_values: AsyncMock,
) -> None:
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    mock_get_extra_values.return_value = {"accuracy", "precision", "recall"}

    result = await handler._is_metric_sort(collection_id, "accuracy")

    assert result is True
    mock_get_extra_values.assert_awaited_once_with(collection_id)


@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_collection_artifacts_extra_values",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_is_metric_sort_custom_metric_not_found(
    mock_get_extra_values: AsyncMock,
) -> None:
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    mock_get_extra_values.return_value = {"accuracy", "precision"}

    with pytest.raises(InvalidSortingError) as error:
        await handler._is_metric_sort(collection_id, "unknown_metric")

    assert error.value.status_code == 400
    mock_get_extra_values.assert_awaited_once_with(collection_id)


def test_define_artifact_type_with_luml_manifest() -> None:
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


def test_define_artifact_type_with_luml_manifest_unsupported_type() -> None:
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


def test_define_artifact_type_from_file_structure() -> None:
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


def test_define_artifact_type_cannot_determine() -> None:
    artifact = Mock(
        manifest=Mock(spec=[]),
        file_index={"random_file.txt": "content"},
    )

    with pytest.raises(
        ArtifactTypeMismatchError, match="Could not define artifact type"
    ):
        ArtifactHandler._define_artifact_type(artifact)


@patch(
    "luml.handlers.artifacts.UserRepository.get_public_user_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_organization_artifacts_limit",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._define_artifact_type",
    return_value=ArtifactType.MODEL,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_artifact_type_not_allowed(
    mock_check_permissions: AsyncMock,
    mock_check_orbit_and_collection_access: AsyncMock,
    mock_define_artifact_type: Mock,
    mock_check_organization_artifacts_limit: AsyncMock,
    mock_get_public_user_by_id: AsyncMock,
    manifest_example: Manifest,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    bucket_secret_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8345")

    mock_check_orbit_and_collection_access.return_value = (
        Mock(bucket_secret_id=bucket_secret_id, organization_id=organization_id),
        Mock(orbit_id=orbit_id, type=CollectionType.DATASET),
    )

    artifact_in = ArtifactCreateIn(
        extra_values={},
        manifest=manifest_example,
        file_hash="hash",
        file_index={},
        size=1,
        file_name="file.txt",
        name=None,
        tags=["tag"],
    )

    with pytest.raises(ArtifactTypeMismatchError):
        await handler.create_artifact(
            user_id,
            organization_id,
            orbit_id,
            collection_id,
            artifact_in,
            API_KEY_SCOPES,
        )

    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ARTIFACT, Action.CREATE, orbit_id
    )
    mock_check_orbit_and_collection_access.assert_awaited_once_with(
        organization_id, orbit_id, collection_id
    )
    mock_check_organization_artifacts_limit.assert_not_awaited()


@patch(
    "luml.handlers.artifacts.UserRepository.get_public_user_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_organization_artifacts_limit",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._define_artifact_type",
    return_value=ArtifactType.MODEL,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_artifact_user_not_found(
    mock_check_permissions: AsyncMock,
    mock_check_orbit_and_collection_access: AsyncMock,
    mock_define_artifact_type: Mock,
    mock_check_organization_artifacts_limit: AsyncMock,
    mock_get_public_user_by_id: AsyncMock,
    manifest_example: Manifest,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    bucket_secret_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8345")

    mock_check_orbit_and_collection_access.return_value = (
        Mock(bucket_secret_id=bucket_secret_id, organization_id=organization_id),
        Mock(orbit_id=orbit_id, type=CollectionType.MODEL),
    )
    mock_get_public_user_by_id.return_value = None

    artifact_in = ArtifactCreateIn(
        extra_values={},
        manifest=manifest_example,
        file_hash="hash",
        file_index={},
        size=1,
        file_name="file.txt",
        name=None,
        tags=["tag"],
    )

    with pytest.raises(NotFoundError, match="User not found"):
        await handler.create_artifact(
            user_id,
            organization_id,
            orbit_id,
            collection_id,
            artifact_in,
            API_KEY_SCOPES,
        )
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.ARTIFACT, Action.CREATE, orbit_id
    )
    mock_check_orbit_and_collection_access.assert_awaited_once_with(
        organization_id, orbit_id, collection_id
    )
    mock_check_organization_artifacts_limit.assert_awaited_once_with(organization_id)
    mock_get_public_user_by_id.assert_awaited_once_with(user_id)


@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_collection_artifacts_extra_values",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_is_metric_sort_standard_column(
    mock_get_extra_values: AsyncMock,
) -> None:
    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")

    result = await handler._is_metric_sort(collection_id, "created_at")

    assert result is False
    mock_get_extra_values.assert_not_awaited()


def test_validate_cursor_matching() -> None:
    from luml.schemas.general import Cursor

    collection_id = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
    artifact_id = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")

    cursor = Cursor(
        id=artifact_id,
        value=None,
        sort_by="created_at",
        order=SortOrder.DESC,
        scope_id=collection_id,
    )

    result = ArtifactHandler._validate_cursor(
        cursor, "created_at", SortOrder.DESC, collection_id
    )

    assert result is cursor


_ORG = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
_ORBIT = UUID("0199c337-09f3-753e-9def-b27745e69be6")
_USER = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
_COLLECTION = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
_ARTIFACT = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")
# Collection and orbit of another tenant, addressable only by guessing their UUID.
_FOREIGN_COLLECTION = UUID("0199c337-09f5-7c3d-8a11-4e2b9d7c6f01")
_FOREIGN_ORBIT = UUID("0199c337-09f6-7b8e-9c22-5f3c8e6d7a02")


def _make_artifact(manifest: Manifest, collection_id: UUID) -> Artifact:
    return Artifact(
        id=_ARTIFACT,
        collection_id=collection_id,
        file_name="foreign.luml",
        name="foreign",
        extra_values={},
        manifest=manifest,
        file_hash="hash",
        file_index={},
        bucket_location="foreign/loc",
        size=1,
        unique_identifier="uid",
        tags=None,
        status=ArtifactStatus.UPLOADED,
        created_at=datetime.now(),
        updated_at=None,
        type=ArtifactType.MODEL,
    )


@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._get_storage_client",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.request_deletion",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_request_delete_url_blocked_by_tracks(
    mock_request_deletion: AsyncMock,
    mock_get_storage_client: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_artifact: AsyncMock,
    mock_check_access: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    mock_check_access.return_value = None
    artifact = Mock(id=_ARTIFACT, collection_id=_COLLECTION, bucket_location="loc")
    mock_get_artifact.return_value = artifact
    mock_get_orbit_simple.return_value = Mock(id=_ORBIT, bucket_secret_id=uuid7())
    mock_get_storage_client.return_value = AsyncMock(
        get_delete_url=AsyncMock(return_value="url")
    )
    mock_request_deletion.side_effect = ArtifactTrackedError()

    with pytest.raises(
        ApplicationError, match="referenced by one or more tracks"
    ) as exc:
        await handler.request_delete_url(_USER, _ORG, _ORBIT, _COLLECTION, _ARTIFACT)
    assert exc.value.status_code == 409
    mock_request_deletion.assert_awaited_once_with(_ARTIFACT, _COLLECTION)


@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._get_storage_client",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.request_deletion",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_request_delete_url_artifact_gone_before_lock(
    mock_request_deletion: AsyncMock,
    mock_get_storage_client: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_artifact: AsyncMock,
    mock_check_access: AsyncMock,
    mock_perms: AsyncMock,
) -> None:
    # The artifact was read, but a concurrent deletion removed it before the
    # locked status change: the request answers 404, not a server error.
    mock_check_access.return_value = None
    mock_get_artifact.return_value = Mock(
        id=_ARTIFACT, collection_id=_COLLECTION, bucket_location="loc"
    )
    mock_get_orbit_simple.return_value = Mock(id=_ORBIT, bucket_secret_id=uuid7())
    mock_get_storage_client.return_value = AsyncMock(
        get_delete_url=AsyncMock(return_value="url")
    )
    mock_request_deletion.return_value = None

    with pytest.raises(ArtifactNotFoundError):
        await handler.request_delete_url(_USER, _ORG, _ORBIT, _COLLECTION, _ARTIFACT)


@patch(
    "luml.handlers.artifacts.ArtifactHandler._get_storage_client",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_request_download_url_rejects_artifact_from_another_collection(
    mock_check_permissions: AsyncMock,
    mock_check_access: AsyncMock,
    mock_get_artifact: AsyncMock,
    mock_get_storage_client: AsyncMock,
) -> None:
    mock_check_access.return_value = (Mock(id=_ORBIT), Mock(id=_COLLECTION))
    mock_get_artifact.return_value = Mock(
        id=_ARTIFACT, collection_id=_FOREIGN_COLLECTION, bucket_location="foreign/loc"
    )

    with pytest.raises(ArtifactNotFoundError) as error:
        await handler.request_download_url(_USER, _ORG, _ORBIT, _COLLECTION, _ARTIFACT)

    assert error.value.status_code == 404
    mock_get_storage_client.assert_not_awaited()


@patch(
    "luml.handlers.artifacts.ArtifactRepository.request_deletion",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._get_storage_client",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_request_delete_url_rejects_artifact_from_another_collection(
    mock_check_permissions: AsyncMock,
    mock_check_access: AsyncMock,
    mock_get_details: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_storage_client: AsyncMock,
    mock_request_deletion: AsyncMock,
) -> None:
    mock_check_access.return_value = (Mock(id=_ORBIT), Mock(id=_COLLECTION))
    mock_get_orbit_simple.return_value = Mock(id=_ORBIT, bucket_secret_id=uuid7())
    mock_get_details.return_value = Mock(
        id=_ARTIFACT,
        collection_id=_FOREIGN_COLLECTION,
        bucket_location="foreign/loc",
        deployments=None,
    )

    with pytest.raises(ArtifactNotFoundError) as error:
        await handler.request_delete_url(_USER, _ORG, _ORBIT, _COLLECTION, _ARTIFACT)

    assert error.value.status_code == 404
    mock_get_storage_client.assert_not_awaited()
    mock_request_deletion.assert_not_awaited()


@patch(
    "luml.handlers.artifacts.ArtifactRepository.update_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_artifact_rejects_artifact_from_another_collection(
    mock_check_permissions: AsyncMock,
    mock_check_access: AsyncMock,
    mock_get_artifact: AsyncMock,
    mock_update_artifact: AsyncMock,
) -> None:
    mock_check_access.return_value = (Mock(id=_ORBIT), Mock(id=_COLLECTION))
    mock_get_artifact.return_value = Mock(
        id=_ARTIFACT,
        collection_id=_FOREIGN_COLLECTION,
        status=ArtifactStatus.UPLOADED,
    )

    # UPLOADED -> UPLOADED is an illegal transition, so an unscoped read would
    # answer 400 and confirm the foreign artifact's status.
    with pytest.raises(ArtifactNotFoundError) as error:
        await handler.update_artifact(
            _USER,
            _ORG,
            _ORBIT,
            _COLLECTION,
            _ARTIFACT,
            ArtifactUpdateIn(status=ArtifactStatus.UPLOADED),
        )

    assert error.value.status_code == 404
    mock_update_artifact.assert_not_awaited()


@patch(
    "luml.handlers.artifacts.TrackEntryRepository.has_entries_for_artifact",
    new_callable=AsyncMock,
    return_value=False,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_artifact_deletion_checks_rejects_artifact_from_another_collection(
    mock_check_permissions: AsyncMock,
    mock_check_access: AsyncMock,
    mock_get_details: AsyncMock,
    mock_has_entries: AsyncMock,
) -> None:
    mock_check_access.return_value = (Mock(id=_ORBIT), Mock(id=_COLLECTION))
    mock_get_details.return_value = Mock(
        id=_ARTIFACT, collection_id=_FOREIGN_COLLECTION, deployments=None
    )

    with pytest.raises(ArtifactNotFoundError) as error:
        await handler._artifact_deletion_checks(
            _USER, _ORG, _ORBIT, _COLLECTION, _ARTIFACT
        )

    assert error.value.status_code == 404
    mock_has_entries.assert_not_awaited()


@patch(
    "luml.handlers.artifacts.ArtifactRepository.delete_artifact",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.DeploymentRepository.delete_deployments_by_artifact_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.TrackEntryRepository.has_entries_for_artifact",
    new_callable=AsyncMock,
    return_value=False,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler._check_orbit_and_collection_access",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_force_delete_artifact_rejects_artifact_from_another_collection(
    mock_check_permissions: AsyncMock,
    mock_check_access: AsyncMock,
    mock_get_details: AsyncMock,
    mock_has_entries: AsyncMock,
    mock_delete_deployments: AsyncMock,
    mock_delete_artifact: AsyncMock,
) -> None:
    mock_check_access.return_value = (Mock(id=_ORBIT), Mock(id=_COLLECTION))
    mock_get_details.return_value = Mock(
        id=_ARTIFACT,
        collection_id=_FOREIGN_COLLECTION,
        deployments=[Mock(id=uuid7())],
    )

    with pytest.raises(ArtifactNotFoundError) as error:
        await handler.force_delete_artifact(_USER, _ORG, _ORBIT, _COLLECTION, _ARTIFACT)

    assert error.value.status_code == 404
    mock_delete_deployments.assert_not_awaited()
    mock_delete_artifact.assert_not_awaited()


@patch(
    "luml.handlers.artifacts.ArtifactHandler._get_storage_client",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_satellite_artifact_rejects_artifact_outside_orbit(
    mock_get_artifact: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_orbit_by_id: AsyncMock,
    mock_get_storage_client: AsyncMock,
    manifest_example: Manifest,
) -> None:
    mock_get_artifact.return_value = _make_artifact(
        manifest_example, _FOREIGN_COLLECTION
    )
    mock_get_collection.return_value = Mock(
        id=_FOREIGN_COLLECTION, orbit_id=_FOREIGN_ORBIT
    )
    mock_get_orbit_by_id.return_value = Mock(id=_ORBIT, bucket_secret_id=uuid7())
    mock_get_storage_client.return_value.get_download_url.return_value = "url"

    with pytest.raises(ArtifactNotFoundError) as error:
        await handler.get_satellite_artifact(_ORBIT, _ARTIFACT)

    assert error.value.status_code == 404
    mock_get_collection.assert_awaited_once_with(_FOREIGN_COLLECTION)
    mock_get_orbit_by_id.assert_not_awaited()
    mock_get_storage_client.assert_not_awaited()


@patch(
    "luml.handlers.artifacts.ArtifactHandler._get_storage_client",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.OrbitRepository.get_orbit_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.CollectionRepository.get_collection",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.artifacts.ArtifactRepository.get_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_satellite_artifact_collection_not_found(
    mock_get_artifact: AsyncMock,
    mock_get_collection: AsyncMock,
    mock_get_orbit_by_id: AsyncMock,
    mock_get_storage_client: AsyncMock,
    manifest_example: Manifest,
) -> None:
    mock_get_artifact.return_value = _make_artifact(
        manifest_example, _FOREIGN_COLLECTION
    )
    mock_get_collection.return_value = None
    mock_get_orbit_by_id.return_value = Mock(id=_ORBIT, bucket_secret_id=uuid7())
    mock_get_storage_client.return_value.get_download_url.return_value = "url"

    with pytest.raises(ArtifactNotFoundError) as error:
        await handler.get_satellite_artifact(_ORBIT, _ARTIFACT)

    assert error.value.status_code == 404
    mock_get_storage_client.assert_not_awaited()
