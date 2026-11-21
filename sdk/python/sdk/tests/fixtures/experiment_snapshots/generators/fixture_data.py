"""Fixed experiment content shared by every fixture generator (no randomness)."""

import json
import math
import os
from pathlib import Path
from typing import Any, Protocol

FIXED_FILE_TIME = 1_760_000_000

STATIC_PARAMS: dict[str, Any] = {
    "learning_rate": 0.001,
    "epochs": 40,
    "optimizer": "adam",
    "use_amp": True,
    "layers": [64, 32],
    "config": {"dropout": 0.1, "seed": 7},
    "dataset_name": "Größe – 東京 ✓",
}


def metric_points() -> dict[str, list[tuple[int, float]]]:
    train_loss = [(step, round(2.0 * 0.9**step, 6)) for step in range(40)]
    val_accuracy = [
        (step, 25.0 if step == 20 else round(0.5 + 0.01 * step, 6))
        for step in range(40)
    ]
    lr_schedule = [(step, round(0.001 * (1 - step / 50), 8)) for step in range(25)]
    return {
        "train_loss": train_loss,
        "val_accuracy": val_accuracy,
        "lr_schedule": lr_schedule,
    }


NON_FINITE_METRIC = "unstable_loss"
NON_FINITE_POINTS: list[tuple[int, float]] = [
    (0, 1.0),
    (1, 0.5),
    (2, math.nan),
    (3, 0.25),
    (4, math.inf),
    (5, 0.125),
]

ATTACHMENTS: dict[str, str] = {
    "notes.txt": "fixture experiment notes\nline two\n",
    "config.json": '{"model": "tiny", "layers": [64, 32]}\n',
}

TRACE_ID = "0af7651916cd43dd8448eb211c80319c"
SECOND_TRACE_ID = "1bf8762a27de54ee9559fc322d91420d"
BASE_NS = 1_760_000_000_000_000_000
SPANS: list[dict[str, Any]] = [
    {
        "trace_id": TRACE_ID,
        "span_id": "b7ad6b7169203331",
        "parent_span_id": None,
        "name": "agent_run",
        "start": BASE_NS,
        "end": BASE_NS + 900_000_000,
        "status_code": 1,
        "attributes": {"input.value": "What is LUML?", "user.city": "Zürich"},
    },
    {
        "trace_id": TRACE_ID,
        "span_id": "c1d2e3f4a5b6c7d8",
        "parent_span_id": "b7ad6b7169203331",
        "name": "llm_call",
        "start": BASE_NS + 100_000_000,
        "end": BASE_NS + 400_000_000,
        "status_code": 1,
        "attributes": {
            "gen_ai.operation.name": "chat",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.input_tokens": 42,
        },
    },
    {
        "trace_id": TRACE_ID,
        "span_id": "d1e2f3a4b5c6d7e8",
        "parent_span_id": "b7ad6b7169203331",
        "name": "tool_call",
        "start": BASE_NS + 450_000_000,
        "end": BASE_NS + 850_000_000,
        "status_code": 1,
        "attributes": {"gen_ai.operation.name": "execute_tool", "tool.name": "search"},
        "events": [
            {
                "name": "retry",
                "timestamp": BASE_NS + 460_000_000,
                "attributes": {"attempt": 1},
            }
        ],
        "links": [
            {
                "trace_id": SECOND_TRACE_ID,
                "span_id": "f1a2b3c4d5e6f7a8",
                "attributes": {},
            }
        ],
    },
    {
        "trace_id": TRACE_ID,
        "span_id": "e1f2a3b4c5d6e7f8",
        "parent_span_id": "d1e2f3a4b5c6d7e8",
        "name": "suche_überprüfen",
        "start": BASE_NS + 500_000_000,
        "end": BASE_NS + 800_000_000,
        "status_code": 2,
        "status_message": "index timeout",
        "attributes": {"retrieval.documents": 3},
    },
    {
        "trace_id": SECOND_TRACE_ID,
        "span_id": "f1a2b3c4d5e6f7a8",
        "parent_span_id": None,
        "name": "summarize",
        "start": BASE_NS + 2_000_000_000,
        "end": BASE_NS + 2_500_000_000,
        "status_code": 1,
        "attributes": {"input.value": "Summarize the release notes"},
    },
    {
        "trace_id": SECOND_TRACE_ID,
        "span_id": "a8b7c6d5e4f3a2b1",
        "parent_span_id": "f1a2b3c4d5e6f7a8",
        "name": "llm_call",
        "start": BASE_NS + 2_100_000_000,
        "end": BASE_NS + 2_400_000_000,
        "status_code": 1,
        "attributes": {
            "gen_ai.operation.name": "chat",
            "gen_ai.request.model": "gpt-4o-mini",
        },
    },
]

