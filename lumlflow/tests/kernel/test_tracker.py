from __future__ import annotations

import builtins
import json
import os
import sqlite3
import subprocess
import sys
import textwrap
import threading
import time
from base64 import b64decode
from collections.abc import Callable
from importlib.metadata import version as distribution_version
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from luml.experiments.tracker import ExperimentTracker
else:
    ExperimentTracker = pytest.importorskip(
        "luml.experiments.tracker"
    ).ExperimentTracker

from lumlflow_kernel.kernel import Kernel
from lumlflow_kernel.tracker import ExperimentRef, Tracker
from tests.kernel.helpers import FakeLink, make_kernel, run, stored_log, stored_value

DEADLINE_S = 20.0
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SDK_VERSION = distribution_version("luml-sdk")
EVALUATE_CELL = (
    PROJECT_ROOT / "examples" / "churn" / "churn.flow" / "cells" / "evaluate.py"
)


def test_an_experiment_run_writes_metadata_params_metrics_and_completes(
    tmp_path: Path, tracker_store: Path
) -> None:
    kernel, link = make_kernel(tmp_path)
    identity = _identity(kernel, run_id="evaluate-run")

    record = run(
        kernel,
        """
        def materialize(self, ctx):
            if ctx.tracker.record.snapshot["params"] != {"folds": 5}:
                raise RuntimeError("declared params were not seeded")
            ctx.tracker.log_params({"alpha": 0.25, "optimizer": "adamw"})
            ctx.tracker.log_metrics({"rmse": 0.4, "mae": 0.3}, step=7)
            return {"metrics": ctx.tracker.record}
        """,
        slug="evaluate",
        run_id="evaluate-run",
        produces={"metrics": "experiment"},
        params={"folds": 5},
        identity=identity,
    )

    tracker = ExperimentTracker(f"sqlite://{tracker_store}")
    experiment = _only_experiment(tracker)
    data = tracker.get_experiment(experiment.id)
    assert data is not None
    assert (experiment.name, experiment.group_name, experiment.status) == (
        "evaluate",
        "churn",
        "completed",
    )
    assert experiment.tags == ["main", "evaluate"]
    assert experiment.metadata == {"lumlflow": identity}
    assert data.static_params == {
        "folds": 5,
        "alpha": 0.25,
        "optimizer": "adamw",
    }
    assert data.dynamic_metrics == {
        "rmse": [{"value": 0.4, "step": 7}],
        "mae": [{"value": 0.3, "step": 7}],
    }
    assert json.loads(stored_value(kernel, record, "metrics")) == {
        "experiment_id": experiment.id,
        "group": "churn",
        "store": str(tracker_store),
        "snapshot": {
            "params": {"folds": 5, "alpha": 0.25, "optimizer": "adamw"},
            "metrics": {"rmse": 0.4, "mae": 0.3},
        },
    }
    started = link.named("experiment_started")
    assert started == [
        {
            "run_id": "evaluate-run",
            "slug": "evaluate",
            "experiment_id": experiment.id,
            "store": str(tracker_store),
        }
    ]
    assert record["experiment_id"] == experiment.id
    assert record["store"] == str(tracker_store)
    assert link.named("materialized")[-1]["experiment_id"] == experiment.id


def test_identical_numbers_prune_consumers_by_hashing_the_snapshot(
    tmp_path: Path, tracker_store: Path
) -> None:
    kernel, _ = make_kernel(tmp_path)
    body = """
        def materialize(self, ctx):
            ctx.tracker.log_param("alpha", 0.25)
            ctx.tracker.log_metric("rmse", 0.4)
            return {"metrics": ctx.tracker.record}
    """

    first = run(
        kernel,
        body,
        run_id="first",
        produces={"metrics": "experiment"},
        identity=_identity(kernel, run_id="first"),
    )
    second = run(
        kernel,
        body,
        run_id="second",
        produces={"metrics": "experiment"},
        identity=_identity(kernel, run_id="second"),
    )

    first_output = first["outputs"]["metrics"]
    second_output = second["outputs"]["metrics"]
    assert first_output["value_ref"] != second_output["value_ref"]
    assert first_output["content_hash"] == second_output["content_hash"]
    tracker = ExperimentTracker(f"sqlite://{tracker_store}")
    assert len(tracker.list_experiments()) == 2


