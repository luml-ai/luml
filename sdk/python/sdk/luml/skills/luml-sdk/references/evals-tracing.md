# Evals and traces

For LLM chains and agents, evals and traces are the record of how the model
behaves, the way metrics are for ML models. Install `luml_sdk[tracing]`, and
`luml_sdk[llm]` for the built-in LLM-judge scorers.

## Set up tracing first

```python
from luml.experiments.tracker import ExperimentTracker
from luml.experiments.tracing import instrument_openai

tracker = ExperimentTracker()
tracker.enable_tracing()   # spans go to this tracker's current experiment
instrument_openai()        # records every OpenAI call as a span
tracker.start_experiment(name="support-bot-eval", group="support-bot")
```

Call `enable_tracing()` before the traced code runs. A span is stored in the
experiment that is current when the span ends.

Trace your own steps with OpenTelemetry:

```python
from opentelemetry import trace

tracer = trace.get_tracer("support-bot")

def answer(question: str) -> str:
    with tracer.start_as_current_span("retrieve") as span:
        documents = retrieve(question)
        span.set_attribute("documents.count", len(documents))
    with tracer.start_as_current_span("generate"):
        return generate(question, documents)
```

## Run an evaluation

```python
from luml.experiments.evaluation import EvalItem, supervised_scorer, unsupervised_scorer
from luml.experiments.evaluation.evaluate import evaluate


@supervised_scorer
def exact_match(inputs: dict, expected_output: str, output: str) -> bool:
    return expected_output.strip().lower() == output.strip().lower()


@unsupervised_scorer
def is_short(inputs: dict, output: str) -> bool:
    return len(output) < 400


items = [
    EvalItem(id="q1", inputs={"question": "Capital of France?"}, expected_output="Paris"),
    EvalItem(id="q2", inputs={"question": "2 + 2?"}, expected_output="4"),
]
results = evaluate(
    eval_dataset=items,
    inference_fn=lambda inputs: answer(inputs["question"]),
    scorers=[exact_match, is_short],
    dataset_id="smoke-v1",
    experiment_tracker=tracker,
    n_threads=1,
)
print(results.aggregated_scores)
```

- Each item becomes an eval sample linked to its trace. Do not log them again.
- `dataset_id` names the eval set. Keep it stable across experiments so they
  compare.
- When `inference_fn` raises, the result holds `{"error": ...}` and no sample is
  logged. Check `results.results` for errors before you report scores.
- A scorer returns a bool, an int, a float, or a dict of several named scores.
  A failing scorer is skipped with a warning.

## Built-in LLM-judge scorers

```python
from luml.experiments.evaluation import (
    Completeness,     # unsupervised: covers the question
    Correctness,      # supervised: factually matches the expected output
    PromptAlignment,  # unsupervised: follows the instructions
    Relevancy,        # unsupervised: relevant to the question
    Summarization,    # unsupervised: summary quality against the source
)
from luml.llm import OpenAIClient

judge = OpenAIClient(model="gpt-4.1-mini", temperature=0.0)
scorers = [Correctness(client=judge), Relevancy(client=judge, input_key="question")]
```

Each takes `client`, `input_key` (which key of `inputs` holds the question or
text) and `name`. Each returns a score from 0 to 1 and a `<name>_reasoning`
text, which is stored in the sample's metadata. Any object with
`complete(system_prompt, user_prompt) -> str` works as a client.

## Log samples yourself

When evals do not run through `evaluate()`, for example scores from an
external tool:

```python
tracker.log_eval_sample(
    eval_id="q1",
    dataset_id="smoke-v1",
    inputs={"question": "Capital of France?"},
    outputs={"response": "Paris"},
    references={"expected": "Paris"},
    scores={"exact_match": True, "rubric_clarity": 4},
    metadata={"latency_ms": 412},
)
tracker.link_eval_sample_to_trace("smoke-v1", "q1", trace_id)
```

Per-sample and per-rubric scores belong here, never in `log_dynamic`.
Aggregates over the whole set can also go in `log_static`.

## Annotations

Human or agent review of a sample or a span:

```python
tracker.log_eval_annotation(
    dataset_id="smoke-v1",
    eval_id="q1",
    name="correct",
    annotation_kind="feedback",   # "feedback" (value_type "bool") or "expectation"
    value_type="bool",            # "bool", "int" or "string"
    value=True,
    user="reviewer",
    rationale="Matches the source.",
)
```

`log_span_annotation(...)` does the same for a span.

## Reading back

```python
tracker.get_experiment_evals_all(experiment_id)
tracker.get_experiment_evals_average_scores(experiment_id, dataset_id="smoke-v1")
tracker.get_experiment_traces_all(experiment_id)
tracker.get_trace(experiment_id, trace_id)
```

## Packaging the chain

A LangGraph app is saved with `save_langgraph`. Any other chain or agent is a
custom `PyFunc` ([packaging.md](packaging.md)). Declare API keys as runtime
secrets; never put them in the artifact.