DATASET_ID = "qa_set"
SECOND_DATASET_ID = "summaries"
EVALS: list[dict[str, Any]] = [
    {
        "dataset_id": DATASET_ID,
        "id": "e1",
        "inputs": {"question": "What is LUML?"},
        "outputs": {"answer": "An ML platform"},
        "refs": {"answer": "An ML platform"},
        "scores": {"exact_match": 1.0, "relevance": 0.9},
        "metadata": {"source": "docs"},
    },
    {
        "dataset_id": DATASET_ID,
        "id": "e2",
        "inputs": {"question": "What is Flow?"},
        "outputs": {"answer": "A tracker"},
        "refs": {"answer": "The experiment tracker"},
        "scores": {"exact_match": 0.0, "relevance": 0.6},
        "metadata": {"source": "faq"},
    },
    {
        "dataset_id": DATASET_ID,
        "id": "e3",
        "inputs": {"question": "Ist es quelloffen? 東京"},
        "outputs": {"answer": "Ja"},
        "refs": {"answer": "Ja"},
        "scores": {"exact_match": 1.0, "relevance": 0.75},
        "metadata": {"source": "faq"},
    },
    {
        "dataset_id": SECOND_DATASET_ID,
        "id": "s1",
        "inputs": {"document": "release notes"},
        "outputs": {"summary": "Bug fixes"},
        "refs": None,
        "scores": {"rouge": 0.4},
        "metadata": None,
    },
    {
        "dataset_id": SECOND_DATASET_ID,
        "id": "s2",
        "inputs": {"document": "changelog"},
        "outputs": {"summary": "New flags"},
        "refs": None,
        "scores": None,
        "metadata": None,
    },
    {
        "dataset_id": SECOND_DATASET_ID,
        "id": "s3",
        "inputs": {"document": "roadmap"},
        "outputs": None,
        "refs": None,
        "scores": {"rouge": 0.2},
        "metadata": None,
    },
]
EVAL_TRACE_LINKS: list[tuple[str, str, str]] = [
    (DATASET_ID, "e1", TRACE_ID),
    (SECOND_DATASET_ID, "s1", SECOND_TRACE_ID),
]

EVAL_ANNOTATIONS: list[dict[str, Any]] = [
    {
        "dataset_id": DATASET_ID,
        "eval_id": "e1",
        "name": "helpful",
        "annotation_kind": "feedback",
        "value_type": "bool",
        "value": True,
        "rationale": "Matches the docs",
    },
    {
        "dataset_id": DATASET_ID,
        "eval_id": "e2",
        "name": "helpful",
        "annotation_kind": "feedback",
        "value_type": "bool",
        "value": False,
    },
    {
        "dataset_id": DATASET_ID,
        "eval_id": "e2",
        "name": "expected_answer",
        "annotation_kind": "expectation",
        "value_type": "string",
        "value": "The experiment tracker",
    },
    {
        "dataset_id": DATASET_ID,
        "eval_id": "e3",
        "name": "quality",
        "annotation_kind": "expectation",
        "value_type": "int",
        "value": 4,
    },
]
SPAN_ANNOTATIONS: list[dict[str, Any]] = [
    {
        "trace_id": TRACE_ID,
        "span_id": "c1d2e3f4a5b6c7d8",
        "name": "correct",
        "annotation_kind": "feedback",
        "value_type": "bool",
        "value": True,
        "rationale": "Cited the right page",
    },
    {
        "trace_id": TRACE_ID,
        "span_id": "b7ad6b7169203331",
        "name": "latency_ok",
        "annotation_kind": "expectation",
        "value_type": "bool",
        "value": False,
    },
]