def test_a_wrong_experiment_value_names_the_tracker_record(
    tmp_path: Path, tracker_store: Path
) -> None:
    kernel, _ = make_kernel(tmp_path)
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            return {"metrics": {"params": {}, "metrics": {"a": 1}}}
        """,
        produces={"metrics": "experiment"},
        identity=_identity(kernel),
    )

    assert record["state"] == "failed"
    assert "ctx.tracker.record" in record["error"]["message"]
    experiment = _only_experiment(ExperimentTracker(f"sqlite://{tracker_store}"))
    assert experiment.status == "error"


def test_ctx_tracker_without_an_experiment_output_fails_in_words(
    tmp_path: Path,
) -> None:
    kernel, _ = make_kernel(tmp_path)
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            ctx.tracker.log_metric("auc", 0.91)
            return {"result": "unreachable"}
        """,
        produces={"result": "asset"},
    )

    assert record["state"] == "failed"
    assert "declare an `experiment` output" in record["error"]["message"]


def test_a_consumer_reads_the_live_experiment_without_observation_marks(
    tmp_path: Path, tracker_store: Path
) -> None:
    kernel, _ = make_kernel(tmp_path)
    produced = run(
        kernel,
        """
        def materialize(self, ctx):
            ctx.tracker.log_param("optimizer", "adamw")
            ctx.tracker.log_metric("rmse", 0.8, step=1)
            ctx.tracker.log_metric("rmse", 0.4, step=2)
            return {"metrics": ctx.tracker.record}
        """,
        slug="evaluate",
        run_id="evaluate-run",
        produces={"metrics": "experiment"},
        params={"folds": 5},
        identity=_identity(kernel, run_id="evaluate-run"),
    )
    consumed = run(
        kernel,
        """
        def materialize(self, ctx, metrics):
            params = metrics.params
            params["local-only"] = True
            return {
                "seen": {
                    "id": metrics.id,
                    "params": metrics.params,
                    "metrics": metrics.metrics,
                    "history": [
                        (point["step"], point["value"])
                        for point in metrics.metric_history("rmse")
                    ],
                    "has_writer": hasattr(metrics, "log_metric"),
                }
            }
        """,
        slug="report",
        run_id="report-run",
        produces={"seen": "asset"},
        inputs={"metrics": _input(produced, "metrics")},
    )

    experiment = _only_experiment(ExperimentTracker(f"sqlite://{tracker_store}"))
    seen_spec = consumed["outputs"]["seen"]
    seen = kernel.executor.fresh(seen_spec["value_ref"], seen_spec["kind"])
    assert consumed["state"] == "succeeded"
    assert consumed["identity_dependent"] is False
    assert consumed["external"] is False
    assert seen == {
        "id": experiment.id,
        "params": {"folds": 5, "optimizer": "adamw"},
        "metrics": {"rmse": 0.4},
        "history": [(1, 0.8), (2, 0.4)],
        "has_writer": False,
    }


