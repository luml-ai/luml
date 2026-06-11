# Built-in Scorers

The LUML SDK ships with five LLM-as-judge scorers that evaluate common quality dimensions out of the box. Each scorer sends the model output (and optionally the input and expected output) to a judge LLM, which reasons about quality and returns a score between 0.0 and 1.0. The judge's short rationale is captured in the eval sample **metadata**, while the numeric score flows into the **scores/metrics** column.

## Available Scorers

| Scorer | Type | What it measures |
|---|---|---|
| `Relevancy` | Unsupervised | Is the output relevant to the input question? |
| `Correctness` | Supervised | Is the output factually correct given expected facts? |
| `Summarization` | Unsupervised | Does the summary accurately capture the source text? |
| `PromptAlignment` | Unsupervised | Does the output follow the given instructions? |
| `Completeness` | Unsupervised | Has the model fully answered the question / completed the task? |

**Supervised** scorers require `expected_output` on each `EvalItem`. **Unsupervised** scorers only need `inputs` and the model output.

## Import Paths

```python
from luml.experiments.evaluation.scorers.builtin import (
    Relevancy,
    Correctness,
    Summarization,
    PromptAlignment,
    Completeness,
)
```

## Zero-Config Default Judge

Every built-in scorer works with zero configuration. When no `client` is provided, the scorer creates a default `OpenAIClient` that uses:

- **Model:** `gpt-4.1-mini`
- **Temperature:** `0.0`
- **Response format:** JSON mode

The `OPENAI_API_KEY` environment variable must be set.

```python
scorer = Relevancy()  # uses default gpt-4.1-mini judge
```

## Configuring a Custom Judge

To use a different model, temperature, or endpoint, construct an `OpenAIClient` and pass it to the scorer:

```python
from luml.llm import OpenAIClient

client = OpenAIClient(model="gpt-4.1", temperature=0.2)
scorer = Relevancy(client=client)
```

For a self-hosted or third-party OpenAI-compatible endpoint:

```python
client = OpenAIClient(
    model="my-model",
    base_url="http://localhost:8080/v1",
    api_key="my-key",
)
scorer = Relevancy(client=client)
```

### Using a Fully Custom LLMClient

Any object that satisfies the `LLMClient` protocol works:

```python
from luml.llm import LLMClient

class MyClient:
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        # call your LLM here and return the raw text response
        ...

scorer = Relevancy(client=MyClient())
```

## The `input_key` Option

Each scorer has default keys it looks for in `inputs` (e.g. Relevancy looks for `"question"` then `"query"`). If your dataset uses different field names, override with `input_key`:

```python
scorer = Relevancy(input_key="prompt")
scorer = Summarization(input_key="document")
scorer = PromptAlignment(input_key="system_prompt")
```

You can also pass a tuple for an ordered fallback chain:

```python
scorer = Relevancy(input_key=("user_query", "prompt"))
```

## Score vs. Reasoning (Metadata) Split

Each scorer returns two values internally:

- `<scorer_name>` — the numeric score (0.0–1.0), logged as an eval metric
- `<scorer_name>_reasoning` — the judge's rationale, routed to the eval sample metadata

The evaluation table's scores/metrics column stays purely numeric. The reasoning is available per-sample in metadata for debugging.

## Complete Example

```python
from luml.experiments.tracker import ExperimentTracker
from luml.experiments.evaluation.evaluate import evaluate
from luml.experiments.evaluation.types import EvalItem
from luml.experiments.evaluation.scorers.builtin import (
    Relevancy,
    Correctness,
    Completeness,
)

eval_dataset = [
    EvalItem(
        id="sample_0",
        inputs={"question": "What is the capital of France?"},
        expected_output="Paris is the capital of France.",
        metadata={"category": "geography"},
    ),
    EvalItem(
        id="sample_1",
        inputs={"question": "Explain photosynthesis in one sentence."},
        expected_output=(
            "Photosynthesis is the process by which plants use sunlight, "
            "water, and CO2 to produce glucose and oxygen."
        ),
        metadata={"category": "biology"},
    ),
]


def run_model(inputs: dict) -> str:
    # your inference function here
    return "Paris is the capital of France."


tracker = ExperimentTracker("sqlite://./eval_experiments")
tracker.enable_tracing()

exp_id = tracker.start_experiment(
    name="builtin_scorers_demo",
    group="demo",
    tags=["builtin-scorers", "evals"],
)
try:
    eval_results = evaluate(
        eval_dataset=eval_dataset,
        inference_fn=run_model,
        scorers=[Relevancy(), Correctness(), Completeness()],
        dataset_id="demo_v1",
        experiment_tracker=tracker,
    )

    for key, value in eval_results.aggregated_scores.items():
        tracker.log_static(f"eval_{key}", value)
finally:
    tracker.end_experiment(exp_id)
```

After running, launch LUMLFlow to inspect per-sample scores and reasoning:

```bash
lumlflow ui --path sqlite://./eval_experiments
```
