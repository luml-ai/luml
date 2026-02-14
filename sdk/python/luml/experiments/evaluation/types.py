from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalItem:
    id: str
    inputs: dict[str, Any]
    expected_output: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalResult:
    eval_item: EvalItem
    model_response: Any
    scores: dict[str, bool | float | int | str]
    trace_id: str


@dataclass
class EvalResults:
    results: list[EvalResult]
    aggregated_scores: dict[str, float | int]
    dataset_id: str

