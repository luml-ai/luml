import json
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from luml.experiments.backends.data_types import MetricCatalog, MetricSummary
from luml.experiments.backends.metric_store import fetch_metric_catalog
from luml.experiments.backends.migration_runner import (
    ExperimentMigrationRunner,
    read_experiment_schema,
)
from luml.experiments.backends.sqlite import SQLiteBackend
from tests.experiments.metric_helpers import (
    FIXTURES_DIR,
    build_revision2_db,
    make_revision2_store,
)

VECTORS = json.loads((FIXTURES_DIR / "legacy_catalog_vectors.json").read_text())
CASES = {case["name"]: case for case in VECTORS["cases"]}

# The schema of SDK releases before the migration runner (revision 0).
PRE_MIGRATION_DDL = """
CREATE TABLE dynamic_metrics (
    key TEXT,
    value REAL,
    step INTEGER,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (key, step)
);
CREATE INDEX idx_dynamic_metrics_key ON dynamic_metrics (key);
CREATE INDEX idx_dynamic_metrics_step ON dynamic_metrics (step);
CREATE INDEX idx_dynamic_metrics_key_step ON dynamic_metrics (key, step);
CREATE INDEX idx_dynamic_metrics_logged_at ON dynamic_metrics (logged_at);
CREATE INDEX idx_dynamic_metrics_key_logged_at ON dynamic_metrics (key, logged_at);
"""


def _revision0_db(path: Path) -> Path:
    conn = sqlite3.connect(path)
    conn.executescript(PRE_MIGRATION_DDL)
    conn.close()
    return path


def _revision1_db(path: Path) -> Path:
    conn = sqlite3.connect(path)
    ExperimentMigrationRunner(conn).migrate(target_version=1)
    conn.close()
    return path


BUILDERS: dict[int, Callable[[Path], Path]] = {
    0: _revision0_db,
    1: _revision1_db,
    2: build_revision2_db,
}


def _decode(value: Any) -> Any:  # noqa: ANN401
    if isinstance(value, dict):
        return bytes.fromhex(value["blob"])
    return value


def _insert(path: Path, rows: list[list[Any]]) -> None:
    conn = sqlite3.connect(path)
    conn.executemany(
        "INSERT INTO dynamic_metrics (key, value, step) VALUES (?, ?, ?)",
        [tuple(_decode(value) for value in row) for row in rows],
    )
    conn.commit()
    conn.close()


def _catalog(path: Path) -> MetricCatalog:
    conn = sqlite3.connect(path)
    try:
        return fetch_metric_catalog(conn, read_experiment_schema(conn))
    finally:
        conn.close()


def _legacy_db(tmp_path: Path, revision: int, rows: list[list[Any]]) -> Path:
    path = BUILDERS[revision](tmp_path / f"rev{revision}.db")
    _insert(path, rows)
    return path


@pytest.mark.parametrize("revision", [0, 1, 2])
@pytest.mark.parametrize("name", list(CASES))
def test_legacy_catalog_reads_steps_from_the_index(
    tmp_path: Path, revision: int, name: str
) -> None:
    case = CASES[name]
    catalog = _catalog(_legacy_db(tmp_path, revision, case["rows"]))

    assert catalog.revision == revision
    assert catalog.metrics == [
        MetricSummary(key, first, last, None, None, None)
        for key, first, last in case["metrics"]
    ]
    assert catalog.skipped_rows == case["skipped_rows"]


# A partial index may lack rows, so it is not used for the catalog.
@pytest.mark.parametrize(
    "extra_index",
    [
        "",
        "CREATE INDEX idx_partial_key_step ON dynamic_metrics (key, step)"
        " WHERE step >= 0;",
    ],
)
def test_legacy_catalog_without_a_full_key_step_index_is_exact(
    tmp_path: Path, extra_index: str
) -> None:
    path = build_revision2_db(tmp_path / "exp.db")
    conn = sqlite3.connect(path)
    conn.executescript(
        f"""
        DROP TABLE dynamic_metrics;
        CREATE TABLE dynamic_metrics (
            key TEXT, value REAL, step INTEGER,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX idx_dynamic_metrics_key ON dynamic_metrics (key);
        {extra_index}
        """
    )
    conn.close()
    vector = VECTORS["no_index"]
    _insert(path, vector["rows"])

    catalog = _catalog(path)

    assert catalog.metrics == [MetricSummary(*entry) for entry in vector["metrics"]]
    assert catalog.skipped_rows == vector["skipped_rows"]


UNLISTED_KEY_ROWS: list[list[Any]] = [
    ["frac", 1.0, 0.5],
    ["frac", 2.0, 1.5],
    ["frac", 3.0, -2.5],
    ["frac", 1.0, None],
    ["frac", 1.0, "s"],
    ["loss", 1.0, 0],
    ["loss", 2.0, 3],
    ["mixed", 1.0, 1],
    ["mixed", 1.0, 1.5],
    ["mixed", 1.0, "s"],
]


