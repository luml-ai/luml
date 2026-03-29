from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from luml_agent.cli.inspect import app

runner = CliRunner()


def _create_meta_db(db_path: Path) -> None:
    meta = db_path / "meta.db"
    conn = sqlite3.connect(str(meta))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE experiment_groups (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE experiments (
            id TEXT PRIMARY KEY,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active',
            group_id TEXT,
            tags TEXT,
            static_params TEXT,
            dynamic_params TEXT
        )
        """
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
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
