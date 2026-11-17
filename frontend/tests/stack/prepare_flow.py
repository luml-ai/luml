"""Writes the Flow suite's store: old-schema, new-schema and live experiments.

The old-schema experiment is written first by released luml-sdk 0.5.0 (when
E2E_OLD_SDK_PYTHON points at its venv), so the store itself starts as a 0.5.0
store; this SDK then adds its experiments to the same store. ``$1/flow.json`` gets
the ids and the old experiment's DB path and schema revision. Usage:
``python prepare_flow.py <flow dir>``.
"""

from __future__ import annotations

import json
import math
import os
import random
import sqlite3
import subprocess
import sys
from pathlib import Path

from luml.experiments.tracker import ExperimentTracker

HERE = Path(__file__).resolve().parent
NEW_STEPS = 200_000
LIVE_STEPS = 1_000


def log_series(
    tracker: ExperimentTracker, experiment_id: str, start: int, stop: int, seed: int
) -> None:
    rng = random.Random(seed)
    for step in range(start, stop):
        value = math.exp(-step / 5_000) + rng.random() * 0.01
        tracker.log_dynamic("train/loss", value, step=step, experiment_id=experiment_id)


def user_version(path: Path) -> int:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        return int(connection.execute("PRAGMA user_version").fetchone()[0])


def main() -> None:
    flow_dir = Path(sys.argv[1])
    store = flow_dir / "store"
    result: dict[str, object] = {"store": str(store)}

    python = os.environ.get("E2E_OLD_SDK_PYTHON")
    if python and Path(python).exists():
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
    # Recorded before this SDK opens the store: nothing it does may migrate these.
    old_versions = {db.parent.name: user_version(db) for db in store.glob("*/exp.db")}

    tracker = ExperimentTracker(f"sqlite://{store}")
    old = [item for item in tracker.list_experiments() if item.name == "old"]
    new_id = tracker.start_experiment(name="flow_new", group="e2e")
    log_series(tracker, new_id, 0, NEW_STEPS, 41)
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
    )
    if old:
        db = store / old[0].id / "exp.db"
        result["old"] = {
            "id": old[0].id,
            "group_id": old[0].group_id,
            "db": str(db),
            "user_version": old_versions[old[0].id],
            "user_version_after_store_open": user_version(db),
        }
    (flow_dir / "flow.json").write_text(json.dumps(result, indent=2))
    old_state = "yes" if old else "no (no luml-sdk 0.5.0)"
    sys.stdout.write(f"flow store ready; old-schema experiment: {old_state}\n")


if __name__ == "__main__":
    main()