def _without_key_step_index(path: Path) -> Path:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        DROP TABLE dynamic_metrics;
        CREATE TABLE dynamic_metrics (
            key TEXT, value REAL, step INTEGER,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.close()
    return path


# Indexed: 3 REAL steps of "frac", its NULL and text step, the text step of "mixed".
# The scan catalog already counted every non-integer step, so also "mixed" 1.5.
@pytest.mark.parametrize(("indexed", "skipped"), [(True, 6), (False, 7)])
def test_legacy_catalog_counts_the_real_steps_of_a_key_it_cannot_list(
    tmp_path: Path, indexed: bool, skipped: int
) -> None:
    path = build_revision2_db(tmp_path / "exp.db")
    if not indexed:
        _without_key_step_index(path)
    _insert(path, UNLISTED_KEY_ROWS)

    catalog = _catalog(path)

    assert [(m.key, m.first_step, m.last_step) for m in catalog.metrics] == [
        ("loss", 0, 3),
        ("mixed", 1, 1),
    ]
    assert catalog.skipped_rows == skipped


def test_revision_3_catalog_skips_no_rows(tmp_path: Path) -> None:
    store = tmp_path / "store"
    db_path = make_revision2_store(store, "exp")
    _insert(db_path, [row for row in UNLISTED_KEY_ROWS if isinstance(row[2], int)])
    backend = SQLiteBackend(str(store), flush_interval=0)
    backend.log_dynamic("exp", "loss", 0.5, step=4)
    catalog = backend.get_metric_catalog("exp")
    backend.close()

    assert catalog.revision == 4
    assert [m.key for m in catalog.metrics] == ["loss", "mixed"]
    assert catalog.skipped_rows == 0


def _wide_revision2_db(path: Path, keys: int, steps: int) -> Path:
    build_revision2_db(path)
    conn = sqlite3.connect(path)
    conn.executemany(
        "INSERT INTO dynamic_metrics (key, value, step) VALUES (?, ?, ?)",
        ((f"k{key:03}", 0.5, step) for key in range(keys) for step in range(steps)),
    )
    conn.commit()
    conn.close()
    return path


def _traced_catalog(path: Path) -> tuple[list[str], int]:
    conn = sqlite3.connect(path)
    schema = read_experiment_schema(conn)
    statements: list[str] = []
    vm_steps = 0

    def count() -> int:
        nonlocal vm_steps
        vm_steps += 1
        return 0

    conn.set_trace_callback(statements.append)
    conn.set_progress_handler(count, 1)
    fetch_metric_catalog(conn, schema)
    conn.set_progress_handler(None, 1)
    conn.set_trace_callback(None)
    plans = [
        row[3]
        for statement in statements
        # Table-valued pragmas trace their inner statements as `--` comments.
        if not statement.startswith("--")
        for row in conn.execute(f"EXPLAIN QUERY PLAN {statement}")
    ]
    conn.close()
    return plans, vm_steps


@pytest.mark.parametrize("builder", [_revision0_db, build_revision2_db])
def test_legacy_catalog_never_scans_the_table(
    tmp_path: Path, builder: Callable[[Path], Path]
) -> None:
    path = builder(tmp_path / "exp.db")
    _insert(path, CASES["mixed"]["rows"])

    plans, _ = _traced_catalog(path)

    table_plans = [plan for plan in plans if "dynamic_metrics" in plan]
    assert table_plans
    assert all(plan.startswith("SEARCH") for plan in table_plans), table_plans


def test_legacy_catalog_cost_does_not_grow_with_points_per_key(tmp_path: Path) -> None:
    _, small = _traced_catalog(_wide_revision2_db(tmp_path / "small.db", 20, 50))
    _, large = _traced_catalog(_wide_revision2_db(tmp_path / "large.db", 20, 5_000))

    # A scan of the large table alone runs more VM steps than it has rows (100,000).
    assert large < 20_000
    assert large <= small * 1.2


def test_backend_and_flow_read_the_legacy_catalog_with_nulls(tmp_path: Path) -> None:
    store = tmp_path / "store"
    db_path = make_revision2_store(store, "exp")
    _insert(db_path, CASES["mixed"]["rows"])
    backend = SQLiteBackend(str(store), flush_interval=0)
    try:
        catalog = backend.get_metric_catalog("exp")
    finally:
        backend.close()
    assert catalog.revision == 2
    assert [(m.key, m.first_step, m.last_step) for m in catalog.metrics] == [
        tuple(entry) for entry in CASES["mixed"]["metrics"]
    ]
    assert {(m.count, m.min, m.max) for m in catalog.metrics} == {(None, None, None)}
    assert catalog.skipped_rows == CASES["mixed"]["skipped_rows"]
