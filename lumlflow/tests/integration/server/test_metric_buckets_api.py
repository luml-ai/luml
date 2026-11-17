import math
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from luml.experiments.tracker import ExperimentTracker
from lumlflow.handlers import experiments as experiments_handler_module
from lumlflow.schemas.experiments import (
    MAX_KEYS_PER_BUCKET_REQUEST,
    MetricBuckets,
    MetricCatalog,
)

from tests.helpers.metrics import (
    LEGACY_INSERT,
    Point,
    log_points,
    require_newer_reader,
    revision2_experiment,
    serve,
)


def sample_points() -> list[Point]:
    regular = [(step, (step % 17) * 0.25 - 1.0) for step in range(-10, 300)]
    special = [
        (1000, math.inf),
        (1001, -math.inf),
        (1002, math.nan),
        (1003, 1e300),
    ]
    return regular + special


def post_buckets(
    client: TestClient,
    experiment_id: str,
    keys: list[str],
    level: int,
    start_step: int | None = None,
    end_step: int | None = None,
) -> Any:  # noqa: ANN401
    return client.post(
        f"/api/experiments/{experiment_id}/metric-buckets",
        json={
            "keys": keys,
            "start_step": start_step,
            "end_step": end_step,
            "level": level,
        },
    )


def bucket_json(client: TestClient, experiment_id: str, **request: Any) -> Any:  # noqa: ANN401
    response = post_buckets(client, experiment_id, **request)
    assert response.status_code == 200, response.text
    return response.json()


def schema_snapshot(db_path: Path) -> tuple[list[tuple[str, str, str | None]], int]:
    conn = sqlite3.connect(db_path)
    try:
        master = conn.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall()
        return master, conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


@pytest.fixture()
def store(tmp_path: Path) -> Path:
    return tmp_path / "experiments"


@pytest.fixture()
def tracker(store: Path) -> Iterator[ExperimentTracker]:
    tracker = ExperimentTracker(f"sqlite://{store}")
    yield tracker
    tracker.backend.close()


@pytest.fixture()
def client(tracker: ExperimentTracker) -> TestClient:
    return serve(tracker)


def test_catalog_has_the_contract_shape_and_is_never_cached(
    tracker: ExperimentTracker, client: TestClient
) -> None:
    experiment_id = tracker.start_experiment(name="shape")
    log_points(tracker, experiment_id, "loss", [(0, 2.0), (5, 1.0), (9, 0.5)])
    log_points(tracker, experiment_id, "acc", [(-3, 0.25)])

    response = client.get(f"/api/experiments/{experiment_id}/metric-catalog")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "revision": 3,
        "bucket_min_level": 3,
        "bucket_max_level": 12,
        "skipped_rows": 0,
        "metrics": [
            {
                "key": "acc",
                "first_step": -3,
                "last_step": -3,
                "count": 1,
                "min": 0.25,
                "max": 0.25,
            },
            {
                "key": "loss",
                "first_step": 0,
                "last_step": 9,
                "count": 3,
                "min": 0.5,
                "max": 2.0,
            },
        ],
    }


def test_buckets_have_the_contract_shape(
    tracker: ExperimentTracker, client: TestClient
) -> None:
    experiment_id = tracker.start_experiment(name="shape")
    log_points(tracker, experiment_id, "loss", [(0, 2.0), (5, 1.0), (16, 0.5)])

    assert bucket_json(client, experiment_id, keys=["loss"], level=2) == {
        "level": 2,
        "series": [
            {
                "key": "loss",
                "first_step": 0,
                "last_step": 16,
                "buckets": [
                    [0, 0, 5, 2, 2, 1.0, 2.0, 3.0],
                    [1, 16, 16, 1, 1, 0.5, 0.5, 0.5],
                ],
                "skipped_rows": 0,
            }
        ],
    }


