import uuid

import pytest
from luml.infra.exceptions import InvalidSortingError
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.deployments import DeploymentRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.satellites import SatelliteRepository
from luml.schemas.artifacts import (
    ArtifactCreate,
    ArtifactStatus,
    ArtifactType,
)
from luml.schemas.deployment import DeploymentCreate, DeploymentStatus
from luml.schemas.general import PaginationParams, SortOrder
from luml.schemas.orbit import OrbitCreateIn
from luml.schemas.satellite import SatelliteCreate
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.repositories.artifacts.conftest import _add_artifact_to_track
from tests.support.builders import (
    create_artifact,
    create_collection as build_collection,
)
from tests.support.seeds import CollectionFixtureData


class TestArtifactRepositoryListing:
    async def test_get_collection_artifacts_returns_collection_artifacts(
        self,
        repository: ArtifactRepository,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        model_data1 = new_artifact.model_copy()
        model_data1.collection_id = seeded_collection.collection.id
        model_data1.unique_identifier = "uid1"

        model_data2 = new_artifact.model_copy()
        model_data2.collection_id = seeded_collection.collection.id
        model_data2.unique_identifier = "uid2"

        created_model1 = await repository.create_artifact(model_data1)
        created_model2 = await repository.create_artifact(model_data2)

        pagination = PaginationParams(limit=100)
        models, _ = await repository.get_collection_artifacts(
            seeded_collection.orbit.id,
            pagination,
            collection_ids=[seeded_collection.collection.id],
        )

        assert len(models) == 2
        model_ids = [m.id for m in models]
        assert created_model1.id in model_ids
        assert created_model2.id in model_ids

    async def test_get_collection_artifacts_returns_only_active_deployments(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        satellite_repository = SatelliteRepository(engine)
        deployment_repository = DeploymentRepository(engine)

        model = new_artifact.model_copy()
        model.collection_id = seeded_collection.collection.id
        model.status = ArtifactStatus.UPLOADED
        created_model = await repository.create_artifact(model)

        satellite = await satellite_repository.create_satellite(
            SatelliteCreate(
                orbit_id=seeded_collection.orbit.id,
                api_key_hash=str(uuid.uuid4()),
                name="test_satellite",
            )
        )

        active, _ = await deployment_repository.create_deployment(
            DeploymentCreate(
                name="active-deployment",
                orbit_id=seeded_collection.orbit.id,
                satellite_id=satellite.id,
                artifact_id=created_model.id,
                status=DeploymentStatus.ACTIVE,
            )
        )
        await deployment_repository.create_deployment(
            DeploymentCreate(
                name="pending-deployment",
                orbit_id=seeded_collection.orbit.id,
                satellite_id=satellite.id,
                artifact_id=created_model.id,
                status=DeploymentStatus.PENDING,
            )
        )

        pagination = PaginationParams(limit=100)
        models, _ = await repository.get_collection_artifacts(
            seeded_collection.orbit.id,
            pagination,
            collection_ids=[seeded_collection.collection.id],
        )

        assert len(models) == 1
        assert [d.id for d in models[0].deployments] == [active.id]

    async def test_get_collection_artifacts_count_counts_created_artifacts(
        self,
        repository: ArtifactRepository,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        count = await repository.get_collection_artifacts_count(
            seeded_collection.collection.id
        )
        assert count == 0

        model = new_artifact.model_copy()
        model.collection_id = seeded_collection.collection.id
        await repository.create_artifact(model)

        count = await repository.get_collection_artifacts_count(
            seeded_collection.collection.id
        )
        assert count == 1

    async def test_get_collection_artifacts_extra_values_returns_sorted_keys(
        self,
        repository: ArtifactRepository,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        model = new_artifact.model_copy()
        model.collection_id = seeded_collection.collection.id
        model.extra_values = {"accuracy": 0.95, "f1": 0.88}
        await repository.create_artifact(model)

        result = await repository.get_collection_artifacts_extra_values(
            seeded_collection.collection.id
        )

        assert "accuracy" in result
        assert "f1" in result
        assert result == sorted(result)

    async def test_get_collection_artifacts_extra_values_returns_empty_list(
        self,
        repository: ArtifactRepository,
        seeded_collection: CollectionFixtureData,
    ) -> None:
        result = await repository.get_collection_artifacts_extra_values(
            seeded_collection.collection.id
        )

        assert result == []

    async def test_get_collection_artifacts_tags_returns_distinct_tags(
        self,
        repository: ArtifactRepository,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        model1 = new_artifact.model_copy()
        model1.collection_id = seeded_collection.collection.id
        model1.unique_identifier = "uid1"
        model1.tags = ["v1", "prod"]

        model2 = new_artifact.model_copy()
        model2.collection_id = seeded_collection.collection.id
        model2.unique_identifier = "uid2"
        model2.tags = ["v2", "prod"]

        await repository.create_artifact(model1)
        await repository.create_artifact(model2)

        result = await repository.get_collection_artifacts_tags(
            seeded_collection.collection.id
        )

        assert set(result) == {"v1", "v2", "prod"}

    async def test_get_collection_artifacts_pages_by_metric_lowest_first(
        self,
        repository: ArtifactRepository,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        low = new_artifact.model_copy()
        low.collection_id = seeded_collection.collection.id
        low.unique_identifier = "low"
        low.extra_values = {"accuracy": 0.1}

        high = new_artifact.model_copy()
        high.collection_id = seeded_collection.collection.id
        high.unique_identifier = "high"
        high.extra_values = {"accuracy": 0.9}

        await repository.create_artifact(low)
        await repository.create_artifact(high)

        first, cursor = await repository.get_collection_artifacts(
            seeded_collection.orbit.id,
            PaginationParams(limit=1, sort_by="accuracy", order=SortOrder.ASC),
            collection_ids=[seeded_collection.collection.id],
        )
        assert len(first) == 1
        assert first[0].extra_values["accuracy"] == 0.1
        assert cursor is not None
        assert cursor.sort_by == "accuracy"

        second, _ = await repository.get_collection_artifacts(
            seeded_collection.orbit.id,
            PaginationParams(
                limit=1, sort_by="accuracy", order=SortOrder.ASC, cursor=cursor
            ),
            collection_ids=[seeded_collection.collection.id],
        )
        assert second[0].extra_values["accuracy"] == 0.9

    async def test_get_collection_artifacts_raises_when_sorted_by_extra_values(
        self,
        repository: ArtifactRepository,
        seeded_collection: CollectionFixtureData,
    ) -> None:
        with pytest.raises(InvalidSortingError):
            await repository.get_collection_artifacts(
                seeded_collection.orbit.id,
                PaginationParams(limit=10, sort_by="extra_values"),
                collection_ids=[seeded_collection.collection.id],
            )

    @pytest.mark.parametrize(
        "sort_by", ["nonexistent_zzz", "collection_name", "metadata"]
    )
    async def test_get_collection_artifacts_rejects_invalid_sort_within_collections(
        self,
        repository: ArtifactRepository,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
        sort_by: str,
    ) -> None:
        model = new_artifact.model_copy()
        model.collection_id = seeded_collection.collection.id
        model.extra_values = {"accuracy": 0.5}
        await repository.create_artifact(model)

        with pytest.raises(InvalidSortingError, match="Invalid sorting column"):
            await repository.get_collection_artifacts(
                seeded_collection.orbit.id,
                PaginationParams(limit=10, sort_by=sort_by),
                collection_ids=[seeded_collection.collection.id],
            )

    async def test_get_collection_artifacts_returns_only_requested_type(
        self,
        repository: ArtifactRepository,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        model = new_artifact.model_copy()
        model.collection_id = seeded_collection.collection.id
        model.unique_identifier = "a-model"
        model.type = ArtifactType.MODEL

        dataset = new_artifact.model_copy()
        dataset.collection_id = seeded_collection.collection.id
        dataset.unique_identifier = "a-dataset"
        dataset.type = ArtifactType.DATASET

        await repository.create_artifact(model)
        await repository.create_artifact(dataset)

        items, _ = await repository.get_collection_artifacts(
            seeded_collection.orbit.id,
            PaginationParams(limit=100),
            collection_ids=[seeded_collection.collection.id],
            artifact_types=[ArtifactType.MODEL],
        )
        assert all(a.type == ArtifactType.MODEL for a in items)
        assert len(items) == 1

    async def test_get_collection_artifacts_matches_search_partially_ignoring_case(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        resnet = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="ResNet50",
            status=new_artifact.status,
        )
        await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="BERT",
            status=new_artifact.status,
        )

        items, _ = await repository.get_collection_artifacts(
            seeded_collection.orbit.id, PaginationParams(limit=100), search="resnet"
        )

        assert [a.id for a in items] == [resnet.id]

    async def test_get_collection_artifacts_returns_nothing_when_search_misses(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="ResNet50",
            status=new_artifact.status,
        )

        items, cursor = await repository.get_collection_artifacts(
            seeded_collection.orbit.id,
            PaginationParams(limit=100),
            search="nonexistent",
        )

        assert items == []
        assert cursor is None

    async def test_get_collection_artifacts_pages_by_created_at(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        for i in range(3):
            await create_artifact(
                engine,
                new_artifact,
                seeded_collection.collection.id,
                name=f"model-{i}",
                status=new_artifact.status,
            )

        first_page, cursor = await repository.get_collection_artifacts(
            seeded_collection.orbit.id, PaginationParams(limit=2)
        )
        assert len(first_page) == 2
        assert cursor is not None

        second_page, next_cursor = await repository.get_collection_artifacts(
            seeded_collection.orbit.id, PaginationParams(limit=2, cursor=cursor)
        )
        assert len(second_page) == 1
        assert next_cursor is None

        all_ids = {a.id for a in first_page} | {a.id for a in second_page}
        assert len(all_ids) == 3

    async def test_get_collection_artifacts_excludes_other_orbit(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        in_scope = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="in-scope",
            status=new_artifact.status,
        )

        other_orbit = await OrbitRepository(engine).create_orbit(
            seeded_collection.organization.id,
            OrbitCreateIn(
                name="other orbit",
                bucket_secret_id=seeded_collection.bucket_secret.id,
            ),
        )
        assert other_orbit is not None
        other_collection_id = (
            await build_collection(engine, other_orbit.id, "other-collection")
        ).id
        await create_artifact(
            engine,
            new_artifact,
            other_collection_id,
            name="out-of-scope",
            status=new_artifact.status,
        )

        items, _ = await repository.get_collection_artifacts(
            seeded_collection.orbit.id, PaginationParams(limit=100)
        )

        assert [a.id for a in items] == [in_scope.id]

    async def test_get_collection_artifacts_returns_whole_orbit_when_no_collection_ids(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        second_collection_id = (
            await build_collection(
                engine, seeded_collection.orbit.id, "second-collection"
            )
        ).id

        a1 = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="a1",
            status=new_artifact.status,
        )
        a2 = await create_artifact(
            engine,
            new_artifact,
            second_collection_id,
            name="a2",
            status=new_artifact.status,
        )

        items, _ = await repository.get_collection_artifacts(
            seeded_collection.orbit.id, PaginationParams(limit=100)
        )

        assert {a.id for a in items} == {a1.id, a2.id}

    async def test_get_collection_artifacts_returns_only_listed_collection(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        second_collection_id = (
            await build_collection(
                engine, seeded_collection.orbit.id, "second-collection"
            )
        ).id

        target = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="t",
            status=new_artifact.status,
        )
        await create_artifact(
            engine,
            new_artifact,
            second_collection_id,
            name="other",
            status=new_artifact.status,
        )

        items, _ = await repository.get_collection_artifacts(
            seeded_collection.orbit.id,
            PaginationParams(limit=100),
            collection_ids=[seeded_collection.collection.id],
        )

        assert [a.id for a in items] == [target.id]

    async def test_get_collection_artifacts_returns_all_listed_collections(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        second_collection_id = (
            await build_collection(
                engine, seeded_collection.orbit.id, "second-collection"
            )
        ).id
        third_collection_id = (
            await build_collection(
                engine, seeded_collection.orbit.id, "third-collection"
            )
        ).id

        a1 = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="a1",
            status=new_artifact.status,
        )
        a2 = await create_artifact(
            engine,
            new_artifact,
            second_collection_id,
            name="a2",
            status=new_artifact.status,
        )
        await create_artifact(
            engine,
            new_artifact,
            third_collection_id,
            name="a3",
            status=new_artifact.status,
        )

        items, _ = await repository.get_collection_artifacts(
            seeded_collection.orbit.id,
            PaginationParams(limit=100),
            collection_ids=[seeded_collection.collection.id, second_collection_id],
        )

        assert {a.id for a in items} == {a1.id, a2.id}

    async def test_get_collection_artifacts_returns_all_listed_types(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        model = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="m",
            artifact_type=ArtifactType.MODEL,
            status=new_artifact.status,
        )
        dataset = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="d",
            artifact_type=ArtifactType.DATASET,
            status=new_artifact.status,
        )
        await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="e",
            artifact_type=ArtifactType.EXPERIMENT,
            status=new_artifact.status,
        )

        items, _ = await repository.get_collection_artifacts(
            seeded_collection.orbit.id,
            PaginationParams(limit=100),
            artifact_types=[ArtifactType.MODEL, ArtifactType.DATASET],
        )

        assert {a.id for a in items} == {model.id, dataset.id}

    async def test_get_collection_artifacts_applies_all_filters_together(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        second_collection_id = (
            await build_collection(
                engine, seeded_collection.orbit.id, "second-collection"
            )
        ).id

        target = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="prod-model",
            artifact_type=ArtifactType.MODEL,
            status=new_artifact.status,
        )
        await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="prod-model",
            artifact_type=ArtifactType.DATASET,
            status=new_artifact.status,
        )
        await create_artifact(
            engine,
            new_artifact,
            second_collection_id,
            name="prod-model",
            artifact_type=ArtifactType.MODEL,
            status=new_artifact.status,
        )
        await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="staging-model",
            artifact_type=ArtifactType.MODEL,
            status=new_artifact.status,
        )

        items, _ = await repository.get_collection_artifacts(
            seeded_collection.orbit.id,
            PaginationParams(limit=100),
            collection_ids=[seeded_collection.collection.id],
            artifact_types=[ArtifactType.MODEL],
            search="prod",
        )

        assert [a.id for a in items] == [target.id]

    async def test_get_collection_artifacts_returns_nothing_when_orbit_is_empty(
        self,
        repository: ArtifactRepository,
        seeded_collection: CollectionFixtureData,
    ) -> None:
        items, cursor = await repository.get_collection_artifacts(
            seeded_collection.orbit.id, PaginationParams(limit=100)
        )

        assert items == []
        assert cursor is None

    async def test_get_collection_artifacts_rejects_metric_sort_across_whole_orbit(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="first",
            extra_values={"acc": 0.1},
            status=new_artifact.status,
        )
        await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="second",
            extra_values={"acc": 0.9},
            status=new_artifact.status,
        )

        with pytest.raises(InvalidSortingError, match="Invalid sorting column"):
            await repository.get_collection_artifacts(
                seeded_collection.orbit.id,
                PaginationParams(limit=100, sort_by="acc", order=SortOrder.DESC),
            )

    @pytest.mark.parametrize(
        "sort_by", ["nonexistent_zzz", "collection_name", "metadata"]
    )
    async def test_get_collection_artifacts_rejects_invalid_sort_across_whole_orbit(
        self,
        repository: ArtifactRepository,
        seeded_collection: CollectionFixtureData,
        sort_by: str,
    ) -> None:
        with pytest.raises(InvalidSortingError, match="Invalid sorting column"):
            await repository.get_collection_artifacts(
                seeded_collection.orbit.id,
                PaginationParams(limit=100, sort_by=sort_by),
            )

    async def test_get_collection_artifacts_drops_artifacts_of_excluded_track(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        in_track = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="in-track",
            status=new_artifact.status,
        )
        free = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="free",
            status=new_artifact.status,
        )

        track_id = await _add_artifact_to_track(
            engine,
            seeded_collection.orbit.id,
            in_track.id,
            seeded_collection.user.email,
        )

        all_items, _ = await repository.get_collection_artifacts(
            seeded_collection.orbit.id, PaginationParams(limit=100)
        )
        assert {a.id for a in all_items} == {in_track.id, free.id}

        items, _ = await repository.get_collection_artifacts(
            seeded_collection.orbit.id,
            PaginationParams(limit=100),
            excluded_tracks=[track_id],
        )
        assert [a.id for a in items] == [free.id]

    async def test_get_collection_artifacts_keeps_artifacts_of_tracks_not_excluded(
        self,
        repository: ArtifactRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        a_in_t1 = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="t1",
            status=new_artifact.status,
        )
        a_in_t2 = await create_artifact(
            engine,
            new_artifact,
            seeded_collection.collection.id,
            name="t2",
            status=new_artifact.status,
        )

        t1 = await _add_artifact_to_track(
            engine,
            seeded_collection.orbit.id,
            a_in_t1.id,
            seeded_collection.user.email,
            name="track-1",
        )
        await _add_artifact_to_track(
            engine,
            seeded_collection.orbit.id,
            a_in_t2.id,
            seeded_collection.user.email,
            name="track-2",
        )

        items, _ = await repository.get_collection_artifacts(
            seeded_collection.orbit.id,
            PaginationParams(limit=100),
            excluded_tracks=[t1],
        )

        assert [a.id for a in items] == [a_in_t2.id]
