"""Write the expected-content JSON for a fixture artifact (stdlib only).

Expected values come from fixture_data (what was logged); schema facts and the stored
form of non-finite metric values come from the artifact itself. Every expected value is
cross-checked against the DB and the script fails on any mismatch.

Usage: describe.py <artifact.tar> <generation.log.json> <out.json> <spec-json-string>
spec: {"era", "producer", "generation", "artifact_kind", "has_data", "has_annotations"}
"""

import json
import math
import sqlite3
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fixture_data as fd  # noqa: E402
from inspect_artifact import load_snapshot, open_db  # noqa: E402

EMPTY_CONTENT: dict[str, Any] = {
    "static_params": {},
    "metrics": {},
    "non_finite_metric": None,
    "attachments": 0,
    "traces": [],
    "datasets": {},
    "eval_annotations": 0,
    "span_annotations": 0,
    "eval_annotation_rationales": [],
}


def metric_stats(points: list[tuple[int, float]]) -> dict[str, float | int]:
    values = [value for _, value in points]
    return {
        "count": len(values),
        "first_step": points[0][0],
        "last_step": points[-1][0],
        "first": values[0],
        "last": values[-1],
        "min": min(values),
        "max": max(values),
    }


def json_number(value: float | None) -> float | str | None:
    if value is None:
        return None
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    return value


def tree_depth(span_id: str, spans: list[dict[str, Any]]) -> int:
    children = [span for span in spans if span["parent_span_id"] == span_id]
    return 1 + max(
        (tree_depth(child["span_id"], spans) for child in children), default=0
    )


def expected_traces() -> list[dict[str, Any]]:
    traces = []
    for trace_id in dict.fromkeys(span["trace_id"] for span in fd.SPANS):
        spans = [span for span in fd.SPANS if span["trace_id"] == trace_id]
        root = next(span for span in spans if span["parent_span_id"] is None)
        traces.append(
            {
                "trace_id": trace_id,
                "span_count": len(spans),
                "root_span": root["name"],
                "span_names": sorted(span["name"] for span in spans),
                "max_depth": tree_depth(root["span_id"], spans),
                "execution_time": max(s["end"] for s in spans)
                - min(s["start"] for s in spans),
                "linked_evals": [e for _, e, t in fd.EVAL_TRACE_LINKS if t == trace_id],
                "span_types": {span["span_id"]: span_type(span) for span in spans},
                "status_messages": {
                    span["span_id"]: span["status_message"]
                    for span in spans
                    if span.get("status_message")
                },
                "events": {s["span_id"]: s["events"] for s in spans if s.get("events")},
                "links": {s["span_id"]: s["links"] for s in spans if s.get("links")},
            }
        )
    return traces


def span_type(span: dict[str, Any]) -> int:
    return {"chat": 1, "execute_tool": 3}.get(
        span["attributes"].get("gen_ai.operation.name"), 0
    )


def expected_datasets() -> dict[str, Any]:
    datasets: dict[str, Any] = {}
    for sample in fd.EVALS:
        dataset = datasets.setdefault(
            sample["dataset_id"], {"eval_ids": [], "evals": {}, "average_scores": {}}
        )
        dataset["eval_ids"].append(sample["id"])
        dataset["evals"][sample["id"]] = {
            key: sample[key] or {}
            for key in ("inputs", "outputs", "refs", "scores", "metadata")
        }
    for dataset_id, dataset in datasets.items():
        sums: dict[str, list[float]] = {}
        for sample in fd.EVALS:
            if sample["dataset_id"] == dataset_id:
                for key, value in (sample["scores"] or {}).items():
                    sums.setdefault(key, []).append(value)
        dataset["average_scores"] = {key: sum(v) / len(v) for key, v in sums.items()}
        dataset["linked"] = next(
            (
                {"eval_id": e, "trace_id": t}
                for d, e, t in fd.EVAL_TRACE_LINKS
                if d == dataset_id
            ),
            None,
        )
    return datasets


