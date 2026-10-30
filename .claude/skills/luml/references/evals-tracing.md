# Flow SDK — evaluations and tracing

Needs `pip install "luml_sdk[tracing]"` (plus `openai` and
`opentelemetry-instrumentation-openai` for LLM work).

## Order of setup

Tracing must be wired **before** the client being traced is used, and the
experiment must exist before spans are logged:

```python
tracker = ExperimentTracker()
tracker.enable_tracing()      # OTel provider + exporter that writes spans to the tracker
instrument_openai()           # patches the OpenAI client
tracker.start_experiment(name="my_eval")
```

`enable_tracing()` is the one-call form of
`from luml.experiments.tracing import setup_tracing, set_experiment_tracker`.
Every span then lands on the experiment that is current when it closes.

## Running an evaluation

```python
from luml.experiments.evaluation import EvalItem
from luml.experiments.evaluation.evaluate import evaluate

results = evaluate(
    eval_dataset=[EvalItem(...), ...],
    inference_fn=lambda inputs: ...,   # receives EvalItem.inputs, returns the output
    scorers=[...],
    dataset_id="simple_qa_v1",
    experiment_tracker=tracker,
    n_threads=1,                       # >1 runs cases in a thread pool
)
results.aggregated_scores   # {score_name: mean}
results.results             # list[EvalResult]: eval_item, model_response, scores, trace_id
```

`evaluate` logs every case as an eval sample on the active experiment and links
it to the trace of its inference call — no manual `log_eval_sample` needed.

`EvalItem(id, inputs: dict, expected_output=None, metadata: dict = {})`.
`inputs` is a free-form dict; `inference_fn` and the scorers agree on its keys.

## Scorers

Function scorers — the common case:

```python
from luml.experiments.evaluation import supervised_scorer, unsupervised_scorer

@supervised_scorer            # needs EvalItem.expected_output
def exact_match(inputs, expected_output, output):
    return expected_output == output

@unsupervised_scorer          # no reference answer
def is_non_empty(inputs, output):
    return bool(output and str(output).strip())
```

A scorer returns `bool | float | int`, or a **dict** to emit several named scores
at once. The scorer's name is the function name; duplicates are disambiguated
automatically. A supervised scorer on an item without `expected_output` raises
`ValueError`.

Class scorers: subclass `SupervisedScorer` / `UnsupervisedScorer` and implement
`score(...)` plus `get_name()`.

### Built-in LLM-judge scorers

```python
from luml.experiments.evaluation import (
    Correctness,      # supervised: factual correctness vs expected facts
    Relevancy,        # unsupervised: response relevant to the question
    Completeness,     # unsupervised: response covers the question
    Summarization,    # unsupervised: summary quality against the source text
    PromptAlignment,  # unsupervised: response follows the instructions
)

scorer = Relevancy()                    # default judge: OpenAIClient, gpt-4.1-mini
scorer = Relevancy(input_key="prompt")  # when the input key is not the default
scorer = Correctness(client=my_llm_client, name="factuality")
```

All five take `(client=None, input_key=None, name=None)` and return a float in
0.0–1.0 plus a `<name>_reasoning` field. Each reads one key out of `inputs`:
`Correctness` → `request`/`question`, `Relevancy` and `Completeness` →
`question`/`query`, `Summarization` and `PromptAlignment` → their own defaults.
When the dataset uses a different key, pass `input_key`.

`Correctness` accepts `expected_output` as a string or as
`{"expected_facts": [...]}`.

The judge must return JSON with a numeric `score`; the SDK retries once with a
corrective reminder and then raises `JudgeModelError`.

Custom judge: any object with `complete(system_prompt, user_prompt) -> str`
satisfies the `LLMClient` protocol.

```python
from luml.llm import OpenAIClient
client = OpenAIClient(model="gpt-4.1-mini", temperature=0.0,
                      base_url="http://localhost:8080/v1")   # any OpenAI-compatible endpoint
```

## Logging eval samples manually

For evaluations not run through `evaluate()`:

```python
tracker.log_eval_sample(
    eval_id="sample_001",
    dataset_id="test_set_v2",
    inputs={"prompt": "..."},
    outputs={"response": "..."},
    references={"expected": "..."},
    scores={"bleu": 0.72},
    metadata={"latency_ms": 412},
)
tracker.link_eval_sample_to_trace(eval_dataset_id, eval_id, trace_id)
```

## Reading evals and traces back

```python
get_experiment_evals(experiment_id, limit=20, cursor_str=None, sort_by="created_at",
                     order="desc", dataset_id=None, json_sort_column=None,
                     search=None, filters=None) -> PaginatedResponse[EvalRecord]
get_experiment_evals_all(...)                # no pagination
get_experiment_evals_average_scores(experiment_id, dataset_id=None, ...) -> dict[str, float]
get_experiment_eval_dataset_ids(experiment_id) -> list[str]
get_eval(experiment_id, eval_id) -> EvalRecord | None

get_experiment_traces(experiment_id, limit=20, cursor_str=None,
                      sort_by="execution_time", order="desc",
                      search=None, filters=None, states=None) -> PaginatedResponse[TraceRecord]
get_experiment_traces_all(...)
get_trace(experiment_id, trace_id) -> TraceDetails | None
```

Column helpers (`get_experiment_eval_columns`, `get_experiment_trace_columns`
and their `*_typed_*` variants) list the keys available for sorting and
filtering — call them before passing `json_sort_column` or `filters`.
`validate_evals_filter` / `validate_traces_filter` check a filter string before use.

## Annotations

Human or agent review attached to an eval sample or a span:

```python
log_eval_annotation(dataset_id, eval_id, name, annotation_kind, value_type,
                    value, user, rationale=None, experiment_id=None) -> AnnotationRecord
log_span_annotation(...)
get_eval_annotations(...) / get_span_annotations(...)
update_annotation(...) / delete_annotation(...)
get_eval_annotation_summary(...) / get_trace_annotation_summary(...)
```

## Raw spans

`log_span(trace_id, span_id, name, start_time_unix_nano, end_time_unix_nano,
parent_span_id=None, kind=0, status_code=0, status_message=None,
attributes=None, events=None, links=None, trace_flags=0, experiment_id=None)`
is the exporter's own sink. Prefer `enable_tracing()` and OTel instrumentation;
call this only when bridging a tracing system LUML does not instrument.

Source of truth: `sdk/python/sdk/luml/experiments/evaluation/`,
`sdk/python/sdk/luml/experiments/tracing/`, examples in `sdk/python/sdk/examples/`.
