import io
import math
import shutil
import sqlite3
import struct
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from luml.experiments.backends.data_types import MetricBuckets, MetricCatalog
from luml.experiments.backends.migration_runner import ExperimentMigrationRunner
from luml.experiments.backends.sqlite import SQLiteBackend

FIXTURES_DIR = Path(__file__).parents[1] / "fixtures" / "experiment_snapshots"
BUCKET_LEVELS = range(3, 13)
SUMMABLE_LIMIT = 1e290
SUM_TOLERANCE = 1e-9

# Released SDKs writing through the pre-revision-3 schema.
LEGACY_INSERT = (
    "INSERT OR REPLACE INTO dynamic_metrics (key, value, step, logged_at) "
    "VALUES (?, ?, ?, ?)"
)


@dataclass(frozen=True)
class Aggregate:
    count: int
    finite_count: int
    min: float | None
    max: float | None
    sum: float | None
    first_step: int
    last_step: int
    abs_sum: float


def is_numeric(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def is_summable(value: object) -> bool:
    """What finite_count and sum cover: no sum of such values can overflow."""
    return is_numeric(value) and -SUMMABLE_LIMIT <= value <= SUMMABLE_LIMIT


def aggregate(points: list[tuple[int, object]]) -> Aggregate:
    numeric = [value for _, value in points if is_numeric(value)]
    summable = [value for value in numeric if is_summable(value)]
    steps = [step for step, _ in points]
    return Aggregate(
        count=len(points),
        finite_count=len(summable),
        min=min(numeric) if numeric else None,
        max=max(numeric) if numeric else None,
        sum=math.fsum(summable) if summable else None,
        first_step=min(steps),
        last_step=max(steps),
        abs_sum=math.fsum(abs(value) for value in summable),
    )


def brute_force_buckets(
    points: list[tuple[int, object]], level: int
) -> dict[int, Aggregate]:
    grouped: dict[int, list[tuple[int, object]]] = {}
    for step, value in points:
        grouped.setdefault(step >> (2 * level), []).append((step, value))
    return {bucket: aggregate(group) for bucket, group in sorted(grouped.items())}


def sums_close(actual: float | None, expected: float | None, abs_sum: float) -> bool:
    """Relative 1e-9, measured against the sum of magnitudes: no summation order
    can promise a relative bound on a sum that cancels."""
    if actual is None or expected is None:
        return actual is expected
    return abs(actual - expected) <= SUM_TOLERANCE * max(abs_sum, abs(expected))


def same_value(left: object, right: object) -> bool:
    """Equal by storage class and bytes; NaN never reaches SQLite (it is NULL)."""
    if type(left) is not type(right):
        return False
    if isinstance(left, float):
        return struct.pack("<d", left) == struct.pack("<d", right)
    return left == right


def assert_bucket_invariants(conn: sqlite3.Connection) -> None:
    """Checks I1-I3 by recomputing every bucket from metric_points in Python, all
    from one snapshot, since writers may commit meanwhile."""
    conn.execute("BEGIN")
    try:
        _assert_bucket_invariants(conn)
    finally:
        conn.rollback()


def _assert_bucket_invariants(conn: sqlite3.Connection) -> None:
    orphans = conn.execute(
        "SELECT DISTINCT metric_id FROM metric_points "
        "WHERE metric_id NOT IN (SELECT id FROM metric_keys)"
    ).fetchall()
    assert orphans == [], f"I3: points without a key: {orphans}"

    points: dict[int, list[tuple[int, object]]] = {}
    for metric_id, step, value in conn.execute(
        "SELECT metric_id, step, value FROM metric_points ORDER BY metric_id, step"
    ):
        points.setdefault(metric_id, []).append((step, value))

    stray = conn.execute(
        "SELECT DISTINCT level FROM metric_buckets WHERE level NOT BETWEEN 3 AND 12"
    ).fetchall()
    assert stray == [], f"buckets at levels that are not stored: {stray}"

    for level in BUCKET_LEVELS:
        stored: dict[tuple[int, int], tuple[object, ...]] = {
            (row[0], row[1]): row[2:]
            for row in conn.execute(
                "SELECT metric_id, bucket, count, finite_count, min, max, sum, "
                "first_step, last_step FROM metric_buckets WHERE level = ?",
                (level,),
            )
        }
        expected = {
            (metric_id, bucket): agg
            for metric_id, metric_points in points.items()
            for bucket, agg in brute_force_buckets(metric_points, level).items()
        }
        assert set(stored) == set(expected), (
            f"I2 at level {level}: missing {set(expected) - set(stored)}, "
            f"extra {set(stored) - set(expected)}"
        )
        for bucket_key, agg in expected.items():
            count, finite_count, low, high, total, first, last = stored[bucket_key]
            context = f"I1 at level {level}, bucket {bucket_key}"
            assert (count, finite_count, first, last) == (
                agg.count,
                agg.finite_count,
                agg.first_step,
                agg.last_step,
            ), context
            assert (low, high) == (agg.min, agg.max), context
            assert sums_close(total, agg.sum, agg.abs_sum), (context, total, agg.sum)


def assert_same_buckets(
    left: MetricBuckets, right: MetricBuckets, *, check_sum: bool = True
) -> None:
    """`check_sum=False` for data whose sums cancel: compare each with the exact sum."""
    assert (left.key, left.level, left.first_step, left.last_step) == (
        right.key,
        right.level,
        right.first_step,
        right.last_step,
    )
    assert len(left.buckets) == len(right.buckets)
    for a, b in zip(left.buckets, right.buckets, strict=True):
        assert (
            a.bucket,
            a.first_step,
            a.last_step,
            a.count,
            a.finite_count,
            a.min,
            a.max,
        ) == (
            b.bucket,
            b.first_step,
            b.last_step,
            b.count,
            b.finite_count,
            b.min,
            b.max,
        )
        if check_sum:
            scale = max(abs(a.sum or 0.0), abs(b.sum or 0.0))
            assert sums_close(a.sum, b.sum, scale), (a, b)
        else:
            assert (a.sum is None) == (b.sum is None), (a, b)


def catalog_steps(catalog: MetricCatalog) -> list[tuple[str, int, int]]:
    return [(m.key, m.first_step, m.last_step) for m in catalog.metrics]


def assert_same_catalog(left: MetricCatalog, right: MetricCatalog) -> None:
    """Below revision 3 a catalog has no count, min or max, so only steps compare."""
    for catalog in (left, right):
        if catalog.revision < 3:
            assert all(
                (m.count, m.min, m.max) == (None, None, None) for m in catalog.metrics
            )
    if left.revision >= 3 and right.revision >= 3:
        assert left.metrics == right.metrics
    else:
        assert catalog_steps(left) == catalog_steps(right)


def extract_fixture_db(name: str, dest: Path) -> Path:
    with tarfile.open(FIXTURES_DIR / f"{name}.tar") as tar:
        member = next(
            n for n in tar.getnames() if n.endswith(("exp.db.zip", "/exp.db", "exp.db"))
        )
        extracted = tar.extractfile(member)
        assert extracted is not None
        data = extracted.read()
    if member.endswith(".zip"):
        data = zipfile.ZipFile(io.BytesIO(data)).read("exp.db")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest


def replace_experiment_db(store: Path, experiment_id: str, source: Path) -> Path:
    """Puts `source` in place of the experiment's database, with no WAL files."""
    db_path = store / experiment_id / "exp.db"
    for suffix in ("-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    shutil.copyfile(source, db_path)
    return db_path


def make_store(store: Path, experiment_id: str) -> None:
    backend = SQLiteBackend(str(store), flush_interval=0)
    backend.initialize_experiment(experiment_id, name=experiment_id)
    backend.close()


def build_revision2_db(path: Path) -> Path:
    """A database as released SDKs create it: migrations 001 and 002 only."""
    (path.parent / "attachments").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        ExperimentMigrationRunner(conn).migrate(target_version=2)
    finally:
        conn.close()
    return path


def make_revision2_store(store: Path, experiment_id: str) -> Path:
    make_store(store, experiment_id)
    db_path = store / experiment_id / "exp.db"
    for suffix in ("", "-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    return build_revision2_db(db_path)


def schema_snapshot(db_path: Path) -> tuple[list[tuple[str, str, str | None]], int]:
    conn = sqlite3.connect(db_path)
    try:
        master = conn.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall()
        return master, conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()
