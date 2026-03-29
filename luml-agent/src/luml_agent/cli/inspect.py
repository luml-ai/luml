from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import typer

app = typer.Typer(add_completion=False)

DEFAULT_DB = str(Path.home() / ".luml-agent" / "experiments")


@dataclass
class ExperimentRow:
    id: str
    name: str
    status: str
    group_id: str
    created_at: str
    tags: list[str] = field(default_factory=list)
    dynamic_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricPoint:
    step: int
    value: float


@dataclass
class MetricSummary:
    key: str
    steps: int
    final: float
    min_val: float
    max_val: float
    mean_val: float


def _meta_db_path(db: str) -> Path:
    return Path(db) / "meta.db"


def _exp_db_path(db: str, experiment_id: str) -> Path:
    return Path(db) / experiment_id / "exp.db"


def _connect_meta(db: str) -> sqlite3.Connection:
    path = _meta_db_path(db)
    if not path.exists():
        typer.echo(f"Error: experiment DB not found at {path}", err=True)
        raise typer.Exit(1)
    return sqlite3.connect(str(path), check_same_thread=False)


def _connect_exp(db: str, experiment_id: str) -> sqlite3.Connection:
    path = _exp_db_path(db, experiment_id)
    if not path.exists():
        typer.echo(
            f"Error: experiment data not found for {experiment_id}", err=True
        )
        raise typer.Exit(1)
    return sqlite3.connect(str(path), check_same_thread=False)


def _load_experiments(db: str) -> list[ExperimentRow]:
    conn = _connect_meta(db)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, created_at, status, group_id, tags, dynamic_params "
        "FROM experiments ORDER BY created_at DESC"
    )
    rows = []
    for row in cursor.fetchall():
        rows.append(
            ExperimentRow(
                id=row[0],
                name=row[1] or "",
                status=row[3] or "",
                group_id=row[4] or "",
                created_at=row[2] or "",
                tags=json.loads(row[5]) if row[5] else [],
                dynamic_params=json.loads(row[6]) if row[6] else {},
            )
        )
    conn.close()
    return rows


def _load_static_params(db: str, experiment_id: str) -> dict[str, Any]:
    conn = _connect_exp(db, experiment_id)
    cursor = conn.cursor()
    cursor.execute("SELECT key, value, value_type FROM static_params")
    params: dict[str, Any] = {}
    for key, value, value_type in cursor.fetchall():
        params[key] = _convert_param(value, value_type)
    conn.close()
    return params


def _convert_param(value: str, value_type: str) -> Any:  # noqa: ANN401
    if value_type == "int":
        return int(value)
    if value_type == "float":
        return float(value)
    if value_type == "bool":
        return value.lower() in ("true", "1")
    if value_type == "json":
        return json.loads(value)
    return value


def _load_metrics(db: str, experiment_id: str) -> dict[str, list[MetricPoint]]:
    conn = _connect_exp(db, experiment_id)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT key, value, step FROM dynamic_metrics ORDER BY key, step"
    )
    metrics: dict[str, list[MetricPoint]] = {}
    for key, value, step in cursor.fetchall():
        if key not in metrics:
            metrics[key] = []
        metrics[key].append(MetricPoint(step=step, value=value))
    conn.close()
    return metrics


def _compute_metric_summary(points: list[MetricPoint]) -> MetricSummary:
    values = [p.value for p in points]
    return MetricSummary(
        key="",
        steps=len(points),
        final=values[-1],
        min_val=min(values),
        max_val=max(values),
        mean_val=sum(values) / len(values),
    )


def _format_val(v: float) -> str:
    if v == int(v) and abs(v) < 1e10:
        return str(int(v))
    return f"{v:.4g}"


def _format_date(dt_str: str) -> str:
    if not dt_str:
        return ""
    return dt_str[:10]


def _format_tags(tags: list[str]) -> str:
    if not tags:
        return ""
    return "[" + ",".join(tags) + "]"


