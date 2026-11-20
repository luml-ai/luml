"""Appends points to the live Flow experiment from another process, as training does.

Usage: ``python append_live.py <store> <experiment id> <count>``. Continues after the
metric's current last step and prints the new last step.
"""

import math
import random
import sys

from luml.experiments.tracker import ExperimentTracker

KEY = "train/loss"


def main() -> None:
    store, experiment_id, count = sys.argv[1], sys.argv[2], int(sys.argv[3])
    tracker = ExperimentTracker(f"sqlite://{store}")
    catalog = tracker.get_metric_catalog(experiment_id)
    last = next(metric.last_step for metric in catalog.metrics if metric.key == KEY)
    rng = random.Random(last)
    for step in range(last + 1, last + 1 + count):
        value = math.exp(-step / 5_000) + rng.random() * 0.01
        tracker.log_dynamic(KEY, value, step=step, experiment_id=experiment_id)
    tracker.backend.flush(experiment_id)
    sys.stdout.write(f"{last + count}\n")


if __name__ == "__main__":
    main()