# Edge cases for the trace and eval readers, logged only into fixtures that say so:
# a span payload far larger than its tree row, and scores the readers must skip.
EDGE_TRACE_ID = "2c09873b38ef65ff0660ad433ea2531e"
LARGE_ATTRIBUTE_KEY = "llm.prompt"
LARGE_ATTRIBUTE_SIZE = 200 * 1024


def large_attribute_value() -> str:
    lines = (f"line {index:06d} of a long prompt\n" for index in range(10_000))
    return "".join(lines)[:LARGE_ATTRIBUTE_SIZE]


EDGE_SPANS: list[dict[str, Any]] = [
    {
        "trace_id": EDGE_TRACE_ID,
        "span_id": "0123456789abcdef",
        "parent_span_id": None,
        "name": "large_prompt",
        "start": BASE_NS + 3_000_000_000,
        "end": BASE_NS + 3_200_000_000,
        "status_code": 1,
        "attributes": {
            LARGE_ATTRIBUTE_KEY: large_attribute_value(),
            "prompt.kind": "large",
        },
    },
    {
        "trace_id": EDGE_TRACE_ID,
        "span_id": "fedcba9876543210",
        "parent_span_id": "0123456789abcdef",
        "name": "llm_call",
        "start": BASE_NS + 3_050_000_000,
        "end": BASE_NS + 3_150_000_000,
        "status_code": 2,
        "status_message": "rate limited",
        "attributes": {"gen_ai.operation.name": "chat", "retry.count": 2},
    },
]

EDGE_DATASET_ID = "edge_scores"
# json.dumps writes NaN, which JSON.parse rejects, so the viewer counts no score of x2.
EDGE_EVALS: list[dict[str, Any]] = [
    {
        "dataset_id": EDGE_DATASET_ID,
        "id": "x1",
        "inputs": {"question": "numbers, booleans and strings"},
        "outputs": None,
        "refs": None,
        "scores": {"accuracy": 1.0, "passed": True, "grade": "A"},
        "metadata": None,
    },
    {
        "dataset_id": EDGE_DATASET_ID,
        "id": "x2",
        "inputs": {"question": "a NaN score"},
        "outputs": None,
        "refs": None,
        "scores": {"unstable_score": math.nan, "passed": False, "grade": "C"},
        "metadata": None,
    },
    {
        "dataset_id": EDGE_DATASET_ID,
        "id": "x3",
        "inputs": {"question": "numbers, booleans and strings"},
        "outputs": None,
        "refs": None,
        "scores": {"accuracy": 0.5, "passed": True, "grade": "B"},
        "metadata": None,
    },
    {
        "dataset_id": EDGE_DATASET_ID,
        "id": "x4",
        "inputs": {"question": "a boolean only"},
        "outputs": None,
        "refs": None,
        "scores": {"passed": False},
        "metadata": None,
    },
]


def _non_finite_label(value: float) -> str:
    return "nan" if math.isnan(value) else "inf" if math.isinf(value) else "finite"


class Tracker(Protocol):
    """The tracker methods used here; their signatures are the same in every era."""

    def log_static(self, *args, **kwargs) -> None: ...
    def log_dynamic(self, *args, **kwargs) -> None: ...
    def log_attachment(self, *args, **kwargs) -> None: ...
    def log_span(self, *args, **kwargs) -> None: ...
    def log_eval_sample(self, *args, **kwargs) -> None: ...
    def link_eval_sample_to_trace(self, *args, **kwargs) -> None: ...
    def log_eval_annotation(self, *args, **kwargs) -> object: ...
    def log_span_annotation(self, *args, **kwargs) -> object: ...


