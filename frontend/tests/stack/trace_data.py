"""Traces, spans and evals of the stack suites, logged the same way by every SDK.

Imported by this SDK's preparation scripts and by released luml-sdk 0.5.0 through
old_sdk_experiment.py, so it uses only the standard library and the tracker methods
both releases have. ``expected()`` is what the specs assert on screen.
"""

from __future__ import annotations

import random
from typing import Any, Protocol

DATASET = "qa"
TRACE_COUNT = 300
BIG_TRACE = "trace-big"
STAGES = 30
STEPS_PER_STAGE = 99
LARGE_KEY = "llm.prompt"
LARGE_CHARS = 1024 * 1024
MEDIUM_KEY = "retrieval.documents"
MEDIUM_CHARS = 100 * 1024
FEEDBACK_EVALS = 5
# 2026-01-01 00:00 UTC: span times are fixed, only created_at is the wall clock.
BASE_NS = 1_767_225_600 * 10**9
MS = 1_000_000
STATUS_BY_INDEX = (1, 2, 0)
STATE_LABELS = {0: "Unspecified", 1: "OK", 2: "Error", 3: "In Progress"}
CHILD_TYPES = (
    ("embed", "embeddings"),
    ("chat", "chat"),
    ("tool", "execute_tool"),
)
WORDS = ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel")


class Tracker(Protocol):
    def log_span(self, *args: Any, **kwargs: Any) -> None: ...  # noqa: ANN401
    def log_eval_sample(self, *args: Any, **kwargs: Any) -> None: ...  # noqa: ANN401
    def link_eval_sample_to_trace(self, *args: Any, **kwargs: Any) -> None: ...  # noqa: ANN401
    def log_eval_annotation(self, *args: Any, **kwargs: Any) -> Any: ...  # noqa: ANN401
    def log_span_annotation(self, *args: Any, **kwargs: Any) -> Any: ...  # noqa: ANN401


def trace_id(index: int) -> str:
    return f"trace-{index:04d}"


def eval_id(index: int) -> str:
    return f"eval-{index:04d}"


def payload_text(key: str, chars: int) -> str:
    """Words between ``BEGIN <key>`` and ``END <key>``, `chars` long: the markers let
    the preparation find where the value lies in the exported DB."""
    rng = random.Random(chars)
    head, tail = f"{begin_marker(key)} ", f" {end_marker(key)}"
    parts: list[str] = []
    length = len(head) + len(tail)
    while length < chars:
        word = rng.choice(WORDS)
        parts.append(word)
        length += len(word) + 1
    return (head + " ".join(parts))[: chars - len(tail)] + tail


def begin_marker(key: str) -> str:
    return f"BEGIN {key}"


def end_marker(key: str) -> str:
    return f"END {key}"


def regular_duration_ns(index: int) -> int:
    return (10 + index) * MS


def regular_span_count(index: int) -> int:
    return 2 + index % 3


def big_span_count() -> int:
    return 3 + STAGES + STAGES * STEPS_PER_STAGE


def scores(index: int) -> dict[str, Any]:
    rng = random.Random(1_000 + index)
    return {
        "accuracy": round(rng.random(), 3),
        "passed": rng.random() < 0.6,
        "tokens": rng.randint(20, 400),
    }


def log_regular_trace(tracker: Tracker, index: int) -> None:
    trace = trace_id(index)
    start = BASE_NS + index * 10_000 * MS
    end = start + regular_duration_ns(index)
    tracker.log_span(
        trace_id=trace,
        span_id=f"{trace}-root",
        name="request",
        start_time_unix_nano=start,
        end_time_unix_nano=end,
        status_code=STATUS_BY_INDEX[index % 3],
        attributes={"request.index": index, "user.tier": ("free", "pro")[index % 2]},
    )
    for child in range(regular_span_count(index) - 1):
        name, operation = CHILD_TYPES[child]
        tracker.log_span(
            trace_id=trace,
            span_id=f"{trace}-{name}",
            name=name,
            start_time_unix_nano=start + (child + 1) * MS,
            end_time_unix_nano=start + (child + 2) * MS,
            parent_span_id=f"{trace}-root",
            status_code=1,
            attributes={"gen_ai.operation.name": operation},
        )