def _format_metrics_inline(dynamic_params: dict[str, Any]) -> str:
    if not dynamic_params:
        return ""
    parts = []
    for k, v in dynamic_params.items():
        if isinstance(v, (int, float)):
            parts.append(f"{k}={_format_val(v)}")
        else:
            parts.append(f"{k}={v}")
    return " ".join(parts)


@app.command()
def list_cmd(
    db: str = typer.Option(DEFAULT_DB, "--db", help="Experiment DB path"),
    all_rows: bool = typer.Option(False, "--all", help="Show all experiments"),
    limit: int = typer.Option(0, "--limit", help="Max rows to show"),
    group: str = typer.Option("", "--group", help="Filter by group"),
    tag: str = typer.Option("", "--tag", help="Filter by tag"),
) -> None:
    experiments = _load_experiments(db)

    if group:
        experiments = [e for e in experiments if e.group_id == group]
    if tag:
        experiments = [e for e in experiments if tag in e.tags]

    total = len(experiments)
    cap = 20
    if all_rows:
        cap = total
    elif limit > 0:
        cap = limit
    shown = experiments[:cap]

    col_id = max((len(e.id) for e in shown), default=2)
    col_name = max((len(e.name) for e in shown), default=4)
    col_status = max((len(e.status) for e in shown), default=6)
    col_date = 10
    col_tags = max((len(_format_tags(e.tags)) for e in shown), default=4)

    header_id = "ID".ljust(col_id)
    header_name = "NAME".ljust(col_name)
    header_status = "STATUS".ljust(col_status)
    header_date = "CREATED".ljust(col_date)
    header_tags = "TAGS".ljust(col_tags)
    header_metrics = "METRICS(final)"

    typer.echo(
        f"{header_id}  {header_name}  {header_status}  "
        f"{header_date}  {header_tags}  {header_metrics}"
    )

    for e in shown:
        eid = e.id.ljust(col_id)
        ename = e.name.ljust(col_name)
        estatus = e.status.ljust(col_status)
        edate = _format_date(e.created_at).ljust(col_date)
        etags = _format_tags(e.tags).ljust(col_tags)
        emetrics = _format_metrics_inline(e.dynamic_params)
        typer.echo(
            f"{eid}  {ename}  {estatus}  {edate}  {etags}  {emetrics}"
        )

    if cap < total:
        typer.echo(
            f"({cap} of {total} experiments, use --all for full list)"
        )
    else:
        typer.echo(f"({total} of {total} experiments)")


