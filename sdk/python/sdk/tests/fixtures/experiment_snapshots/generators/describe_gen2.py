"""Write the expected-content JSON for a fixture of fixtures i to n (stdlib only).

Metric catalogs and buckets come from a brute force over what was logged
(metric_data), never from SDK code; schema facts come from the artifact. The DB is
cross-checked against both and the script fails on any mismatch.

Usage: describe_gen2.py <artifact.tar> <population.log.json> <out.json> <spec-json>
spec: {"era", "producer", "artifact_kind", "has_annotations"}
"""

import io
import json
import math
import re
import sqlite3
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fixture_data as fd  # noqa: E402
import metric_data as md  # noqa: E402
from describe import cross_check, expected_content  # noqa: E402

SNAPSHOT_RE = re.compile(
    r"^(meta_artifacts/dataforce\.studio~c~~c~experiment_snapshot~c~v[12]~~et~~[^/]+/)?"
    r"exp\.db(\.zip)?$"
)


def load_db(artifact: str) -> tuple[str, Path]:
    with tarfile.open(artifact) as tar:
        (member,) = [name for name in tar.getnames() if SNAPSHOT_RE.match(name)]
        data = tar.extractfile(member).read()  # type: ignore[union-attr]
    if member.endswith(".zip"):
        data = zipfile.ZipFile(io.BytesIO(data)).read("exp.db")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp.write(data)
    return member, Path(tmp.name)


def producer_facts(artifact: str, kind: str) -> tuple[str, Any]:
    with tarfile.open(artifact) as tar:
        if kind == "experiment":
            manifest = json.load(tar.extractfile("manifest.json"))  # type: ignore[arg-type]
            return manifest["producer_tags"][0], manifest["payload"]
        (meta,) = [
            n for n in tar.getnames() if re.fullmatch(r"meta-[0-9a-f]+\.json", n)
        ]
        return json.load(tar.extractfile(meta))[0]["tags"][0], None  # type: ignore[arg-type]


def logged_metrics(content: str) -> list[md.LogEntry]:
    log: list[md.LogEntry] = []
    if content == "full":
        for key, points in fd.metric_points().items():
            log += [(key, value, step) for step, value in points]
        log += [
            (fd.NON_FINITE_METRIC, value, step) for step, value in fd.NON_FINITE_POINTS
        ]
    return log + md.metric_log()


def stored_integer_points(
    conn: sqlite3.Connection,
) -> dict[str, dict[int, float | None]]:
    points: dict[str, dict[int, float | None]] = {}
    for key, step, value in conn.execute(
        "SELECT key, step, value FROM dynamic_metrics "
        "WHERE typeof(step) = 'integer' ORDER BY key, step"
    ):
        points.setdefault(key, {})[step] = value
    return points


def check_stored_buckets(
    conn: sqlite3.Connection, points: dict[str, dict[int, float | None]]
) -> None:
    ids = dict(conn.execute("SELECT key, id FROM metric_keys"))
    for level in (3, 5, 8, 12):
        for key, by_step in points.items():
            stored = conn.execute(
                "SELECT bucket, first_step, last_step, count, finite_count, min, max, "
                "sum FROM metric_buckets WHERE level = ? AND metric_id = ? "
                "ORDER BY bucket",
                (level, ids[key]),
            ).fetchall()
            expected = md.buckets(by_step, level)
            assert len(stored) == len(expected), (key, level)
            for row, want in zip(stored, expected, strict=True):
                got = [*row[:5], md.json_number(row[5]), md.json_number(row[6])]
                assert got == want[:7], (key, level, row, want)
                assert (row[7] is None) == (want[7] is None), (key, level)
                if want[7] is not None:
                    assert math.isclose(row[7], want[7], rel_tol=1e-9, abs_tol=1e-300)


def dump(description: dict[str, Any]) -> str:
    """Indented like the other fixtures, but one line per bucket row."""
    rows: dict[str, str] = {}
    for by_level in description["metrics"]["buckets"].values():
        for level, level_rows in by_level.items():
            tokens = []
            for row in level_rows:
                token = f"@row{len(rows)}@"
                rows[token] = json.dumps(row, allow_nan=False)
                tokens.append(token)
            by_level[level] = tokens
    text = json.dumps(description, indent=2, ensure_ascii=False, allow_nan=False)
    return re.sub(r'"(@row\d+@)"', lambda match: rows[match.group(1)], text)


def main() -> None:
    artifact, log_path, out_json, spec_raw = sys.argv[1:5]
    spec = json.loads(spec_raw)
    population = json.loads(Path(log_path).read_text())
    content = population["content"]
    member, db_path = load_db(artifact)
    header = db_path.read_bytes()[:100]
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    objects = conn.execute(
        "SELECT type, name FROM sqlite_master ORDER BY name"
    ).fetchall()
    tables = {name for kind, name in objects if kind == "table"}

    expected = (
        expected_content(conn, True, spec["has_annotations"])
        if content == "full"
        else {"static_params": fd.STATIC_PARAMS}
    )
    if content == "full":
        cross_check(conn, tables, expected)
    log = logged_metrics(content)
    points = md.stored_points(log)
    assert stored_integer_points(conn) == points
    if "metric_buckets" in tables:
        check_stored_buckets(conn, points)
    # Revisions 0-2 read only the (key, step) index: fractional REAL steps are not
    # counted and the catalog has no count, min or max.
    skipped = conn.execute(
        "SELECT count(*) FROM dynamic_metrics "
        "WHERE typeof(key) <> 'text' OR typeof(step) IN ('null', 'text', 'blob')"
    ).fetchone()[0]
    metric_expectations = md.expectations(log)
    if "metric_points" not in tables:
        for entry in metric_expectations["catalog"]:
            entry.update(count=None, min=None, max=None)

    tag, payload = producer_facts(artifact, spec["artifact_kind"])
    description = {
        "artifact": Path(artifact).name,
        "era": spec["era"],
        "producer": spec["producer"],
        "generation": "real code",
        "artifact_kind": spec["artifact_kind"],
        "artifact_generation": 1 if member.endswith(".zip") else 2,
        "transport": "zip" if member.endswith(".zip") else "raw",
        "producer_tag": tag,
        "manifest_payload": payload,
        "generation_log": population,
        "snapshot_member": member,
        "page_size": int.from_bytes(header[16:18], "big"),
        "wal_header": [header[18], header[19]],
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
                "SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL "
                "ORDER BY name"
            )
        },
        "expected": expected,
        "metrics": {"skipped_rows": skipped, **metric_expectations},
    }
    conn.close()
    db_path.unlink()
    Path(out_json).write_text(dump(description) + "\n", encoding="utf-8")
    sys.stdout.write(f"ok {out_json}\n")


if __name__ == "__main__":
    main()