def log_big_trace(tracker: Tracker) -> None:
    """One root, a chat span with a 1 MiB attribute, a failed tool span with a 100 KiB
    one, and stages of steps: a few thousand spans in all."""
    start = BASE_NS + (TRACE_COUNT + 10) * 10_000 * MS
    root = f"{BIG_TRACE}-root"
    tracker.log_span(
        trace_id=BIG_TRACE,
        span_id=root,
        name="pipeline",
        start_time_unix_nano=start,
        end_time_unix_nano=start + 12_500 * MS,
        status_code=1,
        attributes={"pipeline.stages": STAGES},
    )
    tracker.log_span(
        trace_id=BIG_TRACE,
        span_id=f"{BIG_TRACE}-generate",
        name="generate",
        start_time_unix_nano=start + 1 * MS,
        end_time_unix_nano=start + 900 * MS,
        parent_span_id=root,
        status_code=1,
        attributes={
            "llm.request.type": "chat",
            LARGE_KEY: payload_text(LARGE_KEY, LARGE_CHARS),
        },
    )
    tracker.log_span(
        trace_id=BIG_TRACE,
        span_id=f"{BIG_TRACE}-retrieve",
        name="retrieve",
        start_time_unix_nano=start + 901 * MS,
        end_time_unix_nano=start + 1_000 * MS,
        parent_span_id=root,
        status_code=2,
        status_message="retrieval timed out",
        attributes={
            "gen_ai.operation.name": "execute_tool",
            MEDIUM_KEY: payload_text(MEDIUM_KEY, MEDIUM_CHARS),
        },
    )
    for stage in range(STAGES):
        stage_start = start + (1_000 + stage * 380) * MS
        stage_id = f"{BIG_TRACE}-stage-{stage:02d}"
        tracker.log_span(
            trace_id=BIG_TRACE,
            span_id=stage_id,
            name=f"stage-{stage:02d}",
            start_time_unix_nano=stage_start,
            end_time_unix_nano=stage_start + 379 * MS,
            parent_span_id=root,
            status_code=1,
            attributes={"step.stage": stage},
        )
        for step in range(STEPS_PER_STAGE):
            step_start = stage_start + (step * 3 + 1) * MS
            tracker.log_span(
                trace_id=BIG_TRACE,
                span_id=f"{stage_id}-step-{step:03d}",
                name=f"step-{stage:02d}-{step:03d}",
                start_time_unix_nano=step_start,
                end_time_unix_nano=step_start + 2 * MS,
                parent_span_id=stage_id,
                status_code=1,
                attributes={"step.stage": stage, "step.index": step},
            )


def log_evals(tracker: Tracker) -> None:
    for index in range(TRACE_COUNT):
        tracker.log_eval_sample(
            eval_id=eval_id(index),
            dataset_id=DATASET,
            inputs={"question": f"Question {index}?"},
            outputs={"answer": f"Answer {index}"},
            references={"expected": f"Answer {index}"},
            scores=scores(index),
        )


def log_links_and_annotations(tracker: Tracker) -> None:
    for index in range(TRACE_COUNT):
        tracker.link_eval_sample_to_trace(
            eval_dataset_id=DATASET, eval_id=eval_id(index), trace_id=trace_id(index)
        )
    for index in range(FEEDBACK_EVALS):
        tracker.log_eval_annotation(
            dataset_id=DATASET,
            eval_id=eval_id(index),
            name="correct",
            annotation_kind="feedback",
            value_type="bool",
            value=index % 2 == 0,
            user="e2e",
        )
    for trace, span in (
        (trace_id(0), f"{trace_id(0)}-root"),
        (BIG_TRACE, f"{BIG_TRACE}-generate"),
    ):
        tracker.log_span_annotation(
            trace_id=trace,
            span_id=span,
            name="helpful",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="e2e",
        )


def log_all(tracker: Tracker) -> None:
    for index in range(TRACE_COUNT):
        log_regular_trace(tracker, index)
    log_big_trace(tracker)
    log_evals(tracker)
    log_links_and_annotations(tracker)


def expected() -> dict[str, Any]:
    """What the viewer and Flow show for this data, for the specs."""
    all_scores = [scores(index) for index in range(TRACE_COUNT)]
    averages = {
        key: sum(float(item[key]) for item in all_scores) / len(all_scores)
        for key in ("accuracy", "passed", "tokens")
    }
    known = [0, 1, 2, 3, 262, TRACE_COUNT - 1]
    return {
        "dataset": DATASET,
        "trace_count": TRACE_COUNT + 1,
        "traces": {
            trace_id(index): {
                "index": index,
                "span_count": regular_span_count(index),
                "execution_time_ns": regular_duration_ns(index),
                "state": STATE_LABELS[STATUS_BY_INDEX[index % 3]],
                "eval_id": eval_id(index),
            }
            for index in known
        },
        "big": {
            "trace_id": BIG_TRACE,
            "span_count": big_span_count(),
            "execution_time_ns": 12_500 * MS,
            "state": "OK",
            "first_rows": [
                "pipeline",
                "generate",
                "retrieve",
                "stage-00",
                "step-00-000",
            ],
            "root": {
                "span_id": f"{BIG_TRACE}-root",
                "key": "pipeline.stages",
                "value": str(STAGES),
            },
            "large": {
                "span": "generate",
                "span_id": f"{BIG_TRACE}-generate",
                "key": LARGE_KEY,
                "chars": LARGE_CHARS,
                "start": begin_marker(LARGE_KEY),
            },
            "medium": {
                "span": "retrieve",
                "span_id": f"{BIG_TRACE}-retrieve",
                "key": MEDIUM_KEY,
                "chars": MEDIUM_CHARS,
            },
            "small": {
                "span": "stage-00",
                "span_id": f"{BIG_TRACE}-stage-00",
                "key": "step.stage",
                "value": "0",
            },
        },
        "eval_count": TRACE_COUNT,
        "evals": {
            eval_id(index): {
                "index": index,
                "trace_id": trace_id(index),
                "scores": scores(index),
            }
            for index in known
        },
        "averages": averages,
        "attribute_keys": sorted(
            {
                "request.index",
                "user.tier",
                "gen_ai.operation.name",
                "pipeline.stages",
                "llm.request.type",
                LARGE_KEY,
                MEDIUM_KEY,
                "step.stage",
                "step.index",
            }
        ),
    }