def _log_non_finite_metric(tracker: Tracker, exp_id: str) -> dict[str, str]:
    outcomes: dict[str, str] = {}
    for step, value in NON_FINITE_POINTS:
        try:
            tracker.log_dynamic(
                NON_FINITE_METRIC, value, step=step, experiment_id=exp_id
            )
            outcome = "accepted"
        except Exception as error:
            outcome = f"error: {type(error).__name__}: {error}"
        if _non_finite_label(value) != "finite":
            outcomes[_non_finite_label(value)] = outcome
    return outcomes


def _log_spans(
    tracker: Tracker, exp_id: str, spans: list[dict[str, Any]] = SPANS
) -> None:
    for span in spans:
        tracker.log_span(
            span["trace_id"],
            span["span_id"],
            span["name"],
            span["start"],
            span["end"],
            parent_span_id=span["parent_span_id"],
            kind=1,
            status_code=span["status_code"],
            status_message=span.get("status_message"),
            attributes=span["attributes"],
            events=span.get("events"),
            links=span.get("links"),
            experiment_id=exp_id,
        )


def _log_evals(
    tracker: Tracker, exp_id: str, samples: list[dict[str, Any]] = EVALS
) -> None:
    for sample in samples:
        tracker.log_eval_sample(
            sample["id"],
            sample["dataset_id"],
            sample["inputs"],
            outputs=sample["outputs"],
            references=sample["refs"],
            scores=sample["scores"],
            metadata=sample["metadata"],
            experiment_id=exp_id,
        )


def populate(tracker: Tracker, exp_id: str) -> dict[str, Any]:
    """Logs everything; returns what the era's API did with non-finite metric values."""
    for key, value in STATIC_PARAMS.items():
        tracker.log_static(key, value, experiment_id=exp_id)
    for key, points in metric_points().items():
        for step, value in points:
            tracker.log_dynamic(key, value, step=step, experiment_id=exp_id)
    non_finite_log = _log_non_finite_metric(tracker, exp_id)
    for name, content in ATTACHMENTS.items():
        tracker.log_attachment(name, content, experiment_id=exp_id)
    _log_spans(tracker, exp_id)
    _log_evals(tracker, exp_id)
    for dataset_id, eval_id, trace_id in EVAL_TRACE_LINKS:
        tracker.link_eval_sample_to_trace(
            dataset_id, eval_id, trace_id, experiment_id=exp_id
        )
    return {"non_finite_metric_logging": non_finite_log}


def populate_edge_cases(tracker: Tracker, exp_id: str) -> None:
    _log_spans(tracker, exp_id, EDGE_SPANS)
    _log_evals(tracker, exp_id, EDGE_EVALS)


def populate_annotations(tracker: Tracker, exp_id: str) -> None:
    for item in EVAL_ANNOTATIONS:
        tracker.log_eval_annotation(
            item["dataset_id"],
            item["eval_id"],
            item["name"],
            item["annotation_kind"],
            item["value_type"],
            item["value"],
            "fixture-user",
            rationale=item.get("rationale"),
            experiment_id=exp_id,
        )
    for item in SPAN_ANNOTATIONS:
        tracker.log_span_annotation(
            item["trace_id"],
            item["span_id"],
            item["name"],
            item["annotation_kind"],
            item["value_type"],
            item["value"],
            "fixture-user",
            rationale=item.get("rationale"),
            experiment_id=exp_id,
        )


def freeze_attachment_times(store_dir: str, exp_id: str) -> None:
    """Sets fixed times on the attachment sources so the SDK packs neutral mtimes."""
    attachments_dir = Path(store_dir) / "experiments" / exp_id / "attachments"
    paths = sorted(attachments_dir.rglob("*"), reverse=True) + [attachments_dir]
    for path in paths:
        os.utime(path, (FIXED_FILE_TIME, FIXED_FILE_TIME))


def write_generation_log(path: str, log: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(log, indent=2, ensure_ascii=False) + "\n")
