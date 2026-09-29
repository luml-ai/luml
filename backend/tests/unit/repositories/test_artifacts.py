from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid7

import pytest
from luml.infra.exceptions import InvalidSortingError
from luml.models.artifacts import ArtifactOrm
from luml.repositories.artifacts import ArtifactRepository
from luml.schemas.artifacts import ArtifactSortBy
from luml.schemas.general import PaginationParams, SortOrder


@pytest.mark.asyncio
@pytest.mark.parametrize("sort_by", list(ArtifactSortBy))
async def test_is_extra_values_sort_accepts_artifact_sort_fields(
    sort_by: ArtifactSortBy,
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


@pytest.mark.asyncio
@pytest.mark.parametrize("sort_by", ["nonexistent_zzz", "collection_name", "metadata"])
async def test_is_extra_values_sort_rejects_invalid_fields(sort_by: str) -> None:
    repository = ArtifactRepository(Mock())

    with (
        patch.object(
            repository,
            "get_batch_collection_artifacts_extra_values",
            new_callable=AsyncMock,
            return_value=[],
        ) as get_metrics,
        pytest.raises(InvalidSortingError, match=f"Invalid sorting column: {sort_by}"),
    ):
        await repository._is_extra_values_sort([], sort_by)

    get_metrics.assert_awaited_once_with([])


@pytest.mark.asyncio
async def test_is_extra_values_sort_accepts_collection_metric() -> None:
    repository = ArtifactRepository(Mock())
    collection_ids = [uuid7()]

    with patch.object(
        repository,
        "get_batch_collection_artifacts_extra_values",
        new_callable=AsyncMock,
        return_value=["accuracy"],
    ) as get_metrics:
        result = await repository._is_extra_values_sort(collection_ids, "accuracy")

    assert result is True
    get_metrics.assert_awaited_once_with(collection_ids)


def test_metric_sort_cursor_keeps_requested_sort_column() -> None:
    artifact = ArtifactOrm(id=uuid7(), extra_values={"accuracy": 0.9})
    scope_id = uuid7()
    pagination = PaginationParams(
        sort_by="extra_values",
        extra_sort_field="accuracy",
        order=SortOrder.DESC,
        scope_id=scope_id,
    )

    cursor = ArtifactRepository._get_cursor_from_record(
        artifact, pagination, is_extra_value=True
    )

    assert cursor.id == artifact.id
    assert cursor.value == 0.9
    assert cursor.sort_by == "accuracy"
    assert cursor.order == SortOrder.DESC
    assert cursor.scope_id == scope_id