def test_infinities_survive_the_json_round_trip(
    tracker: ExperimentTracker, client: TestClient
) -> None:
    experiment_id = tracker.start_experiment(name="inf")
    log_points(tracker, experiment_id, "x", [(0, math.inf), (1, -math.inf), (2, 1.0)])

    catalog = client.get(f"/api/experiments/{experiment_id}/metric-catalog")
    buckets = post_buckets(client, experiment_id, ["x"], level=0)

    assert catalog.json()["metrics"][0] | {"key": "x"} == {
        "key": "x",
        "first_step": 0,
        "last_step": 2,
        "count": 3,
        "min": "-Infinity",
        "max": "Infinity",
    }
    assert buckets.json()["series"][0]["buckets"] == [
        [0, 0, 0, 1, 0, "Infinity", "Infinity", None],
        [1, 1, 1, 1, 0, "-Infinity", "-Infinity", None],
        [2, 2, 2, 1, 1, 1.0, 1.0, 1.0],
    ]
    parsed_catalog = MetricCatalog.model_validate_json(catalog.text)
    assert (parsed_catalog.metrics[0].min, parsed_catalog.metrics[0].max) == (
        -math.inf,
        math.inf,
    )
    parsed = MetricBuckets.model_validate_json(buckets.text).series[0].buckets
    assert [(bucket.min, bucket.max) for bucket in parsed] == [
        (math.inf, math.inf),
        (-math.inf, -math.inf),
        (1.0, 1.0),
    ]


def test_a_key_with_slashes_and_unicode_is_served(
    tracker: ExperimentTracker, client: TestClient
) -> None:
    key = "train/ünïcode/损失 λ"
    experiment_id = tracker.start_experiment(name="keys")
    log_points(tracker, experiment_id, key, [(1, 0.5), (2, 0.25)])

    catalog = client.get(f"/api/experiments/{experiment_id}/metric-catalog").json()
    series = bucket_json(client, experiment_id, keys=[key], level=0)["series"]

    assert [metric["key"] for metric in catalog["metrics"]] == [key]
    assert series == [
        {
            "key": key,
            "first_step": 1,
            "last_step": 2,
            "buckets": [
                [1, 1, 1, 1, 1, 0.5, 0.5, 0.5],
                [2, 2, 2, 1, 1, 0.25, 0.25, 0.25],
            ],
            "skipped_rows": 0,
        }
    ]


def test_duplicate_keys_are_answered_once_and_missing_keys_are_empty(
    tracker: ExperimentTracker, client: TestClient
) -> None:
    experiment_id = tracker.start_experiment(name="dup")
    log_points(tracker, experiment_id, "a", [(0, 1.0)])

    series = bucket_json(
        client, experiment_id, keys=["a", "missing", "a", "missing"], level=3
    )["series"]

    assert series == [
        {
            "key": "a",
            "first_step": 0,
            "last_step": 0,
            "buckets": [[0, 0, 0, 1, 1, 1.0, 1.0, 1.0]],
            "skipped_rows": 0,
        },
        {
            "key": "missing",
            "first_step": None,
            "last_step": None,
            "buckets": [],
            "skipped_rows": 0,
        },
    ]


def test_empty_inverted_and_partial_ranges(
    tracker: ExperimentTracker, client: TestClient
) -> None:
    experiment_id = tracker.start_experiment(name="ranges")
    log_points(tracker, experiment_id, "m", [(step, float(step)) for step in range(40)])

    def buckets(**request: Any) -> list[list[Any]]:  # noqa: ANN401
        series = bucket_json(client, experiment_id, keys=["m"], **request)["series"]
        assert (series[0]["first_step"], series[0]["last_step"]) == (0, 39)
        return series[0]["buckets"]

    assert buckets(level=1, start_step=10, end_step=9) == []
    assert buckets(level=1, start_step=100, end_step=200) == []
    assert buckets(level=1, start_step=-(2**70), end_step=-1) == []
    # Edge buckets come back whole, not clipped to the range.
    assert buckets(level=2, start_step=17, end_step=33) == [
        [1, 16, 31, 16, 16, 16.0, 31.0, float(sum(range(16, 32)))],
        [2, 32, 39, 8, 8, 32.0, 39.0, float(sum(range(32, 40)))],
    ]
    assert bucket_json(client, experiment_id, keys=[], level=1) == {
        "level": 1,
        "series": [],
    }