@app.command()
def show(
    experiment_id: str = typer.Argument(..., help="Experiment ID"),
    db: str = typer.Option(DEFAULT_DB, "--db", help="Experiment DB path"),
) -> None:
    conn = _connect_meta(db)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, created_at, status, group_id, tags "
        "FROM experiments WHERE id = ?",
        (experiment_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        typer.echo(f"Error: experiment {experiment_id} not found", err=True)
        raise typer.Exit(1)

    name = row[1] or ""
    created_at = _format_date(row[2] or "")
    status = row[3] or ""
    group_id = row[4] or ""
    tags = json.loads(row[5]) if row[5] else []

    typer.echo(f'EXPERIMENT {experiment_id} "{name}" ({status})')
    tags_str = ", ".join(tags) if tags else ""
    typer.echo(f"Created: {created_at}  Group: {group_id}  Tags: {tags_str}")

    static_params = _load_static_params(db, experiment_id)
    if static_params:
        typer.echo("")
        typer.echo("PARAMS")
        key_width = max(len(k) for k in static_params)
        for k, v in static_params.items():
            typer.echo(f"  {k.ljust(key_width)}  {v}")

    all_metrics = _load_metrics(db, experiment_id)
    if all_metrics:
        typer.echo("")
        typer.echo("METRICS SUMMARY")
        key_width = max(len(k) for k in all_metrics)
        header = (
            f"  {'KEY'.ljust(key_width)}  {'STEPS':>5}  {'FINAL':>8}  "
            f"{'MIN':>8}  {'MAX':>8}  {'MEAN':>8}"
        )
        typer.echo(header)
        for k, points in all_metrics.items():
            s = _compute_metric_summary(points)
            typer.echo(
                f"  {k.ljust(key_width)}  {s.steps:>5}  "
                f"{_format_val(s.final):>8}  {_format_val(s.min_val):>8}  "
                f"{_format_val(s.max_val):>8}  {_format_val(s.mean_val):>8}"
            )


@dataclass
class Bucket:
    step: int
    value: float
    min_val: float
    max_val: float


def _bucket_points(
    points: list[MetricPoint], num_buckets: int
) -> list[Bucket]:
    n = len(points)
    if n == 0:
        return []
    if n <= num_buckets:
        return [
            Bucket(step=p.step, value=p.value, min_val=p.value, max_val=p.value)
            for p in points
        ]
    buckets: list[Bucket] = []
    for i in range(num_buckets):
        start = i * n // num_buckets
        end = (i + 1) * n // num_buckets
        chunk = points[start:end]
        values = [p.value for p in chunk]
        rep = chunk[-1]
        buckets.append(
            Bucket(
                step=rep.step,
                value=rep.value,
                min_val=min(values),
                max_val=max(values),
            )
        )
    return buckets


def _load_metric_key(
    db: str, experiment_id: str, key: str
) -> list[MetricPoint]:
    conn = _connect_exp(db, experiment_id)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT step, value FROM dynamic_metrics WHERE key = ? ORDER BY step",
        (key,),
    )
    points = [MetricPoint(step=row[0], value=row[1]) for row in cursor.fetchall()]
    conn.close()
    return points


@app.command()
def metrics(
    experiment_id: str = typer.Argument(..., help="Experiment ID"),
    key: str = typer.Argument(..., help="Metric key"),
    db: str = typer.Option(DEFAULT_DB, "--db", help="Experiment DB path"),
    all_points: bool = typer.Option(
        False, "--all", help="Show all steps (no bucketing)"
    ),
    last: int = typer.Option(0, "--last", help="Show last N raw data points"),
    every: int = typer.Option(0, "--every", help="Show every Nth step"),
    summary: bool = typer.Option(False, "--summary", help="Only show summary line"),
    buckets: int = typer.Option(20, "--buckets", help="Number of buckets"),
) -> None:
    points = _load_metric_key(db, experiment_id, key)
    if not points:
        typer.echo(f"No data for metric '{key}'")
        return

    total_steps = len(points)

    if summary:
        s = _compute_metric_summary(points)
        s = MetricSummary(
            key=key,
            steps=s.steps,
            final=s.final,
            min_val=s.min_val,
            max_val=s.max_val,
            mean_val=s.mean_val,
        )
        typer.echo(f"{key} ({total_steps} steps)")
        typer.echo(
            f"  FINAL={_format_val(s.final)}  MIN={_format_val(s.min_val)}  "
            f"MAX={_format_val(s.max_val)}  MEAN={_format_val(s.mean_val)}"
        )
        return

    if all_points:
        typer.echo(f"{key} ({total_steps} steps)")
        typer.echo(f"  {'STEP':>8}  {'VALUE':>8}")
        for p in points:
            typer.echo(f"  {p.step:>8}  {_format_val(p.value):>8}")
        return

    if last > 0:
        subset = points[-last:]
        typer.echo(f"{key} (last {len(subset)} of {total_steps} steps)")
        typer.echo(f"  {'STEP':>8}  {'VALUE':>8}")
        for p in subset:
            typer.echo(f"  {p.step:>8}  {_format_val(p.value):>8}")
        return

    if every > 0:
        subset = [p for i, p in enumerate(points) if i % every == 0]
        typer.echo(f"{key} (every {every}, {len(subset)} of {total_steps} steps)")
        typer.echo(f"  {'STEP':>8}  {'VALUE':>8}")
        for p in subset:
            typer.echo(f"  {p.step:>8}  {_format_val(p.value):>8}")
        return

    bucketed = _bucket_points(points, buckets)
    typer.echo(f"{key} ({total_steps} steps, showing {len(bucketed)} buckets)")
    typer.echo(f"  {'STEP':>8}  {'VALUE':>8}  {'MIN':>8}  {'MAX':>8}")
    for b in bucketed:
        typer.echo(
            f"  {b.step:>8}  {_format_val(b.value):>8}  "
            f"{_format_val(b.min_val):>8}  {_format_val(b.max_val):>8}"
        )


