from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from luml.handlers.collections import CollectionHandler
from luml.handlers.permissions import PermissionsHandler
from luml.infra.db import engine as shared_engine
from luml.repositories.collections import CollectionRepository
from luml.schemas.collections import CollectionUpdateIn

from tests.support.seeds import CollectionFixtureData


@pytest.fixture
async def handler(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[CollectionHandler]:
    monkeypatch.setattr(PermissionsHandler, "check_permissions", AsyncMock())
    await shared_engine.dispose()
    yield CollectionHandler()
    await shared_engine.dispose()


class TestCollectionHandler:
    @pytest.mark.parametrize(
        ("payload", "expected_name", "expected_description", "expected_tags"),
        [
            pytest.param(
                {"name": "renamed"},
                "renamed",
                "description",
                ["tag1", "tag2"],
                id="name-only",
            ),
            pytest.param(
                {"description": "updated"},
                "name",
                "updated",
                ["tag1", "tag2"],
                id="description-only",
            ),
            pytest.param(
                {"name": "renamed", "description": "updated"},
                "renamed",
                "updated",
                ["tag1", "tag2"],
                id="name-and-description",
            ),
            pytest.param(
                {"tags": ["updated"]},
                "name",
                "description",
                ["updated"],
                id="tags-only",
            ),
            pytest.param({"tags": []}, "name", "description", [], id="empty-tags"),
            pytest.param({"tags": None}, "name", "description", None, id="null-tags"),
            pytest.param({}, "name", "description", ["tag1", "tag2"], id="empty-patch"),
        ],
    )
    async def test_update_collection_preserves_omitted_fields(
        self,
        handler: CollectionHandler,
        seeded_collection: CollectionFixtureData,
        payload: dict[str, Any],
        expected_name: str,
        expected_description: str,
        expected_tags: list[str] | None,
    ) -> None:
        data = seeded_collection

        updated = await handler.update_collection(
            data.user.id,
            data.organization.id,
            data.orbit.id,
            data.collection.id,
            CollectionUpdateIn.model_validate(payload),
        )

        reloaded = await CollectionRepository(data.engine).get_collection(
            data.collection.id
        )
        assert reloaded is not None
        for collection in (updated, reloaded):
            assert collection.name == expected_name
            assert collection.description == expected_description
            assert collection.tags == expected_tags
            assert collection.type == data.collection.type
            assert collection.orbit_id == data.orbit.id
