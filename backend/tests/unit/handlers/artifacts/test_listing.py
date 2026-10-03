from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid7

import pytest
from luml.handlers.artifacts import ArtifactHandler
from luml.infra.exceptions import ApplicationError, InvalidSortingError
from luml.schemas.artifacts import (
    ArtifactListed,
    ArtifactsList,
    ArtifactStatus,
    ArtifactType,
    Manifest,
)
from luml.schemas.deployment import DeploymentBase, DeploymentStatus
from luml.schemas.general import Cursor, PaginationParams, SortOrder
from luml.schemas.permissions import Action, Resource
from luml.utils.pagination import build_scope_id, encode_cursor

from tests.support.ids import (
    ARTIFACT_ID,
    COLLECTION_ID,
    DEPLOYMENT_ID,
    ORBIT_ID,
    ORGANIZATION_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.artifacts.conftest import _make_listed, _pagination_arg


class TestArtifactListing:
    @pytest.fixture(autouse=True)
    def check_access(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        monkeypatch: pytest.MonkeyPatch,
    ) -> AsyncMock:
        check_access = AsyncMock()
        monkeypatch.setattr(
            mocks.handler, "_check_orbit_and_collections_access", check_access
        )
        return check_access

    @pytest.mark.parametrize("cursor", ["garbage", "WzFd"])
    async def test_get_collection_artifacts_raises_bad_request_when_cursor_is_invalid(
        self, mocks: CollaboratorMocks[ArtifactHandler], cursor: str
    ) -> None:
        with pytest.raises(ApplicationError, match="^Invalid cursor$") as error:
            await mocks.handler.get_collection_artifacts(
                uuid7(), uuid7(), uuid7(), cursor_str=cursor
            )

        assert error.value.status_code == 400
        mocks.repository.get_collection_artifacts.assert_not_called()

    async def test_get_collection_artifacts_returns_repository_page(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        check_access: AsyncMock,
        manifest: Manifest,
    ) -> None:
        expected_models_list = [
            ArtifactListed.model_validate(
                {
                    "id": ARTIFACT_ID,
                    "collection_id": COLLECTION_ID,
                    "collection": {"name": "model1-collection"},
                    "file_name": "model1.pkl",
                    "name": "model1",
                    "extra_values": {"accuracy": 0.95},
                    "manifest": manifest,
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
                            id=DEPLOYMENT_ID,
                            name="test",
                            status=DeploymentStatus.ACTIVE,
                            orbit_id=ORBIT_ID,
                        )
                    ],
                }
            )
        ]
        expected = ArtifactsList(items=expected_models_list, cursor=None)

        mocks.repository.get_collection_artifacts.return_value = (
            expected_models_list,
            None,
        )

        result = await mocks.handler.get_collection_artifacts(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, [COLLECTION_ID]
        )

        assert result == expected
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.LIST, ORBIT_ID
        )
        check_access.assert_awaited_once_with(
            ORGANIZATION_ID, ORBIT_ID, [COLLECTION_ID]
        )
        mocks.repository.get_collection_artifacts.assert_awaited_once_with(
            orbit_id=ORBIT_ID,
            pagination=PaginationParams(
                cursor=None,
                sort_by="created_at",
                scope_id=build_scope_id(
                    orbit_id=ORBIT_ID,
                    collection_ids=[COLLECTION_ID],
                    artifact_types=None,
                    search=None,
                    excluded_tracks=None,
                ),
                order=SortOrder.DESC,
                limit=100,
                extra_sort_field=None,
            ),
            collection_ids=[COLLECTION_ID],
            artifact_types=None,
            search=None,
            excluded_tracks=None,
        )

    async def test_get_collection_artifacts_forwards_filters_to_repository(
        self, mocks: CollaboratorMocks[ArtifactHandler], check_access: AsyncMock
    ) -> None:
        collection_ids = [uuid7(), uuid7()]
        artifact_types = [ArtifactType.MODEL, ArtifactType.DATASET]
        excluded_tracks = [uuid7()]
        mocks.repository.get_collection_artifacts.return_value = ([], None)

        await mocks.handler.get_collection_artifacts(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            collection_ids,
            artifact_types,
            search="resnet",
            excluded_tracks=excluded_tracks,
        )

        expected_scope = build_scope_id(
            orbit_id=ORBIT_ID,
            collection_ids=collection_ids,
            artifact_types=artifact_types,
            search="resnet",
            excluded_tracks=excluded_tracks,
        )
        check_access.assert_awaited_once_with(ORGANIZATION_ID, ORBIT_ID, collection_ids)
        mocks.repository.get_collection_artifacts.assert_awaited_once_with(
            orbit_id=ORBIT_ID,
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

    @pytest.mark.parametrize(
        ("sort_by", "cursor_value"),
        [("created_at", datetime(2026, 9, 16)), ("accuracy", 0.8)],
    )
    async def test_get_collection_artifacts_reuses_cursor_when_scope_and_sort_match(
        self,
        mocks: CollaboratorMocks[ArtifactHandler],
        sort_by: str,
        cursor_value: datetime | float,
    ) -> None:
        cursor_id = uuid7()
        scope = build_scope_id(
            orbit_id=ORBIT_ID,
            collection_ids=None,
            artifact_types=None,
            search=None,
            excluded_tracks=None,
        )
        cursor_str = encode_cursor(
            Cursor(
                id=cursor_id,
                value=cursor_value,
                sort_by=sort_by,
                order=SortOrder.DESC,
                scope_id=scope,
            )
        )
        mocks.repository.get_collection_artifacts.return_value = ([], None)

        await mocks.handler.get_collection_artifacts(
            uuid7(), uuid7(), ORBIT_ID, cursor_str=cursor_str, sort_by=sort_by
        )

        pagination = _pagination_arg(mocks.repository.get_collection_artifacts)
        assert pagination.cursor is not None
        assert pagination.cursor.id == cursor_id

    async def test_get_collection_artifacts_resets_cursor_when_scope_changes(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        stale_scope = build_scope_id(
            orbit_id=ORBIT_ID,
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
        mocks.repository.get_collection_artifacts.return_value = ([], None)

        await mocks.handler.get_collection_artifacts(
            uuid7(), uuid7(), ORBIT_ID, cursor_str=cursor_str
        )

        assert _pagination_arg(mocks.repository.get_collection_artifacts).cursor is None

    async def test_get_collection_artifacts_resets_cursor_when_sort_column_changes(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        scope = build_scope_id(
            orbit_id=ORBIT_ID,
            collection_ids=None,
            artifact_types=None,
            search=None,
            excluded_tracks=None,
        )
        cursor_str = encode_cursor(
            Cursor(
                id=uuid7(),
                value="some-name",
                sort_by="name",
                order=SortOrder.DESC,
                scope_id=scope,
            )
        )
        mocks.repository.get_collection_artifacts.return_value = ([], None)

        await mocks.handler.get_collection_artifacts(
            uuid7(), uuid7(), ORBIT_ID, cursor_str=cursor_str, sort_by="created_at"
        )

        assert _pagination_arg(mocks.repository.get_collection_artifacts).cursor is None

    async def test_get_collection_artifacts_returns_first_page_when_cursor_is_empty(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        mocks.repository.get_collection_artifacts.return_value = ([], None)

        result = await mocks.handler.get_collection_artifacts(
            uuid7(), uuid7(), uuid7(), cursor_str=""
        )

        assert result == ArtifactsList(items=[], cursor=None)
        assert _pagination_arg(mocks.repository.get_collection_artifacts).cursor is None

    async def test_get_collection_artifacts_truncates_items_to_limit(
        self, mocks: CollaboratorMocks[ArtifactHandler], manifest: Manifest
    ) -> None:
        items = [_make_listed(manifest) for _ in range(3)]
        mocks.repository.get_collection_artifacts.return_value = (items, None)

        result = await mocks.handler.get_collection_artifacts(
            uuid7(), uuid7(), uuid7(), limit=2
        )

        assert len(result.items) == 2
        assert result.items == items[:2]

    async def test_get_collection_artifacts_returns_encoded_next_cursor(
        self, mocks: CollaboratorMocks[ArtifactHandler], manifest: Manifest
    ) -> None:
        next_cursor = Cursor(
            id=uuid7(),
            value=datetime.now(),
            sort_by="created_at",
            order=SortOrder.DESC,
            scope_id=uuid7(),
        )
        mocks.repository.get_collection_artifacts.return_value = (
            [_make_listed(manifest)],
            next_cursor,
        )

        result = await mocks.handler.get_collection_artifacts(uuid7(), uuid7(), uuid7())

        assert result.cursor == encode_cursor(next_cursor)

    async def test_is_metric_sort_raises_invalid_sorting_when_sorting_by_extra_values(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        with pytest.raises(InvalidSortingError) as error:
            await mocks.handler._is_metric_sort(COLLECTION_ID, "extra_values")

        assert error.value.status_code == 400
        mocks.repository.get_collection_artifacts_extra_values.assert_not_awaited()

    async def test_is_metric_sort_returns_true_when_metric_exists(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        mocks.repository.get_collection_artifacts_extra_values.return_value = {
            "accuracy",
            "precision",
            "recall",
        }

        result = await mocks.handler._is_metric_sort(COLLECTION_ID, "accuracy")

        assert result is True
        mocks.repository.get_collection_artifacts_extra_values.assert_awaited_once_with(
            COLLECTION_ID
        )

    async def test_is_metric_sort_raises_invalid_sorting_when_metric_is_unknown(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        mocks.repository.get_collection_artifacts_extra_values.return_value = {
            "accuracy",
            "precision",
        }

        with pytest.raises(InvalidSortingError) as error:
            await mocks.handler._is_metric_sort(COLLECTION_ID, "unknown_metric")

        assert error.value.status_code == 400
        mocks.repository.get_collection_artifacts_extra_values.assert_awaited_once_with(
            COLLECTION_ID
        )

    async def test_is_metric_sort_returns_false_when_column_is_standard(
        self, mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        result = await mocks.handler._is_metric_sort(COLLECTION_ID, "created_at")

        assert result is False
        mocks.repository.get_collection_artifacts_extra_values.assert_not_awaited()

    def test_validate_cursor_returns_cursor_when_scope_sort_and_order_match(
        self,
    ) -> None:
        cursor = Cursor(
            id=ARTIFACT_ID,
            value=None,
            sort_by="created_at",
            order=SortOrder.DESC,
            scope_id=COLLECTION_ID,
        )

        result = ArtifactHandler._validate_cursor(
            cursor, "created_at", SortOrder.DESC, COLLECTION_ID
        )

        assert result is cursor