def test_a_consumer_without_the_sdk_fails_before_its_code_runs(
    tmp_path: Path,
    tracker_store: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    producer, _ = make_kernel(tmp_path)
    produced = run(
        producer,
        """
        def materialize(self, ctx):
            return {"metrics": ctx.tracker.record}
        """,
        produces={"metrics": "experiment"},
        identity=_identity(producer),
    )
    tracker = ExperimentTracker(f"sqlite://{tracker_store}")
    experiment_id = _only_experiment(tracker).id
    consumer, _ = make_kernel(tmp_path)
    marker = tmp_path / "consumer-ran"
    real_import = builtins.__import__

    def import_without_sdk(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if name == "luml" or name.startswith("luml."):
            raise ModuleNotFoundError("No module named 'luml'", name="luml")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_without_sdk)
    record = run(
        consumer,
        f"""
        def materialize(self, ctx, metrics):
            from pathlib import Path
            Path({str(marker)!r}).write_text("ran")
            return {{"seen": metrics.id}}
        """,
        slug="report",
        produces={"seen": "asset"},
        inputs={"metrics": _input(produced, "metrics")},
    )

    assert record["state"] == "failed"
    assert "luml-sdk" in record["error"]["message"]
    assert record["outputs"] == {}
    assert [experiment.id for experiment in tracker.list_experiments()] == [
        experiment_id
    ]
    assert not marker.exists()


def test_accessing_a_removed_experiment_fails_in_words(
    tmp_path: Path, tracker_store: Path
) -> None:
    kernel, _ = make_kernel(tmp_path)
    produced = run(
        kernel,
        """
        def materialize(self, ctx):
            ctx.tracker.log_metric("rmse", 0.4)
            return {"metrics": ctx.tracker.record}
        """,
        produces={"metrics": "experiment"},
        identity=_identity(kernel),
    )
    tracker = ExperimentTracker(f"sqlite://{tracker_store}")
    experiment = _only_experiment(tracker)
    tracker.delete_experiment(experiment.id)
    marker = tmp_path / "consumer-reached-access"

    record = run(
        kernel,
        f"""
        def materialize(self, ctx, metrics):
            from pathlib import Path
            Path({str(marker)!r}).write_text("accessing")
            return {{"seen": metrics.metrics}}
        """,
        slug="report",
        produces={"seen": "asset"},
        inputs={"metrics": _input(produced, "metrics")},
    )

    message = record["error"]["message"]
    assert record["state"] == "failed"
    assert "missing" in message
    assert experiment.id in message
    assert str(tracker_store) in message
    assert marker.exists()


def test_an_unreachable_experiment_fails_at_access(
    tmp_path: Path,
    tracker_store: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from luml.experiments import tracker as sdk_tracker

    kernel, _ = make_kernel(tmp_path)
    produced = run(
        kernel,
        """
        def materialize(self, ctx):
            return {"metrics": ctx.tracker.record}
        """,
        produces={"metrics": "experiment"},
        identity=_identity(kernel),
    )

    def refuse_read(client: Any, experiment_id: str) -> None:
        raise RuntimeError("tracker schema is not readable")

    monkeypatch.setattr(
        sdk_tracker.ExperimentTracker, "get_experiment_record", refuse_read
    )
    record = run(
        kernel,
        """
        def materialize(self, ctx, metrics):
            return {"seen": metrics.params}
        """,
        slug="report",
        produces={"seen": "asset"},
        inputs={"metrics": _input(produced, "metrics")},
    )

    message = record["error"]["message"]
    assert record["state"] == "failed"
    assert "unreachable" in message
    assert "tracker schema is not readable" in message
    assert str(tracker_store) in message


def test_the_experiment_start_is_reported_before_materialize(
    tmp_path: Path, tracker_store: Path
) -> None:
    announced = tmp_path / "announced"
    link = _StartMarkingLink(announced)
    kernel, _ = make_kernel(tmp_path, link=link)

    record = run(
        kernel,
        f"""
        def materialize(self, ctx):
            from pathlib import Path
            if not Path({str(announced)!r}).exists():
                raise RuntimeError("materialize ran before the start event")
            return {{"metrics": ctx.tracker.record}}
        """,
        slug="evaluate",
        produces={"metrics": "experiment"},
        identity=_identity(kernel),
    )

    event = link.named("experiment_started")[0]
    assert record["state"] == "succeeded"
    assert event["experiment_id"] == record["experiment_id"]
    assert event["store"] == str(tracker_store)


def test_a_failed_run_fails_the_experiment_and_keeps_its_id(
    tmp_path: Path, tracker_store: Path
) -> None:
    kernel, link = make_kernel(tmp_path)
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            ctx.tracker.log_metric("loss", 0.8, step=2)
            raise ValueError("did not converge")
        """,
        slug="train",
        produces={"run": "experiment"},
        identity=_identity(kernel, slug="train"),
    )

    tracker = ExperimentTracker(f"sqlite://{tracker_store}")
    experiment = _only_experiment(tracker)
    assert record["state"] == "failed"
    assert experiment.status == "error"
    assert (
        tracker.get_experiment_metric_history(experiment.id, "loss")[0]["value"] == 0.8
    )
    assert record["experiment_id"] == experiment.id
    assert link.named("failed")[-1]["experiment_id"] == experiment.id


def test_cancelling_a_run_fails_its_live_experiment(
    tmp_path: Path, tracker_store: Path
) -> None:
    kernel, _ = make_kernel(tmp_path)
    logged = tmp_path / "logged"
    finished: list[dict[str, Any]] = []
    worker = threading.Thread(
        target=lambda: finished.append(
            run(
                kernel,
                f"""
                def materialize(self, ctx):
                    from pathlib import Path
                    import time
                    ctx.tracker.log_metric("loss", 0.9, step=1)
                    Path({str(logged)!r}).write_text("ready")
                    while True:
                        time.sleep(0.01)
                """,
                slug="train",
                produces={"run": "experiment"},
                identity=_identity(kernel, slug="train"),
            )
        )
    )
    worker.start()
    try:
        _await(logged.exists)
        assert kernel.cancel({"run_id": "run1"}) == {"cancelled": True}
    finally:
        worker.join(timeout=DEADLINE_S)

    tracker = ExperimentTracker(f"sqlite://{tracker_store}")
    experiment = _only_experiment(tracker)
    assert not worker.is_alive()
    assert finished[0]["state"] == "cancelled"
    assert finished[0]["experiment_id"] == experiment.id
    assert experiment.status == "error"
    assert tracker.get_experiment_metric_history(experiment.id, "loss")[0]["step"] == 1


def test_metrics_are_in_the_tracker_in_order_while_the_cell_is_running(
    tmp_path: Path, tracker_store: Path
) -> None:
    kernel, link = make_kernel(tmp_path)
    logged, release = tmp_path / "logged", tmp_path / "release"
    finished: list[dict[str, Any]] = []
    worker = threading.Thread(
        target=lambda: finished.append(
            run(
                kernel,
                f"""
                def materialize(self, ctx):
                    from pathlib import Path
                    import time
                    ctx.tracker.log_metric("loss", 0.9, step=1)
                    ctx.tracker.log_metrics({{"loss": 0.7}}, step=2)
                    ctx.tracker.log_metric("loss", 0.5, step=3)
                    Path({str(logged)!r}).write_text("ready")
                    while not Path({str(release)!r}).exists():
                        time.sleep(0.01)
                    return {{"run": ctx.tracker.record}}
                """,
                slug="train",
                produces={"run": "experiment"},
                identity=_identity(kernel, slug="train"),
            )
        )
    )
    worker.start()
    try:
        _await(logged.exists)
        experiment_id = link.named("experiment_started")[0]["experiment_id"]
        tracker = ExperimentTracker(f"sqlite://{tracker_store}")
        history = tracker.get_experiment_metric_history(experiment_id, "loss")
        assert [(point["step"], point["value"]) for point in history] == [
            (1, 0.9),
            (2, 0.7),
            (3, 0.5),
        ]
        assert tracker.get_experiment_record(experiment_id).status == "active"
    finally:
        release.write_text("go")
        worker.join(timeout=DEADLINE_S)

    assert not worker.is_alive()
    assert finished[0]["state"] == "succeeded"
    restored = kernel.executor.fresh(
        finished[0]["outputs"]["run"]["value_ref"], "experiment"
    )
    assert restored.snapshot["metrics"] == {"loss": 0.5}


def test_a_close_failure_keeps_the_materialization_and_reaches_the_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kernel, link = make_kernel(tmp_path)
    complete = Tracker.complete

    def complete_then_report_failure(tracker: Tracker) -> None:
        complete(tracker)
        raise RuntimeError("could not close the experiment")

    monkeypatch.setattr(Tracker, "complete", complete_then_report_failure)
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            return {"run": ctx.tracker.record}
        """,
        produces={"run": "experiment"},
        identity=_identity(kernel),
    )

    assert record["state"] == "succeeded"
    assert record["outputs"]["run"]["value_ref"]
    assert record["experiment_close_error"] == "could not close the experiment"
    assert link.named("materialized")[-1]["experiment_close_error"] == (
        "could not close the experiment"
    )


def test_a_run_without_an_experiment_never_imports_the_sdk(tmp_path: Path) -> None:
    probe = textwrap.dedent(
        f"""
        import sys
        from pathlib import Path
        from lumlflow_kernel.kernel import Kernel

        class Link:
            def notify(self, method, params):
                pass
            def stop(self):
                pass

        root = Path({str(tmp_path)!r}) / "project"
        flow = root / "churn.flow"
        (flow / "cells").mkdir(parents=True)
        kernel = Kernel(flow_dir=flow, workspace_dir=root, link=Link())
        source = (
            "class Plain:\\n"
            "    def materialize(self, ctx):\\n"
            "        return {{}}\\n"
        )
        kernel.run({{
            "run_id": "plain",
            "version": {{
                "slug": "plain",
                "source": source,
                "produces": {{}},
            }},
            "inputs": {{}},
            "params": {{}},
            "ctx_info": {{"branch": "main", "step": 1}},
        }})
        print(sorted(name for name in sys.modules if name.split('.')[0] == "luml"))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=PROJECT_ROOT,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        capture_output=True,
        check=True,
        text=True,
    )

    assert result.stdout.strip() == "[]"


def test_a_missing_sdk_fails_before_the_cell_runs(
    tmp_path: Path, tracker_store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "cell-ran"
    kernel, link = make_kernel(tmp_path)
    real_import = builtins.__import__

    def import_without_sdk(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if name == "luml" or name.startswith("luml."):
            raise ModuleNotFoundError("No module named 'luml'", name="luml")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_without_sdk)
    record = run(
        kernel,
        f"""
        def materialize(self, ctx):
            from pathlib import Path
            Path({str(marker)!r}).write_text("ran")
            return {{"run": ctx.tracker.record}}
        """,
        produces={"run": "experiment"},
        identity=_identity(kernel),
    )

    assert record["state"] == "failed"
    assert "luml-sdk" in record["error"]["message"]
    assert record["outputs"] == {}
    assert link.named("experiment_started") == []
    assert not tracker_store.exists()
    assert not marker.exists()


def test_an_unwritable_tracker_store_is_named_before_the_cell_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "not-a-directory"
    store.write_text("blocked", encoding="utf-8")
    monkeypatch.setenv("BACKEND_STORE_URI", str(store))
    monkeypatch.setenv("LUML_BACKEND_STORE_URI", str(store))
    marker = tmp_path / "cell-ran"
    kernel, link = make_kernel(tmp_path)

    record = run(
        kernel,
        f"""
        def materialize(self, ctx):
            from pathlib import Path
            Path({str(marker)!r}).write_text("ran")
            return {{"run": ctx.tracker.record}}
        """,
        produces={"run": "experiment"},
        identity=_identity(kernel),
    )

    assert record["state"] == "failed"
    assert str(store) in record["error"]["message"]
    assert SDK_VERSION in record["error"]["message"]
    assert record["outputs"] == {}
    assert link.named("experiment_started") == []
    assert not marker.exists()


def test_an_sdk_store_refusal_keeps_its_sentence_path_and_version(
    tmp_path: Path, tracker_store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from luml.experiments import tracker as sdk_tracker

    def refuse_store(connection_string: str) -> None:
        raise RuntimeError("store schema 41 is newer than this SDK supports")

    monkeypatch.setattr(sdk_tracker, "ExperimentTracker", refuse_store)
    kernel, _ = make_kernel(tmp_path)
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            raise RuntimeError("cell should not run")
        """,
        produces={"run": "experiment"},
        identity=_identity(kernel),
    )

    message = record["error"]["message"]
    assert record["state"] == "failed"
    assert "store schema 41 is newer than this SDK supports" in message
    assert str(tracker_store) in message
    assert SDK_VERSION in message


def test_an_sdk_write_refusal_keeps_its_sentence_path_and_version(
    tmp_path: Path, tracker_store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from luml.experiments import tracker as sdk_tracker

    def refuse_write(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("this SDK refuses the metric write")

    monkeypatch.setattr(sdk_tracker.ExperimentTracker, "log_dynamic", refuse_write)
    marker = tmp_path / "cell-continued"
    kernel, _ = make_kernel(tmp_path)
    record = run(
        kernel,
        f"""
        def materialize(self, ctx):
            from pathlib import Path
            ctx.tracker.log_metric("auc", 0.91)
            Path({str(marker)!r}).write_text("continued")
            return {{"run": ctx.tracker.record}}
        """,
        produces={"run": "experiment"},
        identity=_identity(kernel),
    )

    message = record["error"]["message"]
    experiment = _only_experiment(ExperimentTracker(f"sqlite://{tracker_store}"))
    assert record["state"] == "failed"
    assert "this SDK refuses the metric write" in message
    assert str(tracker_store) in message
    assert SDK_VERSION in message
    assert experiment.status == "error"
    assert not marker.exists()


@pytest.mark.parametrize("release_after_timeout", [True, False])
def test_a_locked_tracker_store_is_retried_then_named(
    tmp_path: Path,
    tracker_store: Path,
    monkeypatch: pytest.MonkeyPatch,
    release_after_timeout: bool,
) -> None:
    from luml.experiments import tracker as sdk_tracker
    from luml.experiments.backends import sqlite as sdk_sqlite

    seed = ExperimentTracker(f"sqlite://{tracker_store}")
    seed.backend.pool.close_all()
    lock = sqlite3.connect(tracker_store / "meta.db")
    lock.execute("BEGIN IMMEDIATE")
    real_connection = sqlite3.Connection
    second_attempt = threading.Event()
    retry_allowed = threading.Event()
    starts = 0
    real_start = sdk_tracker.ExperimentTracker.start_experiment

    def short_wait_connection(database: str, **kwargs: Any) -> sqlite3.Connection:
        return real_connection(database, timeout=0.05, **kwargs)

    def counted_start(client: Any, **kwargs: Any) -> str:
        nonlocal starts
        starts += 1
        if starts == 2:
            second_attempt.set()
            assert retry_allowed.wait(DEADLINE_S)
        return str(real_start(client, **kwargs))

    monkeypatch.setattr(sdk_sqlite.sqlite3, "Connection", short_wait_connection)
    monkeypatch.setattr(
        sdk_tracker.ExperimentTracker, "start_experiment", counted_start
    )
    marker = tmp_path / "cell-ran"
    kernel, _ = make_kernel(tmp_path)
    finished: list[dict[str, Any]] = []
    worker = threading.Thread(
        target=lambda: finished.append(
            run(
                kernel,
                f"""
                def materialize(self, ctx):
                    from pathlib import Path
                    Path({str(marker)!r}).write_text("ran")
                    return {{"run": ctx.tracker.record}}
                """,
                produces={"run": "experiment"},
                identity=_identity(kernel),
            )
        )
    )
    worker.start()
    try:
        assert second_attempt.wait(DEADLINE_S)
        if release_after_timeout:
            lock.commit()
        retry_allowed.set()
        worker.join(timeout=DEADLINE_S)
    finally:
        retry_allowed.set()
        if lock.in_transaction:
            lock.rollback()
        lock.close()
        worker.join(timeout=DEADLINE_S)

    assert not worker.is_alive()
    assert starts == 2
    experiments = ExperimentTracker(f"sqlite://{tracker_store}").list_experiments()
    if release_after_timeout:
        assert finished[0]["state"] == "succeeded", (
            finished[0].get("error"),
            finished[0].get("experiment_id"),
            finished[0].get("experiment_close_error"),
        )
        assert marker.exists()
        assert len(experiments) == 1
        assert experiments[0].status == "completed"
    else:
        assert finished[0]["state"] == "failed"
        assert str(tracker_store) in finished[0]["error"]["message"]
        assert not marker.exists()
        assert experiments == []


@pytest.mark.parametrize(
    "daemon_version,mismatch", [("999.0.0", True), (SDK_VERSION, False)]
)
def test_sdk_version_skew_warns_once_and_proceeds(
    tmp_path: Path,
    tracker_store: Path,
    monkeypatch: pytest.MonkeyPatch,
    daemon_version: str,
    mismatch: bool,
) -> None:
    monkeypatch.setenv("LUMLFLOW_DAEMON_SDK_VERSION", daemon_version)
    kernel, link = make_kernel(tmp_path)
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            ctx.tracker.log_metric("auc", 0.91)
            return {"run": ctx.tracker.record}
        """,
        produces={"run": "experiment"},
        identity=_identity(kernel),
    )

    live_console = b"".join(
        b64decode(event["bytes"])
        for event in link.named("log")
        if event["stream"] == "stderr"
    ).decode("utf-8")
    log = stored_log(kernel, record).decode("utf-8")
    experiment = _only_experiment(ExperimentTracker(f"sqlite://{tracker_store}"))
    assert record["state"] == "succeeded"
    assert experiment.status == "completed"
    if mismatch:
        warning = record["sdk_version_warning"]
        assert SDK_VERSION in warning
        assert daemon_version in warning
        assert str(Path(sys.executable).absolute()) in warning
        assert live_console.count(warning) == 1
        assert log.count(warning) == 1
        assert link.named("experiment_started")[0]["sdk_version_warning"] == warning
        assert link.named("materialized")[-1]["sdk_version_warning"] == warning
    else:
        assert "sdk_version_warning" not in record
        assert "luml-sdk version mismatch" not in live_console
        assert "luml-sdk version mismatch" not in log


def test_the_churn_evaluate_cell_runs_unchanged_and_logs_alpha(
    tmp_path: Path, tracker_store: Path
) -> None:
    pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    pytest.importorskip("sklearn")
    kernel, _ = make_kernel(tmp_path)
    fixture = run(
        kernel,
        """
        def materialize(self, ctx):
            import pandas

            class Model:
                alpha = 0.25

                def predict(self, rows):
                    return rows["feature"].to_numpy() * 2

            test = pandas.DataFrame({
                "feature": [1.0, 2.0, 3.0],
                "target": [2.0, 4.0, 6.0],
            })
            return {"model": Model(), "test": test}
        """,
        run_id="fixture",
        produces={"model": "asset", "test": "asset"},
    )
    model = fixture["outputs"]["model"]
    test = fixture["outputs"]["test"]

    record = kernel.run(
        {
            "run_id": "evaluate-run",
            "version": {
                "slug": "evaluate",
                "source": EVALUATE_CELL.read_text("utf-8"),
                "produces": {"metrics": "experiment"},
            },
            "inputs": {
                "model": {"value_ref": model["value_ref"], "kind": model["kind"]},
                "test": {"value_ref": test["value_ref"], "kind": test["kind"]},
            },
            "params": {},
            "ctx_info": {"branch": "main", "step": 7},
            "identity": _identity(kernel, slug="evaluate", run_id="evaluate-run"),
        }
    )

    tracker = ExperimentTracker(f"sqlite://{tracker_store}")
    experiment = _only_experiment(tracker)
    assert record["state"] == "succeeded"
    assert experiment.static_params["alpha"] == 0.25
    assert set(experiment.dynamic_params) == {"rmse", "mae", "r2"}
    restored = kernel.executor.fresh(
        record["outputs"]["metrics"]["value_ref"], "experiment"
    )
    assert isinstance(restored, ExperimentRef)
    assert restored.experiment_id == experiment.id
    assert restored.snapshot["metrics"] == experiment.dynamic_params


class _StartMarkingLink(FakeLink):
    def __init__(self, marker: Path) -> None:
        super().__init__()
        self._marker = marker

    def notify(self, method: str, params: dict[str, Any]) -> None:
        super().notify(method, params)
        if method == "experiment_started":
            self._marker.write_text("ready")


def _identity(
    kernel: Kernel, *, slug: str = "evaluate", run_id: str = "run1"
) -> dict[str, str]:
    return {
        "flow": "churn",
        "flow_id": "01M00FLOW00000000000000000",
        "path": str(kernel.flow_dir.resolve()),
        "slug": slug,
        "uid": "01M00CELL00000000000000000",
        "lane": "main",
        "version_id": "01M00VERSION0000000000000",
        "run_id": run_id,
    }


def _only_experiment(tracker: ExperimentTracker) -> Any:
    experiments = tracker.list_experiments()
    assert len(experiments) == 1
    experiment = tracker.get_experiment_record(experiments[0].id)
    assert experiment is not None
    return experiment


def _input(record: dict[str, Any], output: str) -> dict[str, Any]:
    stored = record["outputs"][output]
    return {"value_ref": stored["value_ref"], "kind": stored["kind"]}


def _await(condition: Callable[[], bool]) -> None:
    deadline = time.monotonic() + DEADLINE_S
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("the run never reached the expected point")
