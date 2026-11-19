"""A training process on released luml-sdk 0.5.0 writing to a Flow store Flow shows.

Run with the interpreter of the luml-sdk 0.5.0 venv (``python -I``):

- ``flow_old_live.py start <store> <name>`` starts an experiment, writes round 0 and
  leaves the experiment running.
- ``flow_old_live.py append <store> <experiment id> <round> [metrics|no-metrics]``
  writes one more round; ``no-metrics`` writes its spans and evals only.

Each call prints what it wrote as JSON: the experiment id (and its group id on start),
the metric's last step (or null), the trace ids and the eval ids with their scores.
"""

import json
import math
import sys

from luml.experiments.tracker import ExperimentTracker

KEY = "train/loss"
DATASET = "live"
STEPS_PER_ROUND = 200
ITEMS_PER_ROUND = 3
# 2026-02-01 00:00 UTC: after trace_data.py's spans.
BASE_NS = 1_769_904_000 * 10**9
MS = 1_000_000


def trace_id(round_index: int, item: int) -> str:
    return f"live-{round_index}-{item}"


def accuracy(round_index: int, item: int) -> float:
    return round((round_index * ITEMS_PER_ROUND + item + 1) / 10, 3)


def write_round(
    tracker: ExperimentTracker, experiment_id: str, round_index: int, metrics: bool
) -> dict[str, object]:
    last_step = None
    if metrics:
        first = round_index * STEPS_PER_ROUND
        for step in range(first, first + STEPS_PER_ROUND):
            value = math.exp(-step / 1_000)
            tracker.log_dynamic(KEY, value, step=step, experiment_id=experiment_id)
        last_step = first + STEPS_PER_ROUND - 1
    evals: dict[str, float] = {}
    for item in range(ITEMS_PER_ROUND):
        trace = trace_id(round_index, item)
        start = BASE_NS + (round_index * ITEMS_PER_ROUND + item) * 1_000 * MS
        tracker.log_span(
            trace_id=trace,
            span_id=f"{trace}-root",
            name="live-request",
            start_time_unix_nano=start,
            end_time_unix_nano=start + 5 * MS,
            status_code=1,
            attributes={"live.round": round_index},
            experiment_id=experiment_id,
        )
        tracker.log_eval_sample(
            eval_id=trace,
            dataset_id=DATASET,
            inputs={"question": f"Live {trace}?"},
            outputs={"answer": f"Live {trace}"},
            scores={"accuracy": accuracy(round_index, item)},
            experiment_id=experiment_id,
        )
        tracker.link_eval_sample_to_trace(
            eval_dataset_id=DATASET,
            eval_id=trace,
            trace_id=trace,
            experiment_id=experiment_id,
        )
        evals[trace] = accuracy(round_index, item)
    return {
        "id": experiment_id,
        "last_step": last_step,
        "trace_ids": list(evals),
        "evals": evals,
    }


def main() -> None:
    mode, store = sys.argv[1], sys.argv[2]
    tracker = ExperimentTracker(f"sqlite://{store}")
    if mode == "start":
        experiment_id = tracker.start_experiment(name=sys.argv[3], group="e2e")
        written = write_round(tracker, experiment_id, 0, metrics=True)
        written["group_id"] = next(
            item.group_id
            for item in tracker.list_experiments()
            if item.id == experiment_id
        )
        # Still running when this process ends, as a training run between two writes.
        tracker.current_experiment_id = None
    else:
        experiment_id, round_index = sys.argv[3], int(sys.argv[4])
        metrics = (sys.argv[5] if len(sys.argv) > 5 else "metrics") == "metrics"
        written = write_round(tracker, experiment_id, round_index, metrics)
    sys.stdout.write(json.dumps(written) + "\n")


if __name__ == "__main__":
    main()
