import uuid

from luml.repositories.artifacts import ArtifactRepository
from luml.schemas.artifacts import (
    ArtifactCreate,
    ArtifactStatus,
    ArtifactUpdate,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.builders import create_collection as build_collection
from tests.support.seeds import CollectionFixtureData


class TestArtifactRepositoryCrud:
    async def test_create_artifact_persists_all_fields(
        self,
        repository: ArtifactRepository,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        model = new_artifact.model_copy()
        model.collection_id = seeded_collection.collection.id

        created_model = await repository.create_artifact(model)

        assert created_model
        assert created_model.collection_id == model.collection_id
        assert created_model.file_name == model.file_name
        assert created_model.name == model.name
        assert created_model.extra_values == model.extra_values
        assert created_model.file_hash == model.file_hash
        assert created_model.bucket_location == model.bucket_location
        assert created_model.size == model.size
        assert created_model.unique_identifier == model.unique_identifier
        assert created_model.tags == model.tags
        assert created_model.status == model.status

    async def test_get_artifact_returns_created_artifact(
        self,
        repository: ArtifactRepository,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        model = new_artifact.model_copy()
        model.collection_id = seeded_collection.collection.id

        created_model = await repository.create_artifact(model)
        fetched_model = await repository.get_artifact(created_model.id)

        assert fetched_model
        assert fetched_model.id == created_model.id
        assert fetched_model.collection_id == seeded_collection.collection.id

    async def test_update_status_changes_pending_upload_to_uploaded(
        self,
        repository: ArtifactRepository,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        model = new_artifact.model_copy()
        model.collection_id = seeded_collection.collection.id

        created_model = await repository.create_artifact(model)
        assert created_model.status == ArtifactStatus.PENDING_UPLOAD

        updated_model = await repository.update_status(
            created_model.id, ArtifactStatus.UPLOADED
        )

        assert updated_model
        assert updated_model.id == created_model.id
        assert updated_model.status == ArtifactStatus.UPLOADED

    async def test_update_artifact_changes_name_and_tags(
        self,
        repository: ArtifactRepository,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        model = new_artifact.model_copy()
        model.collection_id = seeded_collection.collection.id

        created_model = await repository.create_artifact(model)

        update_data = ArtifactUpdate(
            id=created_model.id, name="Updated Model Name", tags=["updated"]
        )
        updated_model = await repository.update_artifact(
            created_model.id, seeded_collection.collection.id, update_data
        )

        assert updated_model
        assert updated_model.id == created_model.id
        assert updated_model.name == update_data.name
        assert updated_model.tags == update_data.tags

    async def test_update_artifact_returns_none_when_artifact_is_in_other_collection(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        model = new_artifact.model_copy()
        model.collection_id = seeded_collection.collection.id
        created_model = await repository.create_artifact(model)

        sibling_collection_id = (
            await build_collection(engine, seeded_collection.orbit.id, "sibling")
        ).id

        result = await repository.update_artifact(
            created_model.id,
            sibling_collection_id,
            ArtifactUpdate(id=created_model.id, name="renamed"),
        )

        assert result is None

        untouched = await repository.get_artifact(created_model.id)
        assert untouched is not None
        assert untouched.name == created_model.name
        assert untouched.collection_id == seeded_collection.collection.id

    async def test_get_artifact_details_returns_collection_and_deployments(
        self,
        repository: ArtifactRepository,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        model = new_artifact.model_copy()
        model.collection_id = seeded_collection.collection.id
        created = await repository.create_artifact(model)

        details = await repository.get_artifact_details(created.id)

        assert details is not None
        assert details.id == created.id
        assert details.collection_id == seeded_collection.collection.id
        assert details.collection is not None
        assert details.deployments is not None

    async def test_get_artifact_details_returns_none_when_artifact_is_missing(
        self, repository: ArtifactRepository
    ) -> None:
        result = await repository.get_artifact_details(uuid.uuid4())

        assert result is None
