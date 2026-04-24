from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from luml_prisma.cli.inspect import app

runner = CliRunner()


def _create_meta_db(db_path: Path) -> None:
    meta = db_path / "meta.db"
    conn = sqlite3.connect(str(meta))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE experiment_groups (
            id TEXT PRIMARY KEY,
            name TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tags TEXT,
            last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX idx_experiment_groups_name "
        "ON experiment_groups(name)"
    )
    conn.execute(
        """
        CREATE TABLE experiments (
            id TEXT PRIMARY KEY,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active',
            tags TEXT,
            group_id TEXT REFERENCES experiment_groups(id),
            static_params TEXT,
            dynamic_params TEXT,
            duration REAL,
            description TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE models (
            id TEXT PRIMARY KEY,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tags TEXT,
            path TEXT,
            size INTEGER,
            experiment_id TEXT REFERENCES experiments(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.executemany(
        "INSERT INTO schema_migrations (version) VALUES (?)",
        [(1,), (2,), (3,)],
    )
    conn.execute(
        "INSERT INTO experiment_groups (id, name) VALUES ('g1', 'default')"
    )
    conn.commit()
    conn.close()


def _create_exp_db(db_path: Path, experiment_id: str) -> None:
    exp_dir = db_path / experiment_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    exp_db = exp_dir / "exp.db"
    conn = sqlite3.connect(str(exp_db))
    conn.execute(
        """
        CREATE TABLE static_params (
            key TEXT PRIMARY KEY,
            value TEXT,
            value_type TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE dynamic_metrics (
            key TEXT,
            value REAL,
            step INTEGER,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (key, step)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE attachments (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            file_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            size INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE spans (
            trace_id TEXT NOT NULL,
            span_id TEXT NOT NULL,
            parent_span_id TEXT,
            name TEXT NOT NULL,
            kind INTEGER,
            dfs_span_type INTEGER NOT NULL DEFAULT 0,
            start_time_unix_nano BIGINT NOT NULL,
            end_time_unix_nano BIGINT NOT NULL,
            status_code INTEGER,
            status_message TEXT,
            attributes TEXT,
            events TEXT,
            links TEXT,
            trace_flags INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (trace_id, span_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE evals (
            id TEXT NOT NULL,
            dataset_id TEXT NOT NULL,
            inputs TEXT NOT NULL,
            outputs TEXT,
            refs TEXT,
            scores TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (dataset_id, id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE eval_traces_bridge (
            id TEXT PRIMARY KEY,
            eval_dataset_id TEXT NOT NULL,
            eval_id TEXT NOT NULL,
            trace_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE eval_annotations (
            id TEXT PRIMARY KEY,
            dataset_id TEXT NOT NULL,
            eval_id TEXT NOT NULL,
            name TEXT NOT NULL,
            annotation_kind TEXT NOT NULL
                CHECK(annotation_kind IN ('feedback', 'expectation')),
            value_type TEXT NOT NULL
                CHECK(value_type IN ('int', 'bool', 'string')),
            value TEXT NOT NULL,
            user TEXT NOT NULL,
            rationale TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (dataset_id, eval_id) REFERENCES evals(dataset_id, id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE span_annotations (
            id TEXT PRIMARY KEY,
            trace_id TEXT NOT NULL,
            span_id TEXT NOT NULL,
            name TEXT NOT NULL,
            annotation_kind TEXT NOT NULL
                CHECK(annotation_kind IN ('feedback', 'expectation')),
            value_type TEXT NOT NULL
                CHECK(value_type IN ('int', 'bool', 'string')),
            value TEXT NOT NULL,
            user TEXT NOT NULL,
            rationale TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (trace_id, span_id) REFERENCES spans(trace_id, span_id)
        )
        """
    )
    conn.execute("PRAGMA user_version = 2")
    conn.commit()
    conn.close()


def _seed_experiment(
    db_path: Path,
    experiment_id: str,
    name: str,
    status: str = "completed",
    group_id: str = "g1",
    tags: list[str] | None = None,
    static_params: dict[str, tuple[str, str]] | None = None,
    metrics: dict[str, list[tuple[int, float]]] | None = None,
) -> None:
    dynamic_params: dict[str, float] = {}
    if metrics:
        for key, points in metrics.items():
            if points:
                dynamic_params[key] = points[-1][1]

    meta = db_path / "meta.db"
    conn = sqlite3.connect(str(meta))
    conn.execute(
        "INSERT INTO experiments "
        "(id, name, created_at, status, group_id, tags, dynamic_params) "
        "VALUES (?, ?, '2026-03-28 10:00:00', ?, ?, ?, ?)",
        (
            experiment_id,
            name,
            status,
            group_id,
            json.dumps(tags) if tags else None,
            json.dumps(dynamic_params) if dynamic_params else None,
        ),
    )
    conn.commit()
    conn.close()

    _create_exp_db(db_path, experiment_id)

    if static_params:
        exp_db = db_path / experiment_id / "exp.db"
        conn = sqlite3.connect(str(exp_db))
        for key, (value, value_type) in static_params.items():
            conn.execute(
                "INSERT INTO static_params (key, value, value_type) VALUES (?, ?, ?)",
                (key, value, value_type),
            )
        conn.commit()
        conn.close()

    if metrics:
        exp_db = db_path / experiment_id / "exp.db"
        conn = sqlite3.connect(str(exp_db))
        for metric_key, points in metrics.items():
            for step, val in points:
                conn.execute(
                    "INSERT INTO dynamic_metrics (key, value, step) "
                    "VALUES (?, ?, ?)",
                    (metric_key, val, step),
                )
        conn.commit()
        conn.close()


def _seed_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "experiments"
    db_path.mkdir()
    _create_meta_db(db_path)

    _seed_experiment(
        db_path,
        experiment_id="abc-123",
        name="baseline-lr",
        tags=["gbt", "v1"],
        static_params={
            "learning_rate": ("0.01", "float"),
            "batch_size": ("32", "int"),
            "model_type": ("gradient_boosting", "str"),
        },
        metrics={
            "accuracy": [(i, 0.41 + 0.51 * (i / 500)) for i in range(1, 501)],
            "loss": [(i, 1.24 - 1.16 * (i / 500)) for i in range(1, 501)],
        },
    )

    _seed_experiment(
        db_path,
        experiment_id="def-456",
        name="high-lr",
        tags=["gbt", "v1"],
        static_params={
            "learning_rate": ("0.1", "float"),
            "batch_size": ("32", "int"),
            "model_type": ("gradient_boosting", "str"),
        },
        metrics={
            "accuracy": [(i, 0.39 + 0.49 * (i / 500)) for i in range(1, 501)],
            "loss": [(i, 1.30 - 1.18 * (i / 500)) for i in range(1, 501)],
        },
    )

    return db_path


def _seed_evals(
    db_path: Path,
    experiment_id: str,
    evals_data: list[dict[str, Any]],
) -> None:
    exp_db = db_path / experiment_id / "exp.db"
    conn = sqlite3.connect(str(exp_db))
    for ev in evals_data:
        conn.execute(
            "INSERT INTO evals (id, dataset_id, inputs, outputs, scores) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                ev["id"],
                ev["dataset_id"],
                json.dumps(ev.get("inputs", {})),
                json.dumps(ev.get("outputs")) if ev.get("outputs") else None,
                json.dumps(ev.get("scores")) if ev.get("scores") else None,
            ),
        )
    conn.commit()
    conn.close()


def _seed_db_three(tmp_path: Path) -> Path:
    db_path = _seed_db(tmp_path)
    _seed_experiment(
        db_path,
        experiment_id="ghi-789",
        name="med-lr",
        tags=["gbt", "v2"],
        static_params={
            "learning_rate": ("0.05", "float"),
            "batch_size": ("64", "int"),
            "model_type": ("gradient_boosting", "str"),
        },
        metrics={
            "accuracy": [(i, 0.40 + 0.50 * (i / 500)) for i in range(1, 501)],
            "loss": [(i, 1.27 - 1.17 * (i / 500)) for i in range(1, 501)],
        },
    )
    return db_path


class TestListCommand:
    def test_list_shows_experiments(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(app, ["list-cmd", "--db", str(db_path)])
        assert result.exit_code == 0
        assert "abc-123" in result.output
        assert "def-456" in result.output
        assert "baseline-lr" in result.output
        assert "high-lr" in result.output

    def test_list_shows_final_metrics(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(app, ["list-cmd", "--db", str(db_path)])
        assert result.exit_code == 0
        assert "accuracy=" in result.output
        assert "loss=" in result.output

    def test_list_shows_tags(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(app, ["list-cmd", "--db", str(db_path)])
        assert result.exit_code == 0
        assert "[gbt,v1]" in result.output

    def test_list_default_cap_20(self, tmp_path: Path) -> None:
        db_path = tmp_path / "experiments"
        db_path.mkdir()
        _create_meta_db(db_path)
        for i in range(50):
            _seed_experiment(
                db_path,
                experiment_id=f"exp-{i:03d}",
                name=f"experiment-{i}",
            )

        result = runner.invoke(app, ["list-cmd", "--db", str(db_path)])
        assert result.exit_code == 0
        assert "(20 of 50 experiments, use --all for full list)" in result.output
        lines = [
            ln for ln in result.output.strip().split("\n")
            if ln.startswith("exp-")
        ]
        assert len(lines) == 20

    def test_list_all_override(self, tmp_path: Path) -> None:
        db_path = tmp_path / "experiments"
        db_path.mkdir()
        _create_meta_db(db_path)
        for i in range(30):
            _seed_experiment(
                db_path,
                experiment_id=f"exp-{i:03d}",
                name=f"experiment-{i}",
            )

        result = runner.invoke(
            app, ["list-cmd", "--db", str(db_path), "--all"],
        )
        assert result.exit_code == 0
        assert "(30 of 30 experiments)" in result.output
        lines = [
            ln for ln in result.output.strip().split("\n")
            if ln.startswith("exp-")
        ]
        assert len(lines) == 30

    def test_list_limit_flag(self, tmp_path: Path) -> None:
        db_path = tmp_path / "experiments"
        db_path.mkdir()
        _create_meta_db(db_path)
        for i in range(30):
            _seed_experiment(
                db_path,
                experiment_id=f"exp-{i:03d}",
                name=f"experiment-{i}",
            )

        result = runner.invoke(
            app, ["list-cmd", "--db", str(db_path), "--limit", "5"],
        )
        assert result.exit_code == 0
        assert "(5 of 30 experiments, use --all for full list)" in result.output

    def test_list_group_filter(self, tmp_path: Path) -> None:
        db_path = tmp_path / "experiments"
        db_path.mkdir()
        _create_meta_db(db_path)
        _seed_experiment(db_path, "e1", "in-group", group_id="g1")
        _seed_experiment(db_path, "e2", "other", group_id="g2")

        result = runner.invoke(
            app, ["list-cmd", "--db", str(db_path), "--group", "g1"],
        )
        assert result.exit_code == 0
        assert "e1" in result.output
        assert "e2" not in result.output

    def test_list_tag_filter(self, tmp_path: Path) -> None:
        db_path = tmp_path / "experiments"
        db_path.mkdir()
        _create_meta_db(db_path)
        _seed_experiment(db_path, "e1", "tagged", tags=["gpu"])
        _seed_experiment(db_path, "e2", "untagged", tags=["cpu"])

        result = runner.invoke(
            app, ["list-cmd", "--db", str(db_path), "--tag", "gpu"],
        )
        assert result.exit_code == 0
        assert "e1" in result.output
        assert "e2" not in result.output

    def test_list_footer_count(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(app, ["list-cmd", "--db", str(db_path)])
        assert result.exit_code == 0
        assert "(2 of 2 experiments)" in result.output

    def test_list_header_present(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(app, ["list-cmd", "--db", str(db_path)])
        assert result.exit_code == 0
        first_line = result.output.strip().split("\n")[0]
        assert "ID" in first_line
        assert "NAME" in first_line
        assert "STATUS" in first_line
        assert "METRICS(final)" in first_line


class TestShowCommand:
    def test_show_metadata(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(
            app, ["show", "abc-123", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert 'EXPERIMENT abc-123 "baseline-lr" (completed)' in result.output
        assert "2026-03-28" in result.output
        assert "gbt, v1" in result.output

    def test_show_params(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(
            app, ["show", "abc-123", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert "PARAMS" in result.output
        assert "learning_rate" in result.output
        assert "0.01" in result.output
        assert "batch_size" in result.output
        assert "32" in result.output

    def test_show_metrics_summary(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(
            app, ["show", "abc-123", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert "METRICS SUMMARY" in result.output
        assert "accuracy" in result.output
        assert "loss" in result.output
        assert "STEPS" in result.output
        assert "FINAL" in result.output
        assert "MIN" in result.output
        assert "MAX" in result.output
        assert "MEAN" in result.output

    def test_show_metrics_summary_values(self, tmp_path: Path) -> None:
        db_path = tmp_path / "experiments"
        db_path.mkdir()
        _create_meta_db(db_path)
        _seed_experiment(
            db_path,
            experiment_id="s1",
            name="simple",
            metrics={"acc": [(1, 0.5), (2, 0.7), (3, 0.9)]},
        )
        result = runner.invoke(
            app, ["show", "s1", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert "3" in result.output  # steps
        assert "0.9" in result.output  # final
        assert "0.5" in result.output  # min
        assert "0.7" in result.output  # mean

    def test_show_not_found(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(
            app, ["show", "nonexistent", "--db", str(db_path)],
        )
        assert result.exit_code != 0

    def test_show_group_display(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(
            app, ["show", "abc-123", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert "Group: g1" in result.output


class TestParamsCommand:
    def test_params_basic(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(
            app, ["params", "abc-123", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert "learning_rate" in result.output
        assert "0.01" in result.output
        assert "batch_size" in result.output
        assert "32" in result.output
        assert "model_type" in result.output
        assert "gradient_boosting" in result.output

    def test_params_compact_format(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(
            app, ["params", "abc-123", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        lines = [ln for ln in result.output.strip().split("\n") if ln.strip()]
        assert len(lines) == 3
        assert "PARAMS" not in result.output

    def test_params_no_params(self, tmp_path: Path) -> None:
        db_path = tmp_path / "experiments"
        db_path.mkdir()
        _create_meta_db(db_path)
        _seed_experiment(db_path, "e1", "no-params")
        result = runner.invoke(
            app, ["params", "e1", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert "No params recorded" in result.output

    def test_params_type_conversion(self, tmp_path: Path) -> None:
        db_path = tmp_path / "experiments"
        db_path.mkdir()
        _create_meta_db(db_path)
        _seed_experiment(
            db_path,
            experiment_id="typed",
            name="typed-params",
            static_params={
                "lr": ("0.001", "float"),
                "epochs": ("100", "int"),
                "use_gpu": ("true", "bool"),
                "config": ('{"a": 1}', "json"),
                "label": ("test", "str"),
            },
        )
        result = runner.invoke(
            app, ["params", "typed", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert "0.001" in result.output
        assert "100" in result.output
        assert "True" in result.output


class TestMetricsCommand:
    def test_metrics_default_bucketing(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(
            app, ["metrics", "abc-123", "accuracy", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert "accuracy (500 steps, showing 20 buckets)" in result.output
        assert "STEP" in result.output
        assert "VALUE" in result.output
        assert "MIN" in result.output
        assert "MAX" in result.output
        data_lines = [
            ln
            for ln in result.output.strip().split("\n")
            if ln.strip() and ln.strip()[0].isdigit()
        ]
        assert len(data_lines) == 20

    def test_metrics_bucketing_values(self, tmp_path: Path) -> None:
        db_path = tmp_path / "experiments"
        db_path.mkdir()
        _create_meta_db(db_path)
        _seed_experiment(
            db_path,
            experiment_id="bkt",
            name="bucket-test",
            metrics={
                "val": [
                    (1, 10.0),
                    (2, 20.0),
                    (3, 5.0),
                    (4, 15.0),
                    (5, 25.0),
                    (6, 8.0),
                ],
            },
        )
        result = runner.invoke(
            app,
            ["metrics", "bkt", "val", "--db", str(db_path), "--buckets", "2"],
        )
        assert result.exit_code == 0
        assert "6 steps, showing 2 buckets" in result.output
        lines = [
            ln
            for ln in result.output.strip().split("\n")
            if ln.strip() and ln.strip()[0].isdigit()
        ]
        assert len(lines) == 2
        # Bucket 1: steps 1-3, values [10, 20, 5], rep step=3, val=5, min=5, max=20
        assert "3" in lines[0]
        assert "5" in lines[0]
        assert "20" in lines[0]
        # Bucket 2: steps 4-6, values [15, 25, 8], rep step=6, val=8, min=8, max=25
        assert "6" in lines[1]
        assert "8" in lines[1]
        assert "25" in lines[1]

    def test_metrics_all_flag(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(
            app, ["metrics", "abc-123", "accuracy", "--db", str(db_path), "--all"],
        )
        assert result.exit_code == 0
        assert "accuracy (500 steps)" in result.output
        assert "MIN" not in result.output
        assert "MAX" not in result.output
        data_lines = [
            ln
            for ln in result.output.strip().split("\n")
            if ln.strip() and ln.strip()[0].isdigit()
        ]
        assert len(data_lines) == 500

    def test_metrics_last_flag(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(
            app,
            ["metrics", "abc-123", "accuracy", "--db", str(db_path), "--last", "10"],
        )
        assert result.exit_code == 0
        assert "last 10 of 500 steps" in result.output
        data_lines = [
            ln
            for ln in result.output.strip().split("\n")
            if ln.strip() and ln.strip()[0].isdigit()
        ]
        assert len(data_lines) == 10
        # Should contain the last step
        assert "500" in data_lines[-1]

    def test_metrics_every_flag(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(
            app,
            ["metrics", "abc-123", "accuracy", "--db", str(db_path), "--every", "100"],
        )
        assert result.exit_code == 0
        assert "every 100" in result.output
        data_lines = [
            ln
            for ln in result.output.strip().split("\n")
            if ln.strip() and ln.strip()[0].isdigit()
        ]
        assert len(data_lines) == 5  # steps 0, 100, 200, 300, 400 (0-indexed)

    def test_metrics_summary_flag(self, tmp_path: Path) -> None:
        db_path = tmp_path / "experiments"
        db_path.mkdir()
        _create_meta_db(db_path)
        _seed_experiment(
            db_path,
            experiment_id="s1",
            name="summary-test",
            metrics={"acc": [(1, 0.5), (2, 0.7), (3, 0.9)]},
        )
        result = runner.invoke(
            app,
            ["metrics", "s1", "acc", "--db", str(db_path), "--summary"],
        )
        assert result.exit_code == 0
        assert "acc (3 steps)" in result.output
        assert "FINAL=0.9" in result.output
        assert "MIN=0.5" in result.output
        assert "MAX=0.9" in result.output
        assert "MEAN=" in result.output
        assert "STEP" not in result.output

    def test_metrics_custom_buckets(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(
            app,
            [
                "metrics", "abc-123", "accuracy",
                "--db", str(db_path), "--buckets", "5",
            ],
        )
        assert result.exit_code == 0
        assert "showing 5 buckets" in result.output
        data_lines = [
            ln
            for ln in result.output.strip().split("\n")
            if ln.strip() and ln.strip()[0].isdigit()
        ]
        assert len(data_lines) == 5

    def test_metrics_fewer_steps_than_buckets(self, tmp_path: Path) -> None:
        db_path = tmp_path / "experiments"
        db_path.mkdir()
        _create_meta_db(db_path)
        _seed_experiment(
            db_path,
            experiment_id="few",
            name="few-steps",
            metrics={"acc": [(1, 0.5), (2, 0.7), (3, 0.9)]},
        )
        result = runner.invoke(
            app,
            ["metrics", "few", "acc", "--db", str(db_path), "--buckets", "20"],
        )
        assert result.exit_code == 0
        assert "showing 3 buckets" in result.output
        data_lines = [
            ln
            for ln in result.output.strip().split("\n")
            if ln.strip() and ln.strip()[0].isdigit()
        ]
        assert len(data_lines) == 3

    def test_metrics_single_step(self, tmp_path: Path) -> None:
        db_path = tmp_path / "experiments"
        db_path.mkdir()
        _create_meta_db(db_path)
        _seed_experiment(
            db_path,
            experiment_id="one",
            name="one-step",
            metrics={"acc": [(1, 0.42)]},
        )
        result = runner.invoke(
            app, ["metrics", "one", "acc", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert "1 steps, showing 1 buckets" in result.output
        assert "0.42" in result.output

    def test_metrics_empty(self, tmp_path: Path) -> None:
        db_path = tmp_path / "experiments"
        db_path.mkdir()
        _create_meta_db(db_path)
        _seed_experiment(db_path, experiment_id="emp", name="empty")
        result = runner.invoke(
            app, ["metrics", "emp", "acc", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert "No data for metric 'acc'" in result.output

    def test_metrics_last_exceeds_total(self, tmp_path: Path) -> None:
        db_path = tmp_path / "experiments"
        db_path.mkdir()
        _create_meta_db(db_path)
        _seed_experiment(
            db_path,
            experiment_id="sm",
            name="small",
            metrics={"acc": [(1, 0.5), (2, 0.7)]},
        )
        result = runner.invoke(
            app,
            ["metrics", "sm", "acc", "--db", str(db_path), "--last", "100"],
        )
        assert result.exit_code == 0
        assert "last 2 of 2 steps" in result.output
        data_lines = [
            ln
            for ln in result.output.strip().split("\n")
            if ln.strip() and ln.strip()[0].isdigit()
        ]
        assert len(data_lines) == 2


class TestDbFlag:
    def test_custom_db_path(self, tmp_path: Path) -> None:
        custom_path = tmp_path / "custom-db"
        custom_path.mkdir()
        _create_meta_db(custom_path)
        _seed_experiment(custom_path, "c1", "custom-exp")

        result = runner.invoke(
            app, ["list-cmd", "--db", str(custom_path)],
        )
        assert result.exit_code == 0
        assert "c1" in result.output

    def test_missing_db_errors(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["list-cmd", "--db", str(tmp_path / "nonexistent")],
        )
        assert result.exit_code != 0

    def test_db_flag_on_show(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(
            app, ["show", "abc-123", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert "abc-123" in result.output

    def test_db_flag_on_params(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(
            app, ["params", "abc-123", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert "learning_rate" in result.output


class TestCompareCommand:
    def test_compare_two_experiments(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(
            app,
            ["compare", "abc-123", "def-456", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert "PARAMS DIFF" in result.output
        assert "abc-123" in result.output
        assert "def-456" in result.output
        assert "learning_rate" in result.output
        assert "METRIC: accuracy" in result.output
        assert "METRIC: loss" in result.output

    def test_compare_three_experiments(self, tmp_path: Path) -> None:
        db_path = _seed_db_three(tmp_path)
        result = runner.invoke(
            app,
            [
                "compare", "abc-123", "def-456", "ghi-789",
                "--db", str(db_path),
            ],
        )
        assert result.exit_code == 0
        assert "PARAMS DIFF" in result.output
        assert "abc-123" in result.output
        assert "def-456" in result.output
        assert "ghi-789" in result.output
        assert "learning_rate" in result.output
        assert "batch_size" in result.output

    def test_compare_params_diff_same_marker(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(
            app,
            ["compare", "abc-123", "def-456", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        batch_line = [ln for ln in lines if "batch_size" in ln][0]
        assert "(same)" in batch_line
        lr_line = [ln for ln in lines if "learning_rate" in ln][0]
        assert "(same)" not in lr_line

    def test_compare_params_diff_three_mixed(self, tmp_path: Path) -> None:
        db_path = _seed_db_three(tmp_path)
        result = runner.invoke(
            app,
            [
                "compare", "abc-123", "def-456", "ghi-789",
                "--db", str(db_path),
            ],
        )
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        model_line = [ln for ln in lines if "model_type" in ln][0]
        assert "(same)" in model_line
        batch_line = [ln for ln in lines if "batch_size" in ln][0]
        assert "(same)" not in batch_line

    def test_compare_default_bucketing(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(
            app,
            ["compare", "abc-123", "def-456", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert "20 buckets" in result.output

    def test_compare_summary_flag(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(
            app,
            [
                "compare", "abc-123", "def-456",
                "--db", str(db_path), "--summary",
            ],
        )
        assert result.exit_code == 0
        assert "PARAMS DIFF" in result.output
        assert "METRIC: accuracy" in result.output
        assert "FINAL" in result.output
        assert "MIN" in result.output
        assert "MAX" in result.output
        assert "MEAN" in result.output
        assert "STEP" not in result.output

    def test_compare_custom_buckets(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(
            app,
            [
                "compare", "abc-123", "def-456",
                "--db", str(db_path), "--buckets", "5",
            ],
        )
        assert result.exit_code == 0
        assert "5 buckets" in result.output

    def test_compare_all_flag(self, tmp_path: Path) -> None:
        db_path = tmp_path / "experiments"
        db_path.mkdir()
        _create_meta_db(db_path)
        _seed_experiment(
            db_path, "e1", "exp1",
            static_params={"lr": ("0.01", "float")},
            metrics={"acc": [(1, 0.5), (2, 0.7), (3, 0.9)]},
        )
        _seed_experiment(
            db_path, "e2", "exp2",
            static_params={"lr": ("0.1", "float")},
            metrics={"acc": [(1, 0.4), (2, 0.6), (3, 0.8)]},
        )
        result = runner.invoke(
            app,
            ["compare", "e1", "e2", "--db", str(db_path), "--all"],
        )
        assert result.exit_code == 0
        assert "buckets" not in result.output

    def test_compare_too_few_ids(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(
            app, ["compare", "abc-123", "--db", str(db_path)],
        )
        assert result.exit_code != 0


class TestEvalsCommand:
    def test_evals_basic(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        _seed_evals(
            db_path,
            "abc-123",
            [
                {
                    "id": "eval-001",
                    "dataset_id": "ds-01",
                    "inputs": {"query": "what is ML?"},
                    "scores": {"f1": 0.91, "em": 0.85},
                },
                {
                    "id": "eval-002",
                    "dataset_id": "ds-01",
                    "inputs": {"query": "how does backprop work?"},
                    "scores": {"f1": 0.78, "em": 0.70},
                },
            ],
        )
        result = runner.invoke(
            app, ["evals", "abc-123", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert "ds-01" in result.output
        assert "eval-001" in result.output
        assert "eval-002" in result.output
        assert "f1=0.91" in result.output
        assert "em=0.85" in result.output
        assert "(2 of 2 samples)" in result.output

    def test_evals_default_cap_10(self, tmp_path: Path) -> None:
        db_path = tmp_path / "experiments"
        db_path.mkdir()
        _create_meta_db(db_path)
        _seed_experiment(db_path, "big", "big-eval")
        evals_data = [
            {
                "id": f"eval-{i:03d}",
                "dataset_id": "ds-01",
                "inputs": {"q": f"question {i}"},
                "scores": {"f1": 0.5 + i * 0.01},
            }
            for i in range(25)
        ]
        _seed_evals(db_path, "big", evals_data)
        result = runner.invoke(
            app, ["evals", "big", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert "(10 of 25 samples, use --all for full list)" in result.output

    def test_evals_all_flag(self, tmp_path: Path) -> None:
        db_path = tmp_path / "experiments"
        db_path.mkdir()
        _create_meta_db(db_path)
        _seed_experiment(db_path, "big", "big-eval")
        evals_data = [
            {
                "id": f"eval-{i:03d}",
                "dataset_id": "ds-01",
                "inputs": {"q": f"question {i}"},
                "scores": {"f1": 0.5},
            }
            for i in range(25)
        ]
        _seed_evals(db_path, "big", evals_data)
        result = runner.invoke(
            app, ["evals", "big", "--db", str(db_path), "--all"],
        )
        assert result.exit_code == 0
        assert "(25 of 25 samples)" in result.output

    def test_evals_limit_flag(self, tmp_path: Path) -> None:
        db_path = tmp_path / "experiments"
        db_path.mkdir()
        _create_meta_db(db_path)
        _seed_experiment(db_path, "big", "big-eval")
        evals_data = [
            {
                "id": f"eval-{i:03d}",
                "dataset_id": "ds-01",
                "inputs": {"q": f"question {i}"},
                "scores": {"f1": 0.5},
            }
            for i in range(25)
        ]
        _seed_evals(db_path, "big", evals_data)
        result = runner.invoke(
            app, ["evals", "big", "--db", str(db_path), "--limit", "5"],
        )
        assert result.exit_code == 0
        assert "(5 of 25 samples, use --all for full list)" in result.output

    def test_evals_dataset_filter(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        _seed_evals(
            db_path,
            "abc-123",
            [
                {
                    "id": "eval-001",
                    "dataset_id": "ds-01",
                    "inputs": {"q": "a"},
                    "scores": {"f1": 0.9},
                },
                {
                    "id": "eval-002",
                    "dataset_id": "ds-02",
                    "inputs": {"q": "b"},
                    "scores": {"f1": 0.8},
                },
            ],
        )
        result = runner.invoke(
            app,
            ["evals", "abc-123", "--db", str(db_path), "--dataset", "ds-01"],
        )
        assert result.exit_code == 0
        assert "ds-01" in result.output
        assert "ds-02" not in result.output

    def test_evals_truncation(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        long_input = {"query": "x" * 100}
        _seed_evals(
            db_path,
            "abc-123",
            [
                {
                    "id": "eval-001",
                    "dataset_id": "ds-01",
                    "inputs": long_input,
                    "scores": {"f1": 0.9},
                },
            ],
        )
        result = runner.invoke(
            app, ["evals", "abc-123", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert "..." in result.output

    def test_evals_no_samples(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        result = runner.invoke(
            app, ["evals", "abc-123", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert "No eval samples found" in result.output

    def test_evals_header_present(self, tmp_path: Path) -> None:
        db_path = _seed_db(tmp_path)
        _seed_evals(
            db_path,
            "abc-123",
            [
                {
                    "id": "eval-001",
                    "dataset_id": "ds-01",
                    "inputs": {"q": "test"},
                    "scores": {"f1": 0.9},
                },
            ],
        )
        result = runner.invoke(
            app, ["evals", "abc-123", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        first_line = result.output.strip().split("\n")[0]
        assert "DATASET" in first_line
        assert "EVAL_ID" in first_line
        assert "SCORES" in first_line
        assert "INPUTS(trunc)" in first_line
