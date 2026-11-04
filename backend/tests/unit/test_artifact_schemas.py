from datetime import datetime

import pytest
from luml.constants import MAX_FILE_SIZE_BYTES
from luml.schemas.artifacts import (
    Artifact,
    ArtifactCreate,
    ArtifactIn,
    ArtifactListedBase,
)
from pydantic import BaseModel, ValidationError

from tests.support.ids import ARTIFACT_ID


class TestArtifactSchemas:
    @pytest.mark.parametrize("schema", [ArtifactIn, Artifact, ArtifactListedBase])
    @pytest.mark.parametrize(
        ("size", "valid"),
        [(MAX_FILE_SIZE_BYTES, True), (MAX_FILE_SIZE_BYTES + 1, False)],
    )
    def test_size_is_capped_at_five_terabytes(
        self,
        new_artifact: ArtifactCreate,
        schema: type[BaseModel],
        size: int,
        valid: bool,
    ) -> None:
        data = new_artifact.model_dump() | {
            "id": ARTIFACT_ID,
            "created_at": datetime(2026, 11, 2),
            "collection": {"name": "models"},
            "has_experiment_snapshot": False,
            "size": size,
        }

        if valid:
            assert schema.model_validate(data).model_dump()["size"] == size
        else:
            with pytest.raises(ValidationError, match="bigger than 5TB"):
                schema.model_validate(data)