def expected_content(
    conn: sqlite3.Connection, has_data: bool, has_annotations: bool
) -> dict:
    if not has_data:
        return EMPTY_CONTENT
    stored = conn.execute(
        "SELECT step, value, typeof(value) FROM dynamic_metrics"
        " WHERE key = ? ORDER BY step",
        (fd.NON_FINITE_METRIC,),
    ).fetchall()
    return {
        "static_params": fd.STATIC_PARAMS,
        "metrics": {
            key: metric_stats(points) for key, points in fd.metric_points().items()
        },
        "non_finite_metric": {
            "name": fd.NON_FINITE_METRIC,
            "logged": [[step, str(value)] for step, value in fd.NON_FINITE_POINTS],
            "stored": [
                {"step": step, "value": json_number(value), "sqlite_type": kind}
                for step, value, kind in stored
            ],
        },
        "attachments": len(fd.ATTACHMENTS),
        "traces": expected_traces(),
        "datasets": expected_datasets(),
        "eval_annotations": len(fd.EVAL_ANNOTATIONS) if has_annotations else 0,
        "span_annotations": len(fd.SPAN_ANNOTATIONS) if has_annotations else 0,
        "eval_annotation_rationales": [
            [a["eval_id"], a["name"], a["rationale"]]
            for a in fd.EVAL_ANNOTATIONS
            if has_annotations and a.get("rationale")
        ],
    }


def count(conn: sqlite3.Connection, tables: set[str], table: str) -> int:
    if table not in tables:
        return 0
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def cross_check(conn: sqlite3.Connection, tables: set[str], content: dict) -> None:
    eval_count = sum(len(d["eval_ids"]) for d in content["datasets"].values())
    assert count(conn, tables, "static_params") == len(content["static_params"])
    assert count(conn, tables, "attachments") == content["attachments"]
    assert count(conn, tables, "evals") == eval_count
    assert count(conn, tables, "spans") == sum(
        t["span_count"] for t in content["traces"]
    )
    assert count(conn, tables, "eval_annotations") == content["eval_annotations"]
    assert count(conn, tables, "span_annotations") == content["span_annotations"]
    for key, stats in content["metrics"].items():
        rows = conn.execute(
            "SELECT step, value FROM dynamic_metrics WHERE key = ? ORDER BY step",
            (key,),
        ).fetchall()
        assert metric_stats(rows) == stats, (key, metric_stats(rows), stats)
    for trace in content["traces"]:
        for span_id, kind in trace["span_types"].items():
            stored = conn.execute(
                "SELECT dfs_span_type FROM spans WHERE span_id = ?", (span_id,)
            ).fetchone()[0]
            assert stored == kind, (span_id, stored, kind)


def main() -> None:
    artifact, log_path, out_json, spec_raw = sys.argv[1:5]
    spec = json.loads(spec_raw)
    member, zip_bytes, _ = load_snapshot(artifact)
    conn, _, _ = open_db(zip_bytes)
    tables = {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    indexes = sorted(
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        if not r[0].startswith("sqlite_autoindex")
    )
    revisions = (
        [
            r[0]
            for r in conn.execute(
                "SELECT version FROM exp_schema_migrations ORDER BY version"
            )
        ]
        if "exp_schema_migrations" in tables
        else []
    )
    content = expected_content(conn, spec["has_data"], spec["has_annotations"])
    cross_check(conn, tables, content)
    description = {
        "artifact": Path(artifact).name,
        "era": spec["era"],
        "producer": spec["producer"],
        "generation": spec["generation"],
        "artifact_kind": spec["artifact_kind"],
        "generation_log": json.loads(Path(log_path).read_text()),
        "snapshot_member": member,
        "user_version": conn.execute("PRAGMA user_version").fetchone()[0],
        "recorded_revisions": revisions,
        "tables": sorted(tables),
        "indexes": indexes,
        "attachments_columns": [
            r[1] for r in conn.execute("PRAGMA table_info(attachments)")
        ],
        "expected": content,
    }
    text = json.dumps(description, indent=2, ensure_ascii=False, allow_nan=False)
    Path(out_json).write_text(text + "\n", encoding="utf-8")
    sys.stdout.write(f"ok {out_json}\n")


if __name__ == "__main__":
    main()