def aggregate_level(level_zero: list[list[Any]], level: int) -> list[list[Any]]:
    """The buckets of `level`, computed in Python from the level 0 answer."""
    groups: dict[int, list[list[Any]]] = {}
    for row in level_zero:
        groups.setdefault(row[0] >> (2 * level), []).append(row)
    result = []
    for bucket, rows in sorted(groups.items()):
        numeric = [row[5] for row in rows if row[5] is not None]
        sums = [row[7] for row in rows if row[7] is not None]
        result.append(
            [
                bucket,
                min(row[1] for row in rows),
                max(row[2] for row in rows),
                sum(row[3] for row in rows),
                sum(row[4] for row in rows),
                min(numeric, key=float) if numeric else None,
                max(numeric, key=float) if numeric else None,
                sum(sums) if sums else None,
            ]
        )
    return result


def assert_same_buckets(actual: list[list[Any]], expected: list[list[Any]]) -> None:
    assert [row[:7] for row in actual] == [row[:7] for row in expected]
    for got, want in zip(actual, expected, strict=True):
        if want[7] is None:
            assert got[7] is None
        else:
            assert got[7] == pytest.approx(want[7], rel=1e-9, abs=1e-9)


@pytest.mark.parametrize("level", [1, 3, 5, 12, 13, 31])
def test_every_level_agrees_with_the_points(
    tracker: ExperimentTracker, client: TestClient, level: int
) -> None:
    experiment_id = tracker.start_experiment(name="levels")
    log_points(tracker, experiment_id, "m", sample_points())

    level_zero = bucket_json(client, experiment_id, keys=["m"], level=0)["series"][0]
    assert len(level_zero["buckets"]) == len(sample_points())
    actual = bucket_json(client, experiment_id, keys=["m"], level=level)["series"][0]

    assert actual["buckets"]
    assert_same_buckets(
        actual["buckets"], aggregate_level(level_zero["buckets"], level)
    )


def test_unknown_experiment_is_404(client: TestClient) -> None:
    catalog = client.get("/api/experiments/nope/metric-catalog")
    buckets = post_buckets(client, "nope", ["loss"], level=0)

    assert (catalog.status_code, buckets.status_code) == (404, 404)


@pytest.mark.parametrize("level", [-1, 32])
def test_level_outside_the_range_is_invalid_level(
    tracker: ExperimentTracker, client: TestClient, level: int
) -> None:
    experiment_id = tracker.start_experiment(name="levels")
    log_points(tracker, experiment_id, "m", [(0, 1.0)])

    for keys in (["m"], []):
        response = post_buckets(client, experiment_id, keys, level=level)
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "invalid-level"
        assert str(level) in response.json()["detail"]["message"]


def test_more_than_the_bucket_cap_is_too_many_buckets(
    tracker: ExperimentTracker, client: TestClient
) -> None:
    experiment_id = tracker.start_experiment(name="cap")
    log_points(tracker, experiment_id, "m", [(step, 1.0) for step in range(20_001)])

    too_many = post_buckets(client, experiment_id, ["m"], level=0)
    at_cap = post_buckets(client, experiment_id, ["m"], level=0, end_step=19_999)

    assert too_many.status_code == 422
    assert too_many.json()["detail"] == {
        "code": "too-many-buckets",
        "message": too_many.json()["detail"]["message"],
    }
    assert "20000" in too_many.json()["detail"]["message"]
    assert at_cap.status_code == 200
    assert len(at_cap.json()["series"][0]["buckets"]) == 20_000


