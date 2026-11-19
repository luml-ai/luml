"""What the platform specs expect beyond ``trace_data.expected()``, from the same data
definitions: logged metric values and static params, every eval, and the evals and
traces a search or filter leaves."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import old_sdk_experiment
import trace_data

# What the specs search and filter by (platform.spec.ts uses the same values).
EVAL_SEARCH = "Answer 12"
EVAL_MIN_TOKENS = 300
TRACE_TIER = "pro"


class RecordingTracker:
    """Takes the calls a data definition makes to a tracker and keeps what it logged."""

    def __init__(self, *_: Any, **__: Any) -> None:  # noqa: ANN401
        self.static: dict[str, Any] = {}
        self.dynamic: dict[str, list[float]] = {}

    def start_experiment(self, *_: Any, **__: Any) -> str:  # noqa: ANN401
        return "recorded"

    def log_static(self, key: str, value: Any) -> None:  # noqa: ANN401
        self.static[key] = value

    def log_dynamic(self, key: str, value: float, step: int) -> None:
        values = self.dynamic.setdefault(key, [])
        if step != len(values):
            raise ValueError(f"{key}: step {step} is not the next one")
        values.append(value)

    def end_experiment(self) -> None:
        pass

    def export(self, *_: Any) -> None:  # noqa: ANN401
        pass


def recorded(log: Callable[[RecordingTracker], None]) -> dict[str, Any]:
    tracker = RecordingTracker()
    log(tracker)
    return {"static": tracker.static, "metrics": tracker.dynamic}


def old_regular() -> dict[str, Any]:
    """The `old` experiment as luml-sdk 0.5.0 writes it (old_sdk_experiment.py)."""
    trackers: list[RecordingTracker] = []

    def make(*args: Any) -> RecordingTracker:  # noqa: ANN401
        trackers.append(RecordingTracker(*args))
        return trackers[-1]

    original = old_sdk_experiment.ExperimentTracker
    old_sdk_experiment.ExperimentTracker = make  # type: ignore[assignment,misc]
    try:
        old_sdk_experiment.write_regular("unused", "unused")
    finally:
        old_sdk_experiment.ExperimentTracker = original  # type: ignore[misc]
    return {"static": trackers[0].static, "metrics": trackers[0].dynamic}


def eval_row(index: int) -> dict[str, Any]:
    return {
        "id": trace_data.eval_id(index),
        "question": f"Question {index}?",
        "answer": f"Answer {index}",
        "expected": f"Answer {index}",
        "scores": trace_data.scores(index),
        "correct": index % 2 == 0 if index < trace_data.FEEDBACK_EVALS else None,
    }


def averages(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {
        key: sum(float(row["scores"][key]) for row in rows) / len(rows)
        for key in ("accuracy", "passed", "tokens")
    }


def searched(row: dict[str, Any], search: str) -> bool:
    """SQLite LIKE '%search%' over the id and the text inputs, outputs and refs."""
    texts = [row["id"], row["question"], row["answer"], row["expected"]]
    return any(search.lower() in text.lower() for text in texts)


def trace_row(index: int) -> dict[str, Any]:
    return {
        "id": trace_data.trace_id(index),
        "execution_time_ns": trace_data.regular_duration_ns(index),
        "status": trace_data.STATUS_BY_INDEX[index % 3],
        "span_count": trace_data.regular_span_count(index),
        "eval_id": trace_data.eval_id(index),
        "tier": ("free", "pro")[index % 2],
        "helpful": index == 0,
    }


def fixture_expected(path: Path) -> dict[str, Any]:
    """The metrics and the first eval dataset of a frozen fixture (its JSON)."""
    expected = json.loads(path.with_suffix(".json").read_text())["expected"]
    dataset, evals = next(iter(expected["datasets"].items()))
    return {
        "user_version": json.loads(path.with_suffix(".json").read_text())[
            "user_version"
        ],
        "metrics": expected["metrics"],
        "dataset": dataset,
        "eval_ids": evals["eval_ids"],
        "average_scores": evals["average_scores"],
    }


def expected(
    new_series: dict[str, Callable[[RecordingTracker], None]],
    fixtures: dict[str, Path],
) -> dict[str, Any]:
    evals = [eval_row(index) for index in range(trace_data.TRACE_COUNT)]
    found = [row for row in evals if searched(row, EVAL_SEARCH)]
    filtered = [row for row in evals if row["scores"]["tokens"] > EVAL_MIN_TOKENS]
    traces = [trace_row(index) for index in range(trace_data.TRACE_COUNT)]
    return {
        "experiments": {
            **{label: recorded(log) for label, log in new_series.items()},
            "old": old_regular(),
        },
        "evals": evals,
        "eval_search": {
            "text": EVAL_SEARCH,
            "ids": [row["id"] for row in found],
            "averages": averages(found),
        },
        "eval_filter": {
            "min_tokens": EVAL_MIN_TOKENS,
            "ids": [row["id"] for row in filtered],
            "averages": averages(filtered),
        },
        "traces": traces,
        "trace_filter": {
            "tier": TRACE_TIER,
            "ids": [row["id"] for row in traces if row["tier"] == TRACE_TIER],
        },
        "fixtures": {label: fixture_expected(path) for label, path in fixtures.items()},
    }
