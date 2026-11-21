"""Writes to a Flow store with this SDK while Flow shows it, as other processes do.

Run from the SDK project (``uv run --frozen python flow_writer.py ...``); each mode
prints what it wrote as JSON:

- ``start <store> <name> <points>``: a running experiment with the metrics
  ``CHANGED`` and ``STEADY`` (``points`` steps from 0, see ``start_value``) and the
  span ``SPAN``, its attribute ``SPAN_ATTRIBUTE`` set to ``first``, and the eval
  ``LARGE_EVAL`` whose input is over the viewer's preview size.
- ``overwrite <store> <id> <step> <value> <appended>``: logs ``value`` at an
  existing ``step`` of ``CHANGED``, then ``appended`` points after its last step,
  each ``APPENDED_VALUE``.
- ``respan <store> <id> <value>``: logs ``SPAN`` again, same ids, the attribute set
  to ``value``.
- ``implicit <store> <id> <writer> <count> <mode> <barrier dir> <writers>``: logs
  ``count`` points of ``CHANGED`` without steps, each ``writer * 1000 + index``,
  once ``writers`` processes are ready. ``interleaved`` flushes after each point;
  ``buffered`` flushes once, after every writer has buffered all its points.
- ``fractional <store> <id>``: logs a point of ``CHANGED`` at step 2.5, which this
  SDK refuses; prints the error's type.
"""

import json
import sys
import time
from pathlib import Path
from typing import Any

from luml.experiments.tracker import ExperimentTracker

CHANGED = "edit/changed"
STEADY = "edit/steady"
APPENDED_VALUE = 0.25
SPAN = ("edit-trace", "edit-root")
SPAN_ATTRIBUTE = "edit.round"
# 2026-03-01 00:00 UTC.
SPAN_START_NS = 1_772_323_200 * 10**9
LARGE_EVAL = ("edit", "edit-eval-large")
# Above the 2,000 characters the viewer previews: the input gets a Show all button.
LARGE_INPUT_CHARS = 5_000
BARRIER_TIMEOUT_S = 60.0
# Background flushes would end the buffering early.
NEVER_S = 3_600.0


def start_value(key: str, step: int, points: int) -> float:
    """Inside (0, 1), so an overwrite with a value between keeps the min and the max."""
    fraction = (step + 1) / (points + 1)
    return fraction if key == CHANGED else 1 - fraction


def log_span(tracker: ExperimentTracker, experiment_id: str, value: str) -> None:
    tracker.log_span(
        trace_id=SPAN[0],
        span_id=SPAN[1],
        name="edited-request",
        start_time_unix_nano=SPAN_START_NS,
        end_time_unix_nano=SPAN_START_NS + 3_000_000,
        status_code=1,
        attributes={SPAN_ATTRIBUTE: value},
        experiment_id=experiment_id,
    )


def start(store: str, name: str, points: int) -> dict[str, object]:
    tracker = ExperimentTracker(f"sqlite://{store}")
    experiment_id = tracker.start_experiment(name=name, group="e2e")
    for key in (CHANGED, STEADY):
        for step in range(points):
            tracker.log_dynamic(key, start_value(key, step, points), step=step)
    log_span(tracker, experiment_id, "first")
    tracker.log_eval_sample(
        eval_id=LARGE_EVAL[1],
        dataset_id=LARGE_EVAL[0],
        inputs={"prompt": "long prompt " * (LARGE_INPUT_CHARS // 12)},
        outputs={"answer": "short"},
        scores={"accuracy": 1.0},
    )
    tracker.backend.flush(experiment_id)
    group_id = next(
        item.group_id for item in tracker.list_experiments() if item.id == experiment_id
    )
    # Still running when this process ends, as a training run between two writes.
    tracker.current_experiment_id = None
    return {"id": experiment_id, "group_id": group_id}


def overwrite(
    store: str, experiment_id: str, step: int, value: float, appended: int
) -> dict[str, object]:
    tracker = ExperimentTracker(f"sqlite://{store}")
    catalog = tracker.get_metric_catalog(experiment_id)
    last = next(metric.last_step for metric in catalog.metrics if metric.key == CHANGED)
    tracker.log_dynamic(CHANGED, value, step=step, experiment_id=experiment_id)
    for appended_step in range(last + 1, last + 1 + appended):
        tracker.log_dynamic(
            CHANGED, APPENDED_VALUE, step=appended_step, experiment_id=experiment_id
        )
    tracker.backend.flush(experiment_id)
    return {"last_step": last + appended}


def wait_for_writers(barrier: Path, writer: int, writers: int, stage: str) -> None:
    (barrier / f"{stage}-{writer}").touch()
    deadline = time.monotonic() + BARRIER_TIMEOUT_S
    while len(list(barrier.glob(f"{stage}-*"))) < writers:
        if time.monotonic() > deadline:
            sys.exit(f"writer {writer}: the other writers did not reach {stage}")
        time.sleep(0.01)


def implicit(
    store: str,
    experiment_id: str,
    writer: int,
    count: int,
    mode: str,
    barrier: Path,
    writers: int,
) -> dict[str, object]:
    tracker = ExperimentTracker(f"sqlite://{store}", flush_interval=NEVER_S)
    wait_for_writers(barrier, writer, writers, "ready")
    for index in range(count):
        tracker.log_dynamic(CHANGED, writer * 1000 + index, experiment_id=experiment_id)
        if mode == "interleaved":
            tracker.backend.flush(experiment_id)
    if mode == "buffered":
        wait_for_writers(barrier, writer, writers, "buffered")
    tracker.backend.flush(experiment_id)
    return {"writer": writer, "count": count}


def fractional(store: str, experiment_id: str) -> dict[str, object]:
    tracker = ExperimentTracker(f"sqlite://{store}")
    # What a caller without type checks passes; the hint says int.
    step: Any = 2.5
    try:
        tracker.log_dynamic(CHANGED, 1.0, step=step, experiment_id=experiment_id)
    except TypeError as error:
        return {"raised": type(error).__name__}
    return {"raised": None}


def main() -> None:
    mode, store, args = sys.argv[1], sys.argv[2], sys.argv[3:]
    if mode == "start":
        written = start(store, args[0], int(args[1]))
    elif mode == "overwrite":
        written = overwrite(store, args[0], int(args[1]), float(args[2]), int(args[3]))
    elif mode == "respan":
        tracker = ExperimentTracker(f"sqlite://{store}")
        log_span(tracker, args[0], args[1])
        tracker.backend.flush(args[0])
        written = {"span": list(SPAN)}
    elif mode == "implicit":
        written = implicit(
            store,
            args[0],
            int(args[1]),
            int(args[2]),
            args[3],
            Path(args[4]),
            int(args[5]),
        )
    elif mode == "fractional":
        written = fractional(store, args[0])
    else:
        sys.exit(f"unknown mode {mode}")
    sys.stdout.write(json.dumps(written) + "\n")


if __name__ == "__main__":
    main()
