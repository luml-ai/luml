import pytest
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.collections import CollectionRepository
from luml.repositories.tracks import TrackRepository
from luml.schemas.artifacts import ArtifactCreate, ArtifactType
from luml.schemas.collections import CollectionCreate, CollectionType
from luml.schemas.general import PaginationParams
from luml.schemas.tracks import TrackCreate

from tests.support.builders import create_artifact
from tests.support.seeds import CollectionFixtureData, OrbitFixtureData

SEARCH_VALUES = {
    "plain-name",
    "50%_Off",
    "50x-Off",
    "100%",
    "100x",
    "path/to/name",
    "pathXtoXname",
    r"path\to\name",
    "ends\\",
    r"escaped\%",
}
SEARCH_CASES = [
    ("%", {"50%_Off", "100%", r"escaped\%"}),
    ("_", {"50%_Off"}),
    ("50%", {"50%_Off"}),
    ("%_", {"50%_Off"}),
    ("/", {"path/to/name"}),
    ("\\", {r"path\to\name", "ends\\", r"escaped\%"}),
    ("ends\\", {"ends\\"}),
    (r"\%", {r"escaped\%"}),
    ("oFf", {"50%_Off", "50x-Off"}),
    ("missing", set()),
    ("", SEARCH_VALUES),
    (None, SEARCH_VALUES),
]


@pytest.mark.parametrize(("search", "expected"), SEARCH_CASES)
async def test_artifact_search_matches_literal_substrings(
    seeded_collection: CollectionFixtureData,
    new_artifact: ArtifactCreate,
    search: str | None,
    expected: set[str],
) -> None:
    data = seeded_collection
    for value in SEARCH_VALUES:
        await create_artifact(data.engine, new_artifact, data.collection.id, name=value)

    results, cursor = await ArtifactRepository(data.engine).get_collection_artifacts(
        data.orbit.id, PaginationParams(), search=search
    )

    assert {item.name for item in results} == expected
    assert cursor is None


@pytest.mark.parametrize("field", ["name", "tags"])
@pytest.mark.parametrize(("search", "expected"), SEARCH_CASES)
async def test_collection_search_matches_literal_substrings(
    seeded_orbit: OrbitFixtureData,
    field: str,
    search: str | None,
    expected: set[str],
) -> None:
    data = seeded_orbit
    repository = CollectionRepository(data.engine)
    values = {}
    for index, value in enumerate(SEARCH_VALUES):
        collection = await repository.create_collection(
            CollectionCreate(
                orbit_id=data.orbit.id,
                name=value if field == "name" else f"entry-{index}",
                description="search fixture",
                type=CollectionType.MODEL,
                tags=[value] if field == "tags" else None,
            )
        )
        values[collection.id] = value

    results, cursor = await repository.get_orbit_collections(
        data.orbit.id, PaginationParams(), search=search
    )

    assert {values[item.id] for item in results} == expected
    assert cursor is None


@pytest.mark.parametrize("field", ["name", "tags"])
@pytest.mark.parametrize(("search", "expected"), SEARCH_CASES)
async def test_track_search_matches_literal_substrings(
    seeded_orbit: OrbitFixtureData,
    field: str,
    search: str | None,
    expected: set[str],
) -> None:
    data = seeded_orbit
    repository = TrackRepository(data.engine)
    values = {}
    for index, value in enumerate(SEARCH_VALUES):
        track = await repository.create_track(
            TrackCreate(
                orbit_id=data.orbit.id,
                name=value if field == "name" else f"entry-{index}",
                artifact_type=ArtifactType.MODEL,
                tags=[value] if field == "tags" else None,
            )
        )
        values[track.id] = value

    results, cursor = await repository.get_orbit_tracks(
        data.orbit.id, PaginationParams(), search=search
    )

    assert {values[item.id] for item in results} == expected
    assert cursor is None