@app.command()
def params(
    experiment_id: str = typer.Argument(..., help="Experiment ID"),
    db: str = typer.Option(DEFAULT_DB, "--db", help="Experiment DB path"),
) -> None:
    static_params = _load_static_params(db, experiment_id)
    if not static_params:
        typer.echo("No params recorded.")
        return
    key_width = max(len(k) for k in static_params)
    for k, v in static_params.items():
        typer.echo(f"{k.ljust(key_width)}  {v}")


def _detect_mode(
    *, all_points: bool, last: int, every: int, summary: bool,
) -> str:
    if summary:
        return "summary"
    if all_points or last > 0 or every > 0:
        return "raw"
    return "bucketed"


def _collect_ordered_keys(
    maps: list[dict[str, Any]],
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for m in maps:
        for k in m:
            if k not in seen:
                result.append(k)
                seen.add(k)
    return result


def _print_params_diff(
    experiment_ids: list[str],
    all_params: dict[str, dict[str, Any]],
    id_widths: list[int],
) -> None:
    all_keys = _collect_ordered_keys(list(all_params.values()))
    key_width = max((len(k) for k in all_keys), default=3)

    typer.echo("PARAMS DIFF")
    header_parts = [f"  {'KEY'.ljust(key_width)}"]
    for eid, w in zip(experiment_ids, id_widths, strict=True):
        header_parts.append(eid.ljust(w))
    typer.echo("  ".join(header_parts))

    for k in all_keys:
        val_strs = [
            str(all_params[eid].get(k)) if all_params[eid].get(k) is not None else "-"
            for eid in experiment_ids
        ]
        parts = [f"  {k.ljust(key_width)}"]
        for vs, w in zip(val_strs, id_widths, strict=True):
            parts.append(vs.ljust(w))
        line = "  ".join(parts)
        if len(set(val_strs)) == 1:
            line += "  (same)"
        typer.echo(line)


def _print_metric_summary(
    mk: str,
    experiment_ids: list[str],
    points_per_exp: dict[str, list[MetricPoint]],
    id_widths: list[int],
) -> None:
    typer.echo(f"METRIC: {mk}")
    hdr = [f"  {'':>8}"]
    for eid, w in zip(experiment_ids, id_widths, strict=True):
        hdr.append(eid.center(w))
    typer.echo("  ".join(hdr))
    accessors: list[tuple[str, str]] = [
        ("FINAL", "final"), ("MIN", "min_val"),
        ("MAX", "max_val"), ("MEAN", "mean_val"),
    ]
    for label, attr in accessors:
        row_parts = [f"  {label:>8}"]
        for eid, w in zip(experiment_ids, id_widths, strict=True):
            pts = points_per_exp[eid]
            if pts:
                s = _compute_metric_summary(pts)
                row_parts.append(_format_val(getattr(s, attr)).rjust(w))
            else:
                row_parts.append("-".rjust(w))
        typer.echo("  ".join(row_parts))


def _print_metric_raw(
    mk: str,
    experiment_ids: list[str],
    points_per_exp: dict[str, list[MetricPoint]],
    max_steps: int,
    *,
    all_points: bool,
    last: int,
    every: int,
) -> None:
    typer.echo(f"METRIC: {mk} ({max_steps} steps)")
    col_hdr = [f"  {'STEP':>8}"]
    sub_hdr = [f"  {'':>8}"]
    for eid in experiment_ids:
        col_hdr.append(f"  {eid}")
        sub_hdr.append(f"  {'VAL':>8}")
    typer.echo("".join(col_hdr))
    typer.echo("".join(sub_hdr))

    all_steps: list[int] = []
    steps_seen: set[int] = set()
    for pts in points_per_exp.values():
        selected: list[MetricPoint] = []
        if all_points:
            selected = pts
        elif last > 0:
            selected = pts[-last:]
        elif every > 0:
            selected = [p for i, p in enumerate(pts) if i % every == 0]
        for p in selected:
            if p.step not in steps_seen:
                all_steps.append(p.step)
                steps_seen.add(p.step)
    all_steps.sort()

    step_val_maps = {
        eid: {p.step: p.value for p in points_per_exp[eid]}
        for eid in experiment_ids
    }
    for step in all_steps:
        row = [f"  {step:>8}"]
        for eid in experiment_ids:
            v = step_val_maps[eid].get(step)
            row.append(f"  {_format_val(v) if v is not None else '-':>8}")
        typer.echo("".join(row))


def _print_metric_bucketed(
    mk: str,
    experiment_ids: list[str],
    points_per_exp: dict[str, list[MetricPoint]],
    max_steps: int,
    num_buckets: int,
) -> None:
    typer.echo(f"METRIC: {mk} ({max_steps} steps, {num_buckets} buckets)")
    col_hdr = [f"  {'STEP':>8}"]
    sub_hdr = [f"  {'':>8}"]
    for eid in experiment_ids:
        col_hdr.append(f"    {eid}")
        sub_hdr.append(f"    {'VAL':>8}{'MIN':>5}{'MAX':>5}")
    typer.echo("".join(col_hdr))
    typer.echo("".join(sub_hdr))

    bucketed_data = {
        eid: _bucket_points(pts, num_buckets) if pts else []
        for eid, pts in points_per_exp.items()
    }
    max_bucket_len = max(
        (len(bl) for bl in bucketed_data.values()), default=0
    )
    for i in range(max_bucket_len):
        step_val = next(
            (bucketed_data[eid][i].step for eid in experiment_ids
             if i < len(bucketed_data[eid])),
            None,
        )
        row = [f"  {step_val:>8}" if step_val is not None else f"  {'-':>8}"]
        for eid in experiment_ids:
            if i < len(bucketed_data[eid]):
                b = bucketed_data[eid][i]
                row.append(
                    f"    {_format_val(b.value):>8}"
                    f"{_format_val(b.min_val):>5}"
                    f"{_format_val(b.max_val):>5}"
                )
            else:
                row.append(f"    {'-':>8}{'-':>5}{'-':>5}")
        typer.echo("".join(row))


@app.command()
def compare(
    experiment_ids: list[str] = typer.Argument(  # noqa: B008
        ..., help="Experiment IDs to compare",
    ),
    db: str = typer.Option(DEFAULT_DB, "--db", help="Experiment DB path"),
    all_points: bool = typer.Option(
        False, "--all", help="Show all steps (no bucketing)"
    ),
    last: int = typer.Option(0, "--last", help="Show last N raw data points"),
    every: int = typer.Option(0, "--every", help="Show every Nth step"),
    summary: bool = typer.Option(False, "--summary", help="Only show summary line"),
    buckets: int = typer.Option(20, "--buckets", help="Number of buckets"),
) -> None:
    if len(experiment_ids) < 2:
        typer.echo("Error: compare requires at least 2 experiment IDs", err=True)
        raise typer.Exit(1)

    id_widths = [max(len(eid), 6) for eid in experiment_ids]
    all_params = {eid: _load_static_params(db, eid) for eid in experiment_ids}
    _print_params_diff(experiment_ids, all_params, id_widths)

    exp_metrics = {eid: _load_metrics(db, eid) for eid in experiment_ids}
    all_metric_keys = _collect_ordered_keys(list(exp_metrics.values()))
    mode = _detect_mode(
        all_points=all_points, last=last, every=every, summary=summary,
    )

    for mk in all_metric_keys:
        points_per_exp = {
            eid: exp_metrics[eid].get(mk, []) for eid in experiment_ids
        }
        max_steps = max(
            (len(pts) for pts in points_per_exp.values()), default=0
        )
        if max_steps == 0:
            continue

        typer.echo("")
        if mode == "summary":
            _print_metric_summary(mk, experiment_ids, points_per_exp, id_widths)
        elif mode == "raw":
            _print_metric_raw(
                mk, experiment_ids, points_per_exp, max_steps,
                all_points=all_points, last=last, every=every,
            )
        else:
            _print_metric_bucketed(
                mk, experiment_ids, points_per_exp, max_steps, buckets,
            )


@dataclass
class EvalSample:
    eval_id: str
    dataset_id: str
    inputs: str
    outputs: str | None
    scores: dict[str, Any]


def _load_evals(
    db: str, experiment_id: str, dataset: str = "",
) -> list[EvalSample]:
    conn = _connect_exp(db, experiment_id)
    cursor = conn.cursor()
    if dataset:
        cursor.execute(
            "SELECT id, dataset_id, inputs, outputs, scores "
            "FROM evals WHERE dataset_id = ? ORDER BY dataset_id, id",
            (dataset,),
        )
    else:
        cursor.execute(
            "SELECT id, dataset_id, inputs, outputs, scores "
            "FROM evals ORDER BY dataset_id, id"
        )
    samples: list[EvalSample] = []
    for row in cursor.fetchall():
        scores = json.loads(row[4]) if row[4] else {}
        samples.append(
            EvalSample(
                eval_id=row[0],
                dataset_id=row[1],
                inputs=row[2] or "",
                outputs=row[3],
                scores=scores,
            )
        )
    conn.close()
    return samples


def _truncate(s: str, max_len: int = 40) -> str:
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _format_scores(scores: dict[str, Any]) -> str:
    if not scores:
        return ""
    parts = []
    for k, v in scores.items():
        if isinstance(v, float):
            parts.append(f"{k}={_format_val(v)}")
        else:
            parts.append(f"{k}={v}")
    return " ".join(parts)


@app.command()
def evals(
    experiment_id: str = typer.Argument(..., help="Experiment ID"),
    db: str = typer.Option(DEFAULT_DB, "--db", help="Experiment DB path"),
    all_rows: bool = typer.Option(False, "--all", help="Show all eval samples"),
    limit: int = typer.Option(0, "--limit", help="Max samples to show"),
    dataset: str = typer.Option("", "--dataset", help="Filter by dataset ID"),
) -> None:
    samples = _load_evals(db, experiment_id, dataset=dataset)
    total = len(samples)

    if total == 0:
        typer.echo("No eval samples found.")
        return

    cap = 10
    if all_rows:
        cap = total
    elif limit > 0:
        cap = limit
    shown = samples[:cap]

    col_ds = max(len(s.dataset_id) for s in shown)
    col_ds = max(col_ds, 7)
    col_id = max(len(s.eval_id) for s in shown)
    col_id = max(col_id, 7)

    header = (
        f"{'DATASET'.ljust(col_ds)}  {'EVAL_ID'.ljust(col_id)}  "
        f"{'SCORES':<24}  INPUTS(trunc)"
    )
    typer.echo(header)

    for s in shown:
        ds = s.dataset_id.ljust(col_ds)
        eid = s.eval_id.ljust(col_id)
        scores_str = _format_scores(s.scores).ljust(24)
        inputs_str = _truncate(s.inputs)
        typer.echo(f"{ds}  {eid}  {scores_str}  {inputs_str}")

    if cap < total:
        typer.echo(f"({cap} of {total} samples, use --all for full list)")
    else:
        typer.echo(f"({total} of {total} samples)")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
