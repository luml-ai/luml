# flake8: noqa: E501
"""Runs a released luml-sdk against stores of this one, and the other way round.

Needs a Python with a released luml-sdk installed, so it is skipped by default:

    uv venv /tmp/old-sdk && VIRTUAL_ENV=/tmp/old-sdk uv pip install luml-sdk==0.5.0
    LUML_OLD_SDK_PYTHON=/tmp/old-sdk/bin/python uv run --frozen pytest \\
        tests/experiments/test_metric_cross_version.py
"""

import io
import json
import os
import shutil
import sqlite3
import subprocess
import tarfile
import time
import zipfile
from pathlib import Path
from typing import Any

import pytest

from luml.experiments.backends.migration_runner import ExperimentMigrationRunner
from luml.experiments.backends.sqlite import SQLiteBackend
from luml.experiments.tracker import ExperimentTracker
from tests.experiments.metric_helpers import assert_bucket_invariants, schema_snapshot

OLD_PYTHON = os.environ.get("LUML_OLD_SDK_PYTHON")
pytestmark = pytest.mark.skipif(
    not OLD_PYTHON, reason="set LUML_OLD_SDK_PYTHON to a Python with a released SDK"
)
EXP_ID = "exp"

OLD_READ_AND_WRITE = """
import json, sys
from luml.experiments.backends.migration_runner import ExperimentMigrationRunner
from luml.experiments.backends.sqlite import SQLiteBackend
backend = SQLiteBackend(sys.argv[1])
result = {
    "history": [
        [p["value"], p["step"], str(p["logged_at"])]
        for p in backend.get_experiment_metric_history("exp", "loss")
    ],
    "data": backend.get_experiment_data("exp").dynamic_metrics,
    "keys": backend.get_group_experiments_dynamic_metrics_keys(
        backend.get_experiment("exp").group_id
    ),
}
try:
    backend.log_dynamic("exp", "loss", 9.0)
    result["write"] = "accepted"
except Exception as error:
    result["write"] = f"{type(error).__name__}: {error}"
backend.end_experiment("exp")
result["latest"] = backend.get_experiment("exp").dynamic_params
print(json.dumps(result))
"""

OLD_WRITER = """
import sys, time
from luml.experiments.backends.migration_runner import ExperimentMigrationRunner
from luml.experiments.backends.sqlite import SQLiteBackend
backend = SQLiteBackend(sys.argv[1])
backend.initialize_experiment("exp", "default", "old")
print("ready", flush=True)
for step in range(int(sys.argv[2])):
    backend.log_dynamic("exp", "loss", step * 0.5)
    backend.log_dynamic("exp", "acc", step * 0.25, step=step)
    time.sleep(0.001)
print("done", flush=True)
"""


