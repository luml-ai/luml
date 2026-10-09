from unittest.mock import AsyncMock, Mock, patch

import pytest
from luml.infra.exceptions import InvalidSortingError
from luml.models.artifacts import ArtifactOrm
from luml.repositories.artifacts import ArtifactRepository
from luml.schemas.artifacts import ArtifactSortBy
from luml.schemas.general import PaginationParams, SortOrder

from tests.support.ids import ARTIFACT_ID, COLLECTION_ID


class TestArtifactRepository:
    @pytest.mark.parametrize("sort_by", list(ArtifactSortBy))
    async def test_is_extra_values_sort_returns_false_when_artifact_field(
        self, sort_by: ArtifactSortBy
    ) -> None:
        repository = ArtifactRepository(Mock())

        with patch.object(
            repository,
            "get_batch_collection_artifacts_extra_values",
            new_callable=AsyncMock,
        ) as get_metrics:
            result = await repository._is_extra_values_sort([], sort_by.value)

        assert result is False
        get_metrics.assert_not_awaited()

    @pytest.mark.parametrize(
        "sort_by", ["nonexistent_zzz", "collection_name", "metadata"]
    )
    async def test_is_extra_values_sort_raises_invalid_sorting_error_when_unknown_field(
        self, sort_by: str
    ) -> None:
        repository = ArtifactRepository(Mock())

        with (
            patch.object(
                repository,
                "get_batch_collection_artifacts_extra_values",
                new_callable=AsyncMock,
                return_value=[],
            ) as get_metrics,
            pytest.raises(
                InvalidSortingError, match=f"Invalid sorting column: {sort_by}"
            ),
        ):
            await repository._is_extra_values_sort([], sort_by)

        get_metrics.assert_awaited_once_with([])

    async def test_is_extra_values_sort_returns_true_when_collection_metric(
        self,
    ) -> None:
        repository = ArtifactRepository(Mock())
        collection_ids = [COLLECTION_ID]

        with patch.object(
            repository,
            "get_batch_collection_artifacts_extra_values",
            new_callable=AsyncMock,
            return_value=["accuracy"],
        ) as get_metrics:
            result = await repository._is_extra_values_sort(collection_ids, "accuracy")

        assert result is True
        get_metrics.assert_awaited_once_with(collection_ids)

    def test_get_cursor_from_record_keeps_requested_sort_column_when_extra_value_sort(
        self,
    ) -> None:
        artifact = ArtifactOrm(id=ARTIFACT_ID, extra_values={"accuracy": 0.9})
        pagination = PaginationParams(
            sort_by="extra_values",
            extra_sort_field="accuracy",
            order=SortOrder.DESC,
            scope_id=COLLECTION_ID,
        )

        cursor = ArtifactRepository._get_cursor_from_record(
            artifact, pagination, is_extra_value=True
        )

        assert cursor.id == artifact.id
        assert cursor.value == 0.9
        assert cursor.sort_by == "accuracy"
        assert cursor.order == SortOrder.DESC
        assert cursor.scope_id == COLLECTION_ID
