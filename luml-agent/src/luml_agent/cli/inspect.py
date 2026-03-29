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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
