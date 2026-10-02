from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest
from luml.repositories.lineage import LineageRepository
from luml.schemas.artifacts import ArtifactType
from sqlalchemy.ext.asyncio import AsyncSession

from tests.support.ids import ARTIFACT_ID, ORBIT_ID


class TestLineageRepository:
    async def test_get_or_create_node_raises_runtime_error_when_node_missing(
        self,
    ) -> None:
        mock_session = Mock(spec=AsyncSession)
        mock_session.execute = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=None)
        mock_session.flush = AsyncMock()
        artifact = Mock()
        artifact.id = ARTIFACT_ID
        artifact.name = "model"
        artifact.type = ArtifactType.MODEL
        artifact.collection_name = "Models"
        repository = LineageRepository(Mock())

        with pytest.raises(RuntimeError, match="Lineage node was not created"):
            await repository.get_or_create_node(
                ORBIT_ID, artifact, cast(AsyncSession, mock_session)
            )

        mock_session.execute.assert_awaited_once()
        mock_session.scalar.assert_awaited_once()
        mock_session.flush.assert_not_awaited()
