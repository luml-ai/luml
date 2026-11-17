"""Frozen generation 2 (and fallback) artifacts against the expectations generated
next to them by a brute force that shares no code with the SDK."""

import json
import math
import sqlite3
import tarfile
from pathlib import Path
from typing import Any

import pytest

from luml import ExperimentReference
from luml.experiments.backends.data_types import MetricBucket
from luml.experiments.backends.sqlite import SQLiteBackend
from luml.experiments.tracker import ExperimentTracker
from tests.artifacts.snapshot_helpers import (
    assert_publishable_db,
    connect_read_only,
    extract_snapshot_db,
    read_json_member,
    snapshot_member,
)
from tests.experiments.metric_helpers import (
    FIXTURES_DIR,
    assert_bucket_invariants,
    assert_same_buckets,
    assert_same_catalog,
    make_store,
    replace_experiment_db,
)

FIXTURES = [
    "i_gen2_sdk_0_6_0",
    "j_gen2_model_sdk_0_6_0",
    "k_gen2_from_rev2",
    "l_gen1_twin",
    "m_gen2_twin",
    "n_gen1_fallback",
]
EXP_ID = "fixture"


def _expected(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _number(value: float | str | None) -> float | None:
    if isinstance(value, str):
        return {"Infinity": math.inf, "-Infinity": -math.inf}[value]
    return value


def _producer_tag(artifact: Path, kind: str) -> str:
    if kind == "experiment":
        return read_json_member(artifact, "manifest.json")["producer_tags"][0]
    with tarfile.open(artifact) as tar:
        (meta,) = [name for name in tar.getnames() if name.startswith("meta-")]
    return read_json_member(artifact, meta)[0]["tags"][0]


def _schema_facts(db: Path) -> dict[str, Any]:
    conn = connect_read_only(db)
    try:
        objects = conn.execute("SELECT type, name FROM sqlite_master").fetchall()
        tables = {name for kind, name in objects if kind == "table"}
        return {
            "user_version": conn.execute("PRAGMA user_version").fetchone()[0],
            "recorded_revisions": [
                row[0]
                for row in conn.execute(
                    "SELECT version FROM exp_schema_migrations ORDER BY version"
                )
            ],
            "schema_info": dict(conn.execute("SELECT key, value FROM exp_schema_info"))
            if "exp_schema_info" in tables
            else {},
            "tables": sorted(tables),
            "views": sorted(name for kind, name in objects if kind == "view"),
            "triggers": sorted(name for kind, name in objects if kind == "trigger"),
            "schema_sql": {
                name: " ".join(sql.split())
                for name, sql in conn.execute(
                    "SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL"
                )
            },
        }
    finally:
        conn.close()


def _header(db: Path) -> tuple[int, list[int]]:
    with open(db, "rb") as file:
        header = file.read(100)
    return int.from_bytes(header[16:18], "big"), [header[18], header[19]]


def _backend_on(db: Path, store: Path) -> SQLiteBackend:
    make_store(store, EXP_ID)
    replace_experiment_db(store, EXP_ID, db)
    return SQLiteBackend(str(store), flush_interval=0)


def _assert_bucket_rows(
    actual: list[MetricBucket], expected: list[list[Any]], context: str
) -> None:
    assert len(actual) == len(expected), context
    for bucket, row in zip(actual, expected, strict=True):
        assert (
            bucket.bucket,
            bucket.first_step,
            bucket.last_step,
            bucket.count,
            bucket.finite_count,
            bucket.min,
            bucket.max,
        ) == (*row[:5], _number(row[5]), _number(row[6])), (context, bucket, row)
        if row[7] is None:
            assert bucket.sum is None, (context, bucket)
        else:
            assert bucket.sum is not None
            assert math.isclose(bucket.sum, row[7], rel_tol=1e-9, abs_tol=1e-9), (
                context,
                bucket,
                row,
            )


@pytest.mark.parametrize("name", FIXTURES)
def test_published_artifact_matches_its_expectations(name: str, tmp_path: Path) -> None:
    expected = _expected(name)
    artifact = FIXTURES_DIR / f"{name}.tar"
    with tarfile.open(artifact) as tar:
        assert snapshot_member(tar.getnames()) == expected["snapshot_member"]
    assert (
        _producer_tag(artifact, expected["artifact_kind"]) == expected["producer_tag"]
    )
    generation = expected["artifact_generation"]
    assert expected["producer_tag"].endswith(f"experiment_snapshot:v{generation}")
    if expected["artifact_kind"] == "experiment":
        reference = ExperimentReference(str(artifact))
        assert reference.validate()
        assert reference.get_manifest().payload.model_dump(exclude_none=True) == {
            key: value
            for key, value in expected["manifest_payload"].items()
            if value is not None
        }

    db = tmp_path / "exp.db"
    extract_snapshot_db(artifact, db)
    assert _header(db) == (expected["page_size"], expected["wal_header"])
    facts = _schema_facts(db)
    assert facts == {key: expected[key] for key in facts}
    if generation == 2:
        assert_publishable_db(db)
        conn = connect_read_only(db)
        assert_bucket_invariants(conn)
        conn.close()

    backend = _backend_on(db, tmp_path / "store")
    try:
        _assert_reads(backend, expected)
    finally:
        backend.close()


def _assert_reads(backend: SQLiteBackend, expected: dict[str, Any]) -> None:
    metrics = expected["metrics"]
    catalog = backend.get_metric_catalog(EXP_ID)
    assert catalog.revision == expected["user_version"]
    assert catalog.skipped_rows == metrics["skipped_rows"]
    assert [
        (m.key, m.first_step, m.last_step, m.count, m.min, m.max)
        for m in catalog.metrics
    ] == [
        (
            m["key"],
            m["first_step"],
            m["last_step"],
            m["count"],
            _number(m["min"]),
            _number(m["max"]),
        )
        for m in metrics["catalog"]
    ]
    for key, by_level in metrics["buckets"].items():
        for level, rows in by_level.items():
            result = backend.get_metric_buckets(EXP_ID, key, int(level))
            _assert_bucket_rows(result.buckets, rows, f"{key} level {level}")
    data = backend.get_experiment_data(EXP_ID)
    assert data.static_params == expected["expected"]["static_params"]
    content = expected["expected"]
    if "traces" in content:
        assert len(backend.get_experiment_traces_all(EXP_ID)) == len(content["traces"])
        assert len(backend.list_attachments(EXP_ID)) == content["attachments"]


def test_both_generations_of_the_same_data_read_the_same(tmp_path: Path) -> None:
    backends = {
        name: _backend_on(
            _extracted(name, tmp_path / name / "exp.db"), tmp_path / name / "store"
        )
        for name in ("l_gen1_twin", "m_gen2_twin")
    }
    old, new = backends["l_gen1_twin"], backends["m_gen2_twin"]
    try:
        assert old.get_metric_catalog(EXP_ID).revision == 2
        assert new.get_metric_catalog(EXP_ID).revision == 3
        assert_same_catalog(
            old.get_metric_catalog(EXP_ID), new.get_metric_catalog(EXP_ID)
        )
        keys = [m.key for m in new.get_metric_catalog(EXP_ID).metrics]
        for key in keys:
            for level in range(16):
                assert_same_buckets(
                    old.get_metric_buckets(EXP_ID, key, level),
                    new.get_metric_buckets(EXP_ID, key, level),
                )
        assert old.get_experiment_data(EXP_ID).static_params == (
            new.get_experiment_data(EXP_ID).static_params
        )
    finally:
        old.close()
        new.close()


def test_the_fallback_fixture_counts_its_fractional_step_in_the_buckets(
    tmp_path: Path,
) -> None:
    backend = _backend_on(
        _extracted("n_gen1_fallback", tmp_path / "n" / "exp.db"), tmp_path / "store"
    )
    try:
        keys = [m.key for m in backend.get_metric_catalog(EXP_ID).metrics]
        for level in _expected("n_gen1_fallback")["metrics"]["levels"]:
            skipped = {
                key: backend.get_metric_buckets(EXP_ID, key, level).skipped_rows
                for key in keys
            }
            assert skipped == {key: int(key == "loss") for key in keys}, level
        assert backend.get_metric_buckets(EXP_ID, "loss", 0, 3, 250).skipped_rows == 0
    finally:
        backend.close()


def _extracted(name: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True)
    extract_snapshot_db(FIXTURES_DIR / f"{name}.tar", dest)
    return dest


def test_a_fresh_export_has_the_frozen_format(tmp_path: Path) -> None:
    """Changing what an export writes must come with new fixtures."""
    frozen = _expected("i_gen2_sdk_0_6_0")
    tracker = ExperimentTracker(f"sqlite://{tmp_path / 'store'}")
    exp_id = tracker.start_experiment(name="fresh", tags=["fixture"])
    tracker.log_dynamic("loss", 0.5, step=0)
    tracker.log_attachment("notes.txt", "hello")
    tracker.end_experiment(exp_id)
    artifact = tmp_path / "fresh.tar"

    tracker.export(str(artifact), experiment_id=exp_id)

    with tarfile.open(artifact) as tar:
        assert [(m.name, m.mode, m.uid, m.uname, m.mtime) for m in tar][:2] == [
            ("manifest.json", 0o644, 0, "", 0),
            ("exp.db", 0o644, 0, "", 0),
        ]
        assert tar.getnames() == [
            "manifest.json",
            frozen["snapshot_member"],
            "attachments.tar",
            "attachments.index.json",
        ]
    assert _producer_tag(artifact, "experiment") == frozen["producer_tag"]
    payload = read_json_member(artifact, "manifest.json")["payload"]
    assert sorted(payload) == sorted(frozen["manifest_payload"])
    db = tmp_path / "exp.db"
    extract_snapshot_db(artifact, db)
    assert _header(db) == (frozen["page_size"], frozen["wal_header"])
    facts = _schema_facts(db)
    assert facts == {key: frozen[key] for key in facts}
    live_db = tmp_path / "store" / exp_id / "exp.db"
    assert _schema_facts(live_db)["schema_sql"] == frozen["schema_sql"]
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT count(*) FROM metric_points").fetchone() == (1,)
    conn.close()