def _old_sdk(script: str, *args: str) -> subprocess.Popen[str]:
    assert OLD_PYTHON is not None
    return subprocess.Popen(
        [OLD_PYTHON, "-I", "-c", script, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def test_released_sdk_reads_revision_3_and_its_writes_fail_cleanly(
    tmp_path: Path,
) -> None:
    store = tmp_path / "store"
    backend = SQLiteBackend(str(store), flush_interval=0)
    backend.initialize_experiment(EXP_ID, name="new")
    for step in range(50):
        backend.log_dynamic(EXP_ID, "loss", step * 0.5)
        backend.log_dynamic(EXP_ID, "acc", float(step), step=step * 2)
    backend.log_dynamic(EXP_ID, "loss", float("inf"))
    expected_history = backend.get_experiment_metric_history(EXP_ID, "loss")
    expected_data = backend.get_experiment_data(EXP_ID).dynamic_metrics
    backend.close()
    db_path = store / EXP_ID / "exp.db"
    schema_before = schema_snapshot(db_path)

    old = _old_sdk(OLD_READ_AND_WRITE, str(store))
    stdout, stderr = old.communicate(timeout=120)
    assert old.returncode == 0, stderr
    result: dict[str, Any] = json.loads(stdout.strip().splitlines()[-1])

    # str() of the datetime both SDKs parse from the TIMESTAMP column.
    assert result["history"] == [
        [p["value"], p["step"], str(p["logged_at"])] for p in expected_history
    ]
    assert result["data"] == json.loads(json.dumps(expected_data))
    assert result["keys"] == ["acc", "loss"]
    assert result["write"].startswith("IntegrityError")
    assert "schema revision 3; upgrade luml-sdk" in result["write"]
    assert result["latest"] == {"loss": float("inf"), "acc": 49.0}
    assert schema_snapshot(db_path) == schema_before
    conn = sqlite3.connect(db_path)
    assert_bucket_invariants(conn)
    conn.close()


def test_reading_a_store_a_released_sdk_is_writing(tmp_path: Path) -> None:
    store = tmp_path / "store"
    steps = 1500
    old = _old_sdk(OLD_WRITER, str(store), str(steps))
    assert old.stdout is not None
    assert old.stdout.readline().strip() == "ready"
    db_path = store / EXP_ID / "exp.db"

    reader = SQLiteBackend(str(store))
    reads = 0
    while old.poll() is None:
        history = reader.get_experiment_metric_history(EXP_ID, "loss")
        assert [p["step"] for p in history] == list(range(len(history)))
        reader.get_metric_catalog(EXP_ID)
        reader.get_metric_buckets(EXP_ID, "acc", 3)
        reader.get_experiment_data(EXP_ID)
        reads += 1
        time.sleep(0.01)
    _, stderr = old.communicate(timeout=120)
    assert old.returncode == 0, stderr
    assert reads > 5

    assert schema_snapshot(db_path)[1] == 2
    catalog = reader.get_metric_catalog(EXP_ID)
    assert catalog.revision == 2
    assert [(m.key, m.count, m.last_step) for m in catalog.metrics] == [
        ("acc", None, steps - 1),
        ("loss", None, steps - 1),
    ]
    buckets = reader.get_metric_buckets(EXP_ID, "loss", 4)
    assert sum(b.count for b in buckets.buckets) == steps
    reader.close()


OLD_POPULATE = """
import json, os, sys
from luml.experiments.backends.data_types import AnnotationKind, AnnotationValueType
from luml.experiments.backends.sqlite import SQLiteBackend
store = sys.argv[1]
b = SQLiteBackend(store)
b.initialize_experiment("exp", "g1", "old", tags=["t"])
b.log_static("exp", "lr", 0.1)
for s in range(200):
    b.log_dynamic("exp", "loss", 1.0 / (s + 1))
    b.log_dynamic("exp", "acc/top1", s * 0.01, step=s * 3)
b.log_dynamic("exp", "loss", float("inf"), step=500)
b.log_attachment("exp", "a.txt", "hello")
b.log_span("exp", "t1", "s1", "root", 1, 2, attributes={"x": 1})
b.log_eval_sample("exp", "ev1", "ds", {"q": "x"}, {"a": "y"}, scores={"acc": 1.0})
b.link_eval_sample_to_trace("exp", "ds", "ev1", "t1")
b.log_eval_annotation(
    "exp", "ds", "ev1", "good", AnnotationKind.FEEDBACK, AnnotationValueType.BOOL, True, "u"
)
b.log_span_annotation(
    "exp", "t1", "s1", "note", AnnotationKind.FEEDBACK, AnnotationValueType.BOOL, False, "u"
)
model_path = os.path.join(store, "model.bin")
open(model_path, "wb").write(bytes(10))
model, _ = b.log_model("exp", model_path, name="m")
b.end_experiment("exp")
print(json.dumps({"group_id": b.get_experiment("exp").group_id, "model_id": model.id}))
"""

# Calls every public read of the released SDK, each on a fresh copy of the store,
# and prints the results with their types.
OLD_READ_SWEEP = """
import datetime, enum, inspect, json, logging, os, shutil, sys, tempfile
logging.disable(logging.CRITICAL)
from luml.experiments.backends.sqlite import SQLiteBackend
store, info = sys.argv[1], json.loads(sys.argv[2])
ARGS = {
    "experiment_id": "exp", "group_id": info["group_id"], "key": "loss",
    "trace_id": "t1", "span_id": "s1", "eval_id": "ev1", "dataset_id": "ds",
    "eval_dataset_id": "ds", "name": "a.txt", "model_id": info["model_id"],
    "sort_by": "loss", "experiment_ids": ["exp"], "eval_ids": ["ev1"],
    "trace_ids": ["t1"], "groups_ids": [info["group_id"]],
}
def norm(x):
    if isinstance(x, enum.Enum):
        return [type(x).__name__, x.value]
    if isinstance(x, datetime.datetime):
        return ["datetime", x.isoformat()]
    if isinstance(x, dict):
        return {str(k): norm(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [norm(v) for v in x]
    if hasattr(x, "__dict__") and not isinstance(x, type):
        return [type(x).__name__, norm({k: v for k, v in vars(x).items() if k != "path"})]
    if isinstance(x, bytes):
        return ["bytes", len(x)]
    return [type(x).__name__, x]
results = {}
for name, fn in inspect.getmembers(SQLiteBackend, inspect.isfunction):
    if not name.startswith(("get_", "list_", "resolve_", "check_", "validate_")):
        continue
    params = list(inspect.signature(fn).parameters.values())[1:]
    if any(p.name not in ARGS and p.default is p.empty for p in params):
        continue
    copy = os.path.join(tempfile.mkdtemp(), "store")
    shutil.copytree(store, copy)
    try:
        results[name] = norm(fn(SQLiteBackend(copy), **{p.name: ARGS[p.name] for p in params if p.name in ARGS}))
    except Exception as error:
        results[name] = ["raised", type(error).__name__]
    shutil.rmtree(os.path.dirname(copy))
print(json.dumps(results))
"""

OLD_EXPORT = """
import sys
from luml.experiments.tracker import ExperimentTracker
ExperimentTracker("sqlite://" + sys.argv[1]).export(sys.argv[2], experiment_id="exp")
"""


def _run_old(script: str, *args: str) -> str:
    old = _old_sdk(script, *args)
    stdout, stderr = old.communicate(timeout=300)
    assert old.returncode == 0, stderr
    return stdout.strip().splitlines()[-1] if stdout.strip() else ""


def _revision2_and_3_stores(tmp_path: Path) -> tuple[Path, Path, str]:
    store2, store3 = tmp_path / "rev2", tmp_path / "rev3"
    info = _run_old(OLD_POPULATE, str(store2))
    shutil.copytree(store2, store3)
    conn = sqlite3.connect(store3 / EXP_ID / "exp.db")
    assert ExperimentMigrationRunner(conn).migrate() == [3]
    conn.close()
    return store2, store3, info


def test_released_sdk_reads_the_same_from_revision_3_as_from_revision_2(
    tmp_path: Path,
) -> None:
    store2, store3, info = _revision2_and_3_stores(tmp_path)

    reads2 = json.loads(_run_old(OLD_READ_SWEEP, str(store2), info))
    reads3 = json.loads(_run_old(OLD_READ_SWEEP, str(store3), info))

    assert reads2.pop("get_experiment_ddl_version") == ["int", 2]
    assert reads3.pop("get_experiment_ddl_version") == ["int", 3]
    assert len(reads2) > 30
    assert reads3 == reads2
    history = reads3["get_experiment_metric_history"]
    assert history[0]["logged_at"][0] == "datetime"


def test_released_sdk_exports_a_revision_3_experiment(tmp_path: Path) -> None:
    _, store3, _ = _revision2_and_3_stores(tmp_path)
    artifact = tmp_path / "exp.tar"

    _run_old(OLD_EXPORT, str(store3), str(artifact))

    with tarfile.open(artifact) as tar:
        member = tar.extractfile("exp.db.zip")
        assert member is not None
        db_bytes = zipfile.ZipFile(io.BytesIO(member.read())).read("exp.db")
    exported = tmp_path / "exported.db"
    exported.write_bytes(db_bytes)
    conn = sqlite3.connect(exported)
    assert conn.execute("PRAGMA user_version").fetchone() == (3,)
    counts = dict(
        conn.execute("SELECT key, count(*) FROM dynamic_metrics GROUP BY key")
    )
    assert counts == {"acc/top1": 200, "loss": 201}
    assert_bucket_invariants(conn)
    conn.close()


def test_released_sdk_reads_a_generation_2_snapshot_like_the_live_store(
    tmp_path: Path,
) -> None:
    store2, store3, info = _revision2_and_3_stores(tmp_path)
    artifact = tmp_path / "exp.tar"
    tracker = ExperimentTracker(f"sqlite://{store2}")
    tracker.export(str(artifact), experiment_id=EXP_ID)
    tracker.backend.close()
    published = tmp_path / "published"
    shutil.copytree(store3, published)
    db_path = published / EXP_ID / "exp.db"
    for suffix in ("-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    with tarfile.open(artifact) as tar:
        member = tar.extractfile("exp.db")
        assert member is not None
        db_path.write_bytes(member.read())

    reads3 = json.loads(_run_old(OLD_READ_SWEEP, str(store3), info))
    reads_published = json.loads(_run_old(OLD_READ_SWEEP, str(published), info))

    assert schema_snapshot(store2 / EXP_ID / "exp.db")[1] == 2
    assert reads_published == reads3
