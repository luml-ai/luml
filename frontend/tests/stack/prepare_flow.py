"""Writes the Flow suite's store: old-schema, new-schema and live experiments.

The old-schema experiment is written first by released luml-sdk 0.5.0 (when
E2E_OLD_SDK_PYTHON points at its venv), so the store itself starts as a 0.5.0
store; this SDK then adds its experiments to the same store. ``$1/flow.json`` gets
the ids and the old experiment's DB path and schema revision. Usage:
``python prepare_flow.py <flow dir>``.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import old_sdk_experiment
import trace_data
from old_sdk import old_sdk_python

from luml.experiments.tracker import ExperimentTracker

HERE = Path(__file__).resolve().parent
NEW_STEPS = 200_000
LIVE_STEPS = 1_000
OTHER_STEPS = 500
OTHER_ITEMS = 3
# Evals whose id holds this text: the searched evals of the score averages test.
EVAL_SEARCH = "eval-001"


def log_series(
    tracker: ExperimentTracker, experiment_id: str, start: int, stop: int, seed: int
) -> None:
    rng = random.Random(seed)
    for step in range(start, stop):
        value = math.exp(-step / 5_000) + rng.random() * 0.01
        tracker.log_dynamic("train/loss", value, step=step, experiment_id=experiment_id)


def log_other(tracker: ExperimentTracker, experiment_id: str) -> dict[str, Any]:
    """Traces, evals and a metric that differ from every other experiment's."""
    log_series(tracker, experiment_id, 0, OTHER_STEPS, 43)
    evals: dict[str, float] = {}
    for item in range(OTHER_ITEMS):
        trace = f"other-{item}"
        start = trace_data.BASE_NS + item * 1_000 * trace_data.MS
        tracker.log_span(
            trace_id=trace,
            span_id=f"{trace}-root",
            name="other-request",
            start_time_unix_nano=start,
            end_time_unix_nano=start + 7 * trace_data.MS,
            status_code=1,
            attributes={"other.index": item},
        )
        evals[trace] = (item + 1) / (OTHER_ITEMS + 1)
        tracker.log_eval_sample(
            eval_id=trace,
            dataset_id="other",
            inputs={"question": f"Other {item}?"},
            outputs={"answer": f"Other {item}"},
            scores={"accuracy": evals[trace]},
        )
        tracker.link_eval_sample_to_trace(
            eval_dataset_id="other", eval_id=trace, trace_id=trace
        )
    return {
        "steps": OTHER_STEPS,
        "dataset": "other",
        "trace_ids": list(evals),
        "evals": evals,
        "averages": {"accuracy": sum(evals.values()) / len(evals)},
    }


def eval_search_averages() -> dict[str, Any]:
    indexes = [
        index
        for index in range(trace_data.TRACE_COUNT)
        if EVAL_SEARCH in trace_data.eval_id(index)
    ]
    scores = [trace_data.scores(index) for index in indexes]
    return {
        "search": EVAL_SEARCH,
        "ids": [trace_data.eval_id(index) for index in indexes],
        "averages": {
            key: sum(float(item[key]) for item in scores) / len(scores)
            for key in ("accuracy", "passed", "tokens")
        },
    }


def user_version(path: Path) -> int:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        return int(connection.execute("PRAGMA user_version").fetchone()[0])


def main() -> None:
    flow_dir = Path(sys.argv[1])
    store = flow_dir / "store"
    result: dict[str, object] = {"store": str(store)}
    trace_seconds = 0.0

    python = old_sdk_python(
        "the old-schema tests are skipped and the comparisons leave the old "
        "experiment out"
    )
    if python:
        subprocess.run(
            [
                python,
                "-I",
                str(HERE / "old_sdk_experiment.py"),
                str(store),
                str(flow_dir / "old.tar"),
            ],
            check=True,
        )
        (flow_dir / "old.tar").unlink()
        started = time.monotonic()
        subprocess.run(
            [python, "-I", str(HERE / "old_sdk_experiment.py"), "traces", str(store)],
            check=True,
        )
        trace_seconds = time.monotonic() - started
        subprocess.run(
            [python, "-I", str(HERE / "old_sdk_experiment.py"), "legacy", str(store)],
            check=True,
        )
    # Recorded before this SDK opens the store: nothing it does may migrate these.
    old_versions = {db.parent.name: user_version(db) for db in store.glob("*/exp.db")}

    tracker = ExperimentTracker(f"sqlite://{store}")
    old = [item for item in tracker.list_experiments() if item.name == "old"]
    traces_old = [
        item for item in tracker.list_experiments() if item.name == "traces_old"
    ]
    started = time.monotonic()
    traces_id = tracker.start_experiment(name="flow_traces", group="e2e")
    trace_data.log_all(tracker)
    tracker.end_experiment()
    trace_seconds += time.monotonic() - started
    new_id = tracker.start_experiment(name="flow_new", group="e2e")
    log_series(tracker, new_id, 0, NEW_STEPS, 41)
    tracker.end_experiment()
    other_id = tracker.start_experiment(name="flow_other", group="e2e")
    other = log_other(tracker, other_id)
    tracker.end_experiment()
    live_id = tracker.start_experiment(name="flow_live", group="e2e")
    log_series(tracker, live_id, 0, LIVE_STEPS, 42)
    tracker.backend.flush(live_id)
    # Leave it running: the tracker fails its active experiment when it is collected.
    tracker.current_experiment_id = None

    groups = {group.name: group.id for group in tracker.list_groups()}
    experiments = {item.name: item for item in tracker.list_experiments()}
    result.update(
        new={
            "id": new_id,
            "group_id": experiments["flow_new"].group_id,
            "steps": NEW_STEPS,
        },
        live={
            "id": live_id,
            "group_id": experiments["flow_live"].group_id,
            "steps": LIVE_STEPS,
        },
        groups=groups,
        traces={
            "id": traces_id,
            "group_id": experiments["flow_traces"].group_id,
            "db": str(store / traces_id / "exp.db"),
            "user_version": user_version(store / traces_id / "exp.db"),
        },
        expected=trace_data.expected(),
        other={
            "id": other_id,
            "group_id": experiments["flow_other"].group_id,
            **other,
        },
        eval_search=eval_search_averages(),
        large_sha256=hashlib.sha256(
            trace_data.payload_text(
                trace_data.LARGE_KEY, trace_data.LARGE_CHARS
            ).encode()
        ).hexdigest(),
    )
    if traces_old:
        db = store / traces_old[0].id / "exp.db"
        result["traces_old"] = {
            "id": traces_old[0].id,
            "group_id": traces_old[0].group_id,
            "db": str(db),
            "user_version": old_versions[traces_old[0].id],
        }
    if old:
        db = store / old[0].id / "exp.db"
        result["old"] = {
            "id": old[0].id,
            "group_id": old[0].group_id,
            "db": str(db),
            "user_version": old_versions[old[0].id],
            "user_version_after_store_open": user_version(db),
            "seed": old_sdk_experiment.SEED,
        }
    if python:
        result["fractional"] = {
            "id": "fallback",
            "group_id": experiments["fallback"].group_id,
            "db": str(store / "fallback" / "exp.db"),
            "user_version": old_versions["fallback"],
            "steps": old_sdk_experiment.LEGACY_STEPS,
        }
    (flow_dir / "flow.json").write_text(json.dumps(result, indent=2))
    old_state = "yes" if old else "no (no luml-sdk 0.5.0)"
    sys.stdout.write(
        f"flow store ready; old-schema experiment: {old_state}; "
        f"trace experiments written in {trace_seconds:.1f}s\n"
    )


if __name__ == "__main__":
    main()