def test_a_request_over_the_total_bucket_bound_stops_early(
    tracker: ExperimentTracker, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(experiments_handler_module, "MAX_BUCKETS_PER_REQUEST", 30)
    experiment_id = tracker.start_experiment(name="bound")
    keys = [f"m{index}" for index in range(6)]
    for key in keys:
        log_points(tracker, experiment_id, key, [(step, 1.0) for step in range(10)])
    sdk_read = tracker.get_metric_buckets
    read_keys: list[str] = []

    def counting_read(experiment_id: str, key: str, **kwargs: Any) -> Any:  # noqa: ANN401
        read_keys.append(key)
        return sdk_read(experiment_id, key, **kwargs)

    monkeypatch.setattr(tracker, "get_metric_buckets", counting_read)

    at_bound = post_buckets(client, experiment_id, keys[:3], level=0)
    read_keys.clear()
    over_bound = post_buckets(client, experiment_id, keys, level=0)

    assert at_bound.status_code == 200
    assert sum(len(s["buckets"]) for s in at_bound.json()["series"]) == 30
    assert over_bound.status_code == 422
    assert over_bound.json()["detail"]["code"] == "too-many-buckets"
    assert "30" in over_bound.json()["detail"]["message"]
    assert read_keys == keys[:4]


def test_more_than_the_key_limit_is_422_before_any_read(
    tracker: ExperimentTracker, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    experiment_id = tracker.start_experiment(name="keys")
    log_points(tracker, experiment_id, "m", [(0, 1.0)])
    keys = ["m"] + [f"unknown{index}" for index in range(MAX_KEYS_PER_BUCKET_REQUEST)]
    sdk_read = tracker.get_metric_buckets
    read_keys: list[str] = []

    def counting_read(experiment_id: str, key: str, **kwargs: Any) -> Any:  # noqa: ANN401
        read_keys.append(key)
        return sdk_read(experiment_id, key, **kwargs)

    monkeypatch.setattr(tracker, "get_metric_buckets", counting_read)

    over_limit = post_buckets(client, experiment_id, keys, level=0)
    reads_over_limit = len(read_keys)
    at_limit = post_buckets(client, experiment_id, keys[:-1], level=0)

    assert over_limit.status_code == 422
    assert reads_over_limit == 0
    assert at_limit.status_code == 200
    assert len(at_limit.json()["series"]) == MAX_KEYS_PER_BUCKET_REQUEST
    assert at_limit.json()["series"][0]["buckets"] == [[0, 0, 0, 1, 1, 1.0, 1.0, 1.0]]


def test_a_database_for_a_newer_reader_is_409(store: Path) -> None:
    setup = ExperimentTracker(f"sqlite://{store}")
    experiment_id = setup.start_experiment(name="future")
    log_points(setup, experiment_id, "m", [(0, 1.0)])
    setup.end_experiment(experiment_id)
    setup.backend.close()
    require_newer_reader(store / experiment_id / "exp.db")
    reader = ExperimentTracker(f"sqlite://{store}")
    client = serve(reader)

    catalog = client.get(f"/api/experiments/{experiment_id}/metric-catalog")
    buckets = post_buckets(client, experiment_id, ["m"], level=0)

    for response in (catalog, buckets):
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "needs-newer-reader"
        assert "newer reader" in response.json()["detail"]["message"]
    reader.backend.close()


def test_a_revision_2_experiment_is_served_unmigrated_with_the_same_buckets(
    store: Path,
) -> None:
    old_id, old_db = revision2_experiment(store, "m", sample_points())
    before = schema_snapshot(old_db)
    assert before[1] == 2
    tracker = ExperimentTracker(f"sqlite://{store}")
    new_id = tracker.start_experiment(name="current")
    log_points(tracker, new_id, "m", sample_points())
    client = serve(tracker)

    old_catalog = client.get(f"/api/experiments/{old_id}/metric-catalog").json()
    new_catalog = client.get(f"/api/experiments/{new_id}/metric-catalog").json()
    assert (old_catalog["revision"], old_catalog["bucket_max_level"]) == (2, None)
    assert old_catalog["metrics"] == [
        {**metric, "count": None, "min": None, "max": None}
        for metric in new_catalog["metrics"]
    ]
    for level in (0, 2, 3, 6, 12, 14):
        old = bucket_json(client, old_id, keys=["m"], level=level)
        new = bucket_json(client, new_id, keys=["m"], level=level)
        assert old["series"][0]["first_step"] == new["series"][0]["first_step"]
        assert_same_buckets(old["series"][0]["buckets"], new["series"][0]["buckets"])

    assert schema_snapshot(old_db) == before
    tracker.backend.close()


def test_a_revision_2_experiment_counts_its_fractional_steps_per_series(
    store: Path,
) -> None:
    experiment_id, db_path = revision2_experiment(
        store, "m", [(step, 1.0) for step in range(10)]
    )
    conn = sqlite3.connect(db_path)
    conn.executemany(
        LEGACY_INSERT,
        [("m", 0.5, 2.5, None), ("m", 0.5, 7.5, None), ("other", 1.0, 0, None)],
    )
    conn.commit()
    conn.close()
    tracker = ExperimentTracker(f"sqlite://{store}")
    client = serve(tracker)

    whole = bucket_json(client, experiment_id, keys=["m", "other"], level=1)
    window = bucket_json(
        client, experiment_id, keys=["m"], level=0, start_step=0, end_step=5
    )

    assert [(s["key"], s["skipped_rows"]) for s in whole["series"]] == [
        ("m", 2),
        ("other", 0),
    ]
    assert sum(bucket[3] for bucket in whole["series"][0]["buckets"]) == 10
    assert window["series"][0]["skipped_rows"] == 1
    tracker.backend.close()


def test_a_growing_experiment_shows_new_points_between_calls(
    tracker: ExperimentTracker, client: TestClient
) -> None:
    experiment_id = tracker.start_experiment(name="live")
    log_points(tracker, experiment_id, "m", [(step, 1.0) for step in range(70)])

    def tail() -> tuple[dict[str, Any], list[list[Any]]]:
        catalog = client.get(f"/api/experiments/{experiment_id}/metric-catalog")
        series = bucket_json(client, experiment_id, keys=["m"], level=3, start_step=64)[
            "series"
        ][0]
        return catalog.json()["metrics"][0], series["buckets"]

    first_summary, first_tail = tail()
    log_points(tracker, experiment_id, "m", [(step, 3.0) for step in range(70, 130)])
    second_summary, second_tail = tail()

    assert (first_summary["last_step"], first_summary["count"]) == (69, 70)
    assert (second_summary["last_step"], second_summary["count"]) == (129, 130)
    assert second_summary["max"] == 3.0
    assert first_tail == [[1, 64, 69, 6, 6, 1.0, 1.0, 6.0]]
    assert second_tail == [
        [1, 64, 127, 64, 64, 1.0, 3.0, 6.0 + 58 * 3.0],
        [2, 128, 129, 2, 2, 3.0, 3.0, 6.0],
    ]


def test_the_history_endpoint_keeps_its_output(
    tracker: ExperimentTracker, client: TestClient
) -> None:
    experiment_id = tracker.start_experiment(name="history")
    log_points(tracker, experiment_id, "m", [(step, float(step)) for step in range(10)])

    response = client.get(
        f"/api/experiments/{experiment_id}/metrics/m", params={"max_points": 4}
    )

    body = response.json()
    assert response.status_code == 200
    assert set(body) == {"experiment_id", "key", "subsampled", "history"}
    assert (body["experiment_id"], body["key"], body["subsampled"]) == (
        experiment_id,
        "m",
        True,
    )
    assert [(point["step"], point["value"]) for point in body["history"]] == [
        (0, 0.0),
        (3, 3.0),
        (6, 6.0),
        (9, 9.0),
    ]
    assert all(
        set(point) == {"step", "value", "logged_at"} for point in body["history"]
    )
