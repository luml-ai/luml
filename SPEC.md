# Proposals

## Problem

The LUML SDK has a working scorer system (`sdk/python/sdk/luml/experiments/evaluation/`) that lets users define custom scorers as Python functions (`@supervised_scorer` / `@unsupervised_scorer`) and run evaluations. However, the SDK only supports user-defined scorers — there are no built-in, ready-to-use scorers for common LLM evaluation tasks like relevancy, correctness, or summarization quality. Users must implement these from scratch every time.

## Proposed Solution

Add a set of **built-in LLM-as-judge scorers** to the SDK that users can import and use alongside their custom scorers in `evaluate()` calls. These scorers use an LLM (default: `gpt-4.1-mini`) to evaluate model outputs on common quality dimensions:

**General scorers:**
- **Relevancy** — is the output relevant to the input query?
- **Correctness** — is the output factually correct given expected facts? (includes faithfulness & hallucination detection)
- **Summarization** — does the summary accurately capture the source text?

**Agentic scorers:**
- **Prompt Alignment** — does the output follow the given instructions?
- **Completeness** — has the model fully answered the question / completed the task?

Each scorer asks the judge LLM to **reason first, then assign a score**. The scorer produces:
- a numeric score (`float` 0.0–1.0) under the scorer's name — logged as an eval metric and aggregated, and
- the judge's short rationale — routed to the eval sample's **metadata** (not the scores/metrics) for debuggability.

Both flow through the existing `ExperimentTracker` into the evaluation table; the scores/metrics column stays purely numeric.

## Why This Approach

- **SDK-first** — scorers run locally in the user's environment, no platform backend changes needed. This is the fastest path to value.
- **Extends existing abstractions** — built-in scorers are regular `BaseScorer` subclasses, fully compatible with the existing `evaluate()` function, `EvalResult.scores` dict, and aggregation logic.
- **LLM-agnostic** — the SDK defines a general-purpose `LLMClient` protocol (`luml.llm`) that any LLM-based feature can use. The SDK ships an `OpenAIClient` as the default, but users can plug in any LLM provider (Anthropic, Ollama, HuggingFace, etc.) by implementing a single `complete()` method. Built-in scorers accept this generic client; judge-specific logic (JSON parsing, score extraction) lives in the scorer layer. Users who stick with the default only need `openai` as an optional install (`luml_sdk[llm]`).
- **Reproducible by default** — the default `OpenAIClient` runs the judge at `temperature=0.0`, so scores are stable run-to-run. Temperature, `max_tokens`, and `max_retries` are configurable.
- **Robust to noisy judges** — built-in scorers extract a continuous score with anchored rubrics in the prompt, perform one corrective retry on malformed JSON, and rely on the OpenAI SDK's built-in retries for transient API failures.
- **User-defined scorers unchanged** — `@supervised_scorer` and `@unsupervised_scorer` decorators continue to work as-is. Users can mix built-in and custom scorers freely.

## Non-Goals (Out of Scope)

The following are explicitly **not** part of this work and an implementer should not build them:

- **Async judging.** Built-in scorers use the synchronous `LLMClient.complete()` to stay compatible with `evaluate()`'s `ThreadPoolExecutor` parallelism. No `async`/`await` scorer path.
- **Token/cost tracking.** The scorer layer does not measure or report token usage or LLM cost for judge calls.
- **Deterministic (non-LLM) scorers.** Exact-match, regex, fuzzy/edit-distance, BLEU/ROUGE, embedding-similarity, and similar metrics are out of scope. This ticket ships only the five LLM-as-judge scorers.
- **Backend / UI / platform changes.** No changes to the LUML backend, frontend, schemas, or evaluation table rendering. Everything runs SDK-side and reuses the existing `ExperimentTracker` logging path.
- **Custom retry/backoff for transient API errors.** Transient failures are delegated to the OpenAI SDK's built-in retries (`max_retries`); the scorer layer adds only the single corrective retry for malformed JSON.
- **Provider SDKs other than OpenAI.** The SDK ships only `OpenAIClient`. Anthropic/HuggingFace/etc. are supported via the user-implemented `LLMClient` protocol, not bundled clients.

---

# Design

## Architecture Overview

The LLM client abstraction lives at the SDK top level so any feature can use it. Built-in scorers live in a subpackage under the existing scorers module.

```
sdk/python/sdk/luml/
├── llm/
│   ├── __init__.py      # Public exports: LLMClient, OpenAIClient, LLMError
│   ├── _client.py       # LLMClient protocol + OpenAIClient default implementation
│   └── _exceptions.py   # LLMError
├── experiments/
│   └── evaluation/
│       └── scorers/
│           ├── __init__.py          # (existing) re-exports base; ADD builtin re-exports (see Public API)
│           ├── base.py              # (existing) BaseScorer, UnsupervisedScorer, SupervisedScorer, decorators
│           └── builtin/
│               ├── __init__.py      # Public exports: Relevancy, Correctness, Summarization, PromptAlignment, Completeness
│               ├── _base.py         # LLMJudgeScorer + SupervisedLLMJudgeScorer + _call_judge/_init_client/_extract_input helpers
│               ├── _exceptions.py   # JudgeModelError (extends LLMError)
│               ├── _prompts.py      # Shared JSON-output instruction + corrective reminder constants
│               ├── relevancy.py     # Relevancy scorer
│               ├── correctness.py   # Correctness scorer
│               ├── summarization.py # Summarization scorer
│               ├── prompt_alignment.py  # PromptAlignment scorer
│               └── completeness.py  # Completeness scorer
```

## LLMClient Protocol and OpenAIClient (`luml.llm`)

The LLM client is an **SDK-wide** abstraction — a Protocol with a single `complete()` method. Any LLM-based feature (scorers, future prompt optimization, synthetic data, etc.) can accept an `LLMClient` and use it without knowing the provider.

```python
class LLMClient(Protocol):
    """Protocol for LLM clients. Any object with this method signature works."""
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Send a prompt to an LLM and return the raw text response."""
        ...
```

The SDK ships `OpenAIClient` as the default implementation:

```python
class OpenAIClient:
    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        api_key: str | None = None,       # defaults to OPENAI_API_KEY env var
        base_url: str | None = None,      # for Ollama, vLLM, Azure, etc.
        response_format: dict | None = None,  # e.g. {"type": "json_object"}
        temperature: float = 0.0,         # deterministic judging by default
        max_tokens: int | None = None,    # optional cap on completion length
        max_retries: int = 2,             # passed to openai.OpenAI for transient errors
    ) -> None: ...

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """
        Calls the OpenAI chat completions API and returns the response text.
        Raises LLMError on API failure.
        """
```

- Uses `openai.OpenAI` (sync client) to stay compatible with the existing `ThreadPoolExecutor`-based parallelism in `evaluate()`.
- `api_key` defaults to `None`, which makes the OpenAI client read from the `OPENAI_API_KEY` environment variable.
- `base_url` allows pointing at any OpenAI-compatible API (Ollama at `http://localhost:11434/v1`, vLLM, Azure OpenAI, LM Studio, etc.).
- `response_format` is optional — callers that need JSON output (like the scorer layer) pass `{"type": "json_object"}` at construction time.
- `temperature` defaults to `0.0` for reproducible judging; callers can raise it. It is always passed to the chat completions call.
- `max_tokens` is only forwarded to the API when not `None`.
- `max_retries` is forwarded to `openai.OpenAI(max_retries=...)`, so transient API errors (rate limit, timeout, network) are retried by the OpenAI SDK itself with exponential backoff. The scorer layer does **not** add its own retry for these.
- `openai` is imported lazily inside `OpenAIClient.__init__`, so users who provide their own client never need the `openai` package installed.
- `complete()` builds messages `[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]`, calls `chat.completions.create(...)`, and returns `response.choices[0].message.content` (coerced to `""` if `None`). Any exception from the OpenAI SDK is wrapped and re-raised as `LLMError`.

**`complete()` returns a raw `str`, not a parsed dict.** This keeps the protocol generic — it's the caller's job to parse the response. For scorers, `_call_judge` (below) handles JSON parsing and score validation internally.

### JSON output mode and provider caveats

- When the scorer layer constructs the default `OpenAIClient` it sets `response_format={"type": "json_object"}`. OpenAI requires the literal word "JSON" to appear in the prompt for this mode — this is satisfied by `JSON_OUTPUT_INSTRUCTION` (below), so **the JSON instruction must remain in every judge prompt**; an implementer must not strip it.
- `response_format={"type": "json_object"}` is **not supported by every OpenAI-compatible backend** (some Ollama/vLLM models reject or ignore it). This is a known limitation; the scorer's `_call_judge` corrective retry plus `JudgeModelError` handling cover the case where such a backend returns non-JSON, so a single eval item degrades to a logged `__error__<name>` rather than crashing the run. Users on backends without JSON mode can pass their own `LLMClient` and shape the output themselves.

### Tracing interaction

The default `OpenAIClient` constructs its own `openai.OpenAI()` instance. If the user has enabled OpenTelemetry tracing and called `instrument_openai()` (as in `examples/evals_example.py`), the judge's own OpenAI calls are auto-instrumented and will appear as child spans **nested under the existing `eval_scoring` span** created by `_evaluate_single_item`. This is intended and desirable (judge calls become visible in the trace); no extra instrumentation is added by the scorer layer.

## LLM Judge Base Classes (`_base.py`)

Two base classes for built-in scorers, sharing common LLM judge logic but with different `score()` signatures matching the existing `UnsupervisedScorer` / `SupervisedScorer` split. Because all five built-in judges share the same response contract (`{"reasoning": str, "score": float}`), the base classes provide a **concrete** `parse_judgment` and a **concrete** input-extraction helper; concrete scorers only implement `default_name` and `build_prompt`.

### Judge response contract

Every built-in judge prompt asks the LLM to return a JSON object with exactly two fields:

```json
{"reasoning": "<short explanation>", "score": 0.75}
```

`score` is a continuous float in `[0.0, 1.0]`, with qualitative anchors stated in each scorer's prompt:
- `0.0` = worst (fully fails the dimension)
- `0.5` = partial
- `1.0` = best (fully satisfies the dimension)

### Shared constants (`_prompts.py`)

```python
JSON_OUTPUT_INSTRUCTION = (
    "Respond ONLY with a JSON object containing exactly two fields: "
    '"reasoning" (a brief string explaining your judgment) and '
    '"score" (a number between 0.0 and 1.0). '
    'Example: {"reasoning": "...", "score": 0.7}'
)

CORRECTIVE_REMINDER = (
    "Your previous response was invalid. Respond ONLY with a JSON object "
    'with exactly two fields: "reasoning" (string) and "score" (a number '
    "between 0.0 and 1.0). Do not include any other text."
)
```

### Shared helper: `_call_judge`

Bridges the generic `LLMClient.complete() -> str` with the scorer's need for validated JSON. Performs **one corrective retry** when the response is not valid JSON or is missing a numeric `score`. Transient API errors raised by `complete()` are **not** retried here (the OpenAI SDK handles those) — they propagate as `LLMError`.

```python
def _try_parse(raw: str) -> dict[str, Any] | None:
    """Parse raw as JSON; return the dict only if it has a numeric 'score', else None."""
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(parsed, dict) and isinstance(parsed.get("score"), (int, float)) \
            and not isinstance(parsed.get("score"), bool):
        return parsed
    return None

def _call_judge(client: LLMClient, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Call the LLM, parse JSON, retry once on malformed/missing-score output.

    Raises JudgeModelError if the judge fails to produce valid JSON with a
    numeric 'score' after the corrective retry. LLMError from the client
    propagates unchanged.
    """
    raw = client.complete(system_prompt, user_prompt)
    parsed = _try_parse(raw)
    if parsed is not None:
        return parsed

    retry_prompt = f"{user_prompt}\n\n{CORRECTIVE_REMINDER}"
    raw = client.complete(system_prompt, retry_prompt)
    parsed = _try_parse(raw)
    if parsed is not None:
        return parsed

    raise JudgeModelError(
        f"Judge did not return valid JSON with a numeric 'score' "
        f"after one retry. Last response: {raw!r}"
    )
```

### Shared helper: `_init_client`

```python
def _init_client(
    client: LLMClient | None,
    model: str,
    api_key: str | None,
    base_url: str | None,
    temperature: float,
) -> LLMClient:
    """Return the provided client, or create a default OpenAIClient with JSON output."""
    return client or OpenAIClient(
        model=model, api_key=api_key, base_url=base_url,
        response_format={"type": "json_object"}, temperature=temperature,
    )
```

**Constructor priority:** If `client` is provided, `model`/`api_key`/`base_url`/`temperature` are ignored. If `client` is `None` (default), an `OpenAIClient` is created with `response_format={"type": "json_object"}` and the provided parameters.

### Shared helper: `_extract_input`

Resolves the relevant input string for a scorer, honoring a user-supplied `input_key` and falling back to a per-scorer chain of default keys, then to `str(inputs)`.

```python
def _extract_input(
    inputs: dict[str, Any],
    input_key: str | None,
    default_keys: tuple[str, ...],
) -> str:
    """Return the input text for the judge prompt.

    - If input_key is set and present in inputs, use inputs[input_key].
    - Else try each key in default_keys in order; use the first present.
    - Else fall back to str(inputs).
    Values are coerced to str.
    """
    if input_key is not None and input_key in inputs:
        return str(inputs[input_key])
    for key in default_keys:
        if key in inputs:
            return str(inputs[key])
    return str(inputs)
```

### Concrete `parse_judgment` (shared, in `_base.py`)

Both base classes implement `parse_judgment` once. `_call_judge` already guarantees a numeric `score`, so this clamps it and attaches the reasoning string under the `REASONING_SUFFIX` key:

```python
from luml.experiments.evaluation.types import REASONING_SUFFIX  # "_reasoning"

def parse_judgment(self, judgment: dict[str, Any]) -> dict[str, Any]:
    name = self.get_name()
    score = max(0.0, min(1.0, float(judgment["score"])))
    reasoning = str(judgment.get("reasoning", ""))
    return {name: score, f"{name}{REASONING_SUFFIX}": reasoning}
```

The scorer returns both entries in a single flat dict (the only channel `score()` has). `_evaluate_single_item` then separates the `REASONING_SUFFIX` entry into the eval sample metadata — see *Evaluate Integration*. Subclasses may override `parse_judgment` if they need extra fields, but the five built-ins do not.

### `LLMJudgeScorer` — for scorers that don't need ground truth

Extends `UnsupervisedScorer`. Used by: Relevancy, Summarization, PromptAlignment, Completeness.

```python
class LLMJudgeScorer(UnsupervisedScorer):
    """Base class for unsupervised LLM-as-judge scorers."""

    def __init__(
        self,
        client: LLMClient | None = None,
        model: str = "gpt-4.1-mini",
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.0,
        input_key: str | None = None,   # override default input key lookup
        name: str | None = None,        # override default scorer name
    ) -> None:
        self._client = _init_client(client, model, api_key, base_url, temperature)
        self._input_key = input_key
        self._name = name or self.default_name()

    @abstractmethod
    def default_name(self) -> str:
        """Return the default scorer name (e.g. 'relevancy')."""

    @abstractmethod
    def build_prompt(self, inputs: dict[str, Any], output: Any) -> tuple[str, str]:
        """Return (system_prompt, user_prompt) for the judge LLM."""

    # parse_judgment: concrete (see above)

    def score(self, inputs: dict[str, Any], output: Any) -> dict[str, Any]:
        system_prompt, user_prompt = self.build_prompt(inputs, output)
        judgment = _call_judge(self._client, system_prompt, user_prompt)
        return self.parse_judgment(judgment)

    def get_name(self) -> str:
        return self._name
```

### `SupervisedLLMJudgeScorer` — for scorers that need ground truth

Extends `SupervisedScorer`. Used by: Correctness. Same `__init__`, `default_name`, concrete `parse_judgment`, `get_name`; the only difference is `build_prompt` / `score` carry `expected_output`.

```python
class SupervisedLLMJudgeScorer(SupervisedScorer):
    def __init__(self, client=None, model="gpt-4.1-mini", api_key=None,
                 base_url=None, temperature=0.0, input_key=None, name=None) -> None:
        self._client = _init_client(client, model, api_key, base_url, temperature)
        self._input_key = input_key
        self._name = name or self.default_name()

    @abstractmethod
    def default_name(self) -> str: ...

    @abstractmethod
    def build_prompt(self, inputs: dict[str, Any], expected_output: Any, output: Any) -> tuple[str, str]: ...

    def score(self, inputs: dict[str, Any], expected_output: Any, output: Any) -> dict[str, Any]:
        system_prompt, user_prompt = self.build_prompt(inputs, expected_output, output)
        judgment = _call_judge(self._client, system_prompt, user_prompt)
        return self.parse_judgment(judgment)

    def get_name(self) -> str:
        return self._name
```

**Why two base classes?** Correctness naturally *is* a supervised scorer — it requires ground truth (`expected_output`). Making it extend `SupervisedScorer` means `_call_scorer()` routes it correctly via the existing `isinstance` check, passing `eval_item.expected_output` directly. No changes to `_call_scorer` or `evaluate()` are needed. The other four scorers only need `inputs` and `output`, so they extend `UnsupervisedScorer` via `LLMJudgeScorer`.

## Individual Scorer Specifications

Each scorer below defines `default_name`, the `default_keys` it reads from `inputs`, and the exact system/user prompts. `parse_judgment` is inherited (returns `{name: score, f"{name}_reasoning": reasoning}`). `output` is coerced with `str(output)` when interpolated into the user prompt.

### Score Output Format

Each built-in scorer's `score()` returns two entries:

```python
{
    "<scorer_name>": 0.85,                # float 0.0–1.0
    "<scorer_name>_reasoning": "...",     # str rationale
}
```

`_evaluate_single_item` routes the `_reasoning` entry into the eval sample **metadata** and keeps only the numeric `<scorer_name>` score as an eval metric (see *Evaluate Integration*). So the evaluation table's scores/metrics stay numeric, while the rationale is available in the sample metadata. Aggregation (`_aggregate_scores`) only ever sees numeric metrics.

### Relevancy

- **Name:** `relevancy` · **Type:** unsupervised (`LLMJudgeScorer`)
- **Default input keys:** `("question", "query")`
- **System prompt:**
  > You are an impartial evaluator. Assess how relevant a response is to a given question. Score on a continuous scale from 0.0 to 1.0 where 0.0 means the response is completely irrelevant, 0.5 means it is partially relevant but misses key aspects or includes irrelevant content, and 1.0 means it is fully relevant and directly addresses the question. First reason about the relevance, then assign a score. {JSON_OUTPUT_INSTRUCTION}
- **User prompt:** `f"Question:\n{question}\n\nResponse:\n{output}"`

### Correctness

- **Name:** `correctness` · **Type:** supervised (`SupervisedLLMJudgeScorer`)
- **Default input keys:** `("request", "question")`
- **`expected_output` handling:** if it is a dict containing `expected_facts` (a list), join the facts into a bulleted block; otherwise use `str(expected_output)`.
- **System prompt:**
  > You are an impartial evaluator assessing the factual correctness of a response against a set of expected facts / reference answer. Check faithfulness (are the stated facts correct and supported by the expected facts?) and hallucination (does the response fabricate information not supported by the expected facts?). Score from 0.0 to 1.0 where 0.0 means the response is factually incorrect, contradicts the expected facts, or hallucinates; 0.5 means it is partially correct (some expected facts covered, others missing or wrong); and 1.0 means it is fully correct and faithful to all expected facts with no hallucinations. First reason, then assign a score. {JSON_OUTPUT_INSTRUCTION}
- **User prompt:** `f"Request:\n{request}\n\nExpected facts / reference:\n{expected_str}\n\nResponse:\n{output}"`

### Summarization

- **Name:** `summarization` · **Type:** unsupervised (`LLMJudgeScorer`)
- **Default input keys:** `("text",)`
- **System prompt:**
  > You evaluate the quality of a summary against its source text. A good summary accurately captures the key information from the source without adding false or unsupported information (no hallucination) and without omitting essential points. Score from 0.0 to 1.0 where 0.0 means the summary is inaccurate, misleading, or fabricates information; 0.5 means it is accurate but misses important information or contains minor inaccuracies; and 1.0 means it accurately and concisely captures all key information from the source. First reason, then assign a score. {JSON_OUTPUT_INSTRUCTION}
- **User prompt:** `f"Source text:\n{text}\n\nSummary:\n{output}"`

### Prompt Alignment

- **Name:** `prompt_alignment` · **Type:** unsupervised (`LLMJudgeScorer`)
- **Default input keys:** `("instructions",)`
- **System prompt:**
  > You evaluate whether a response follows the given instructions. Consider all constraints in the instructions (format, length, style, and content requirements). Score from 0.0 to 1.0 where 0.0 means the response ignores or violates the instructions, 0.5 means it follows some instructions but violates others, and 1.0 means it fully follows all instructions. First reason, then assign a score. {JSON_OUTPUT_INSTRUCTION}
- **User prompt:** `f"Instructions:\n{instructions}\n\nResponse:\n{output}"`

### Completeness

- **Name:** `completeness` · **Type:** unsupervised (`LLMJudgeScorer`)
- **Default input keys:** `("question", "task")`
- **System prompt:**
  > You evaluate whether a response fully and completely addresses all parts of a question or task. Score from 0.0 to 1.0 where 0.0 means the response does not address the question/task, 0.5 means it addresses some parts but leaves important parts unanswered, and 1.0 means it fully and completely addresses all parts. First reason, then assign a score. {JSON_OUTPUT_INSTRUCTION}
- **User prompt:** `f"Question / task:\n{question}\n\nResponse:\n{output}"`

## Evaluate Integration

`_call_scorer()` is **unchanged**. One small, well-defined change is made to `_evaluate_single_item()` to route judge reasoning out of the metrics and into the eval sample metadata.

What stays the same:

1. `_call_scorer` checks `isinstance(scorer, SupervisedScorer)` first — Correctness matches this branch and receives `(inputs, expected_output, output)`.
2. The remaining built-in scorers are `UnsupervisedScorer` instances — they match the `elif` branch and receive `(inputs, output)`.
3. All built-in scorers return `dict[str, Any]` (e.g. `{"relevancy": 0.85, "relevancy_reasoning": "..."}`), which `_call_scorer` passes through and `_evaluate_single_item` merges into `all_scores` exactly as today.
4. Errors from LLM judge calls (`JudgeModelError`, `LLMError`) are caught by the existing `except Exception` block and logged as `__error__<scorer_name>` in the scores dict.

The change — reasoning routing. Define a shared constant in `evaluation/types.py`:

```python
REASONING_SUFFIX = "_reasoning"
```

In `_evaluate_single_item`, after the scoring loop assembles `all_scores` and before logging / building the `EvalResult`, split out the reasoning entries:

```python
metric_scores: dict[str, Any] = {}
reasoning_metadata: dict[str, Any] = {}
for key, value in all_scores.items():
    if key.endswith(REASONING_SUFFIX):
        reasoning_metadata[key] = value
    else:
        metric_scores[key] = value
```

Then:
- `experiment_tracker.log_eval_sample(..., scores=metric_scores, metadata={**eval_item.metadata, **reasoning_metadata})`
- `EvalResult(..., scores=metric_scores, ...)` (the returned/aggregated scores never contain reasoning)

Consequences:
- `_aggregate_scores` operates on `metric_scores` only — it never sees reasoning strings (no change to `_aggregate_scores` itself).
- Error keys (`error`, `__error__<name>`) do not end with `REASONING_SUFFIX`, so they stay in `metric_scores` as before, preserving the existing `successful_items` count (`"error" not in r.scores`).
- The span-attribute loop already filters to numeric values, so reasoning strings are naturally skipped there.
- A custom scorer that happens to emit a key ending in `_reasoning` will have that entry routed to metadata too — this is the documented contract for the metrics-vs-metadata split.

## Optional Dependency

`openai` is added as an optional dependency in `pyproject.toml`, only needed when using the default `OpenAIClient`:

```toml
[project.optional-dependencies]
llm = [
    "openai>=1.0.0,<3.0.0",
]
```

`openai` is imported lazily inside `OpenAIClient.__init__`. If a user passes their own `client` to a scorer (or any other LLM feature), `openai` is never imported and doesn't need to be installed. If no `client` is passed and `openai` is missing, the error is clear:

```
ImportError: The default OpenAI client requires the 'openai' package. Install with: pip install luml_sdk[llm]
  Or pass a custom client: Relevancy(client=MyCustomClient())
```

## Error Handling

Two layers of errors:

- **LLM-level errors** (`LLMError`): Raised by `LLMClient` implementations for API failures (auth, network, timeouts, and rate limits that survive the OpenAI SDK's own retries). Defined in `luml.llm`. Custom client implementations should raise `LLMError` for consistency, though any exception will be caught by the scorer layer.
- **Judge-level errors** (`JudgeModelError`): Raised by `_call_judge` when the LLM response can't be parsed as JSON or is missing a numeric `score`, after one corrective retry. `JudgeModelError` extends `LLMError`.

Both are caught by the existing `except Exception` block in `_call_scorer` → `_evaluate_single_item`, which logs them as `__error__<scorer_name>` in the scores dict. Evaluation continues for other items and other scorers.

- **Transient API errors** (rate limit, timeout, network) are retried by the OpenAI SDK (`max_retries`, default 2). The scorer layer does not add its own retry for these.
- **Missing input keys** are handled gracefully: `_extract_input` falls back through the default key chain and finally to `str(inputs)`, so a missing key never raises — the judge simply evaluates with whatever context is available.

## Public API / Exports

The LLM client abstraction is imported from the top-level `luml.llm` module:

```python
from luml.llm import (
    LLMClient,        # Protocol — for type hints when implementing custom clients
    OpenAIClient,     # Default implementation
    LLMError,         # Base error for LLM failures
)
```

Built-in scorers are defined in `luml.experiments.evaluation.scorers.builtin` and re-exported up the package chain for discoverability. **All three import paths below must work and resolve to the same classes:**

```python
# Canonical location
from luml.experiments.evaluation.scorers.builtin import (
    Relevancy, Correctness, Summarization, PromptAlignment, Completeness,
)
# Re-export from the scorers package
from luml.experiments.evaluation.scorers import (
    Relevancy, Correctness, Summarization, PromptAlignment, Completeness,
)
# Re-export from the evaluation package, alongside BaseScorer / EvalItem / etc.
from luml.experiments.evaluation import (
    Relevancy, Correctness, Summarization, PromptAlignment, Completeness,
)
```

**Export wiring:** `builtin/__init__.py` exports the five classes; `scorers/__init__.py` re-exports them from `builtin` and adds them to its `__all__`; `evaluation/__init__.py` re-exports them from `scorers` and adds them to its `__all__` (joining the existing `BaseScorer`, `EvalItem`, `EvalResult`, decorators, etc.).

Usage examples:

```python
from luml.experiments.evaluation import evaluate
from luml.experiments.evaluation.types import EvalItem
from luml.experiments.evaluation.scorers.builtin import Relevancy, Correctness

# Default: OpenAI with gpt-4.1-mini, temperature=0
results = evaluate(
    eval_dataset=[
        EvalItem(
            id="1",
            inputs={"question": "What is retrieval-augmented generation?"},
            expected_output={"expected_facts": ["RAG combines retrieval with generation", "RAG reduces hallucinations"]},
        ),
    ],
    inference_fn=my_model,
    scorers=[Relevancy(), Correctness(model="gpt-4.1")],
    dataset_id="v1",
    experiment_tracker=tracker,
)

# Non-standard input key
scorers = [Relevancy(input_key="prompt")]

# Ollama via base_url (uses OpenAI-compatible API)
scorers = [Relevancy(model="llama3", base_url="http://localhost:11434/v1")]

# Fully custom provider (no openai package needed)
class MyAnthropicClient:
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        ...
        return '{"reasoning": "...", "score": 0.85}'  # raw string — scorer parses JSON

scorers = [Relevancy(client=MyAnthropicClient())]

# Same client instance shared across multiple scorers
client = MyAnthropicClient()
scorers = [Relevancy(client=client), Correctness(client=client)]
```

---

# Scenarios

## Happy Paths

### Scenario: Relevancy scorer with valid inputs
**Given** a user has `openai` installed and `OPENAI_API_KEY` set
**When** they run `evaluate()` with `Relevancy()` and `EvalItem(inputs={"question": "What is retrieval-augmented generation?"})`, and the inference function returns `"RAG combines document retrieval with text generation to produce grounded responses."`
**Then** the eval sample's `scores` contains `{"relevancy": <float 0.0–1.0>}` and its `metadata` contains `{"relevancy_reasoning": <str>}`

### Scenario: Correctness scorer with expected_output
**Given** a user runs `evaluate()` with `Correctness()` and `EvalItem(inputs={"request": "What is retrieval-augmented generation?"}, expected_output={"expected_facts": ["RAG combines retrieval with generation", "RAG reduces hallucinations"]})`
**When** the inference function returns `"RAG combines document retrieval with text generation, helping reduce hallucinations."`
**Then** the eval sample's `scores` contains `{"correctness": <float>}` (high, both facts covered) and its `metadata` contains `{"correctness_reasoning": <str>}`

### Scenario: Correctness with plain-string expected_output
**Given** `EvalItem(inputs={"request": "Capital of the Netherlands?"}, expected_output="Amsterdam")`
**When** `Correctness().build_prompt` runs
**Then** `expected_str` is `"Amsterdam"` (no `expected_facts` key, so `str(expected_output)` is used) and the judge call proceeds normally

### Scenario: Summarization scorer
**Given** `Summarization()` and `EvalItem(inputs={"text": "<long source text about RAG>"})`
**When** the inference function returns `"RAG improves LLM accuracy."`
**Then** `scores` contains `{"summarization": <float>}` (accurate but incomplete) and `metadata` contains `{"summarization_reasoning": <str>}`

### Scenario: Prompt alignment scorer
**Given** `PromptAlignment()` and `EvalItem(inputs={"instructions": "Respond in bullet points. Keep it under 50 words."})`
**When** the inference function returns a 200-word paragraph
**Then** `scores` contains `{"prompt_alignment": <low float>}` and `metadata` contains `{"prompt_alignment_reasoning": <str>}`

### Scenario: Completeness scorer
**Given** `Completeness()` and `EvalItem(inputs={"question": "What is RAG and what are its main benefits?"})`
**When** the inference function returns `"RAG is a retrieval technique."`
**Then** `scores` contains `{"completeness": <low float>}` and `metadata` contains `{"completeness_reasoning": <str>}`

### Scenario: Reasoning routed to metadata, not scores
**Given** the judge returns `{"reasoning": "The response directly answers the question.", "score": 0.9}`
**When** `Relevancy.parse_judgment` runs and `_evaluate_single_item` splits the result
**Then** `parse_judgment` returns `{"relevancy": 0.9, "relevancy_reasoning": "The response directly answers the question."}`, and after routing the eval sample's `scores` is `{"relevancy": 0.9}` while its `metadata` includes `{"relevancy_reasoning": "The response directly answers the question."}`

### Scenario: Mixed built-in and custom scorers
**Given** a custom scorer `@unsupervised_scorer def is_short(inputs, output): return len(str(output)) < 100`
**When** the user runs `evaluate()` with `scorers=[Relevancy(), is_short]`
**Then** the eval sample's `scores` contains `{"relevancy": <float>, "is_short": True}`, its `metadata` contains `{"relevancy_reasoning": <str>}`, and aggregation works for the numeric/boolean values

### Scenario: Custom model override
**Given** `Relevancy(model="gpt-4.1")`
**When** the scorer runs
**Then** the judge LLM call uses `gpt-4.1` instead of the default `gpt-4.1-mini`

### Scenario: Temperature override
**Given** `Relevancy(temperature=0.7)`
**When** the default `OpenAIClient` is created and `complete()` runs
**Then** the chat completions call is made with `temperature=0.7` (default is `0.0`)

### Scenario: Custom input key
**Given** `Relevancy(input_key="prompt")` and `EvalItem(inputs={"prompt": "What is RAG?"})`
**When** `build_prompt` runs
**Then** `_extract_input` returns the value of `inputs["prompt"]` and the judge evaluates against it

### Scenario: Custom API key
**Given** `Relevancy(api_key="sk-my-custom-key")`
**When** the scorer runs
**Then** the OpenAI client uses the provided key instead of the `OPENAI_API_KEY` env var

### Scenario: Ollama via base_url
**Given** Ollama running locally with `llama3`
**When** the user creates `Relevancy(model="llama3", base_url="http://localhost:11434/v1")`
**Then** the `OpenAIClient` points at the Ollama OpenAI-compatible endpoint and uses `llama3`

### Scenario: Custom LLM client (non-OpenAI provider)
**Given** a user implements a class with `complete(system_prompt, user_prompt) -> str` that calls Anthropic
**When** they create `Relevancy(client=my_anthropic_client)`
**Then** the scorer uses the custom client, and the `openai` package is never imported

### Scenario: Custom client with supervised scorer
**Given** a user implements a custom LLM client
**When** they create `Correctness(client=my_custom_client)`
**Then** the supervised scorer uses the custom client, and `expected_output` is still passed through `build_prompt` correctly

### Scenario: Client parameter takes priority over model/api_key/base_url/temperature
**Given** `Relevancy(client=my_client, model="gpt-4.1", api_key="sk-key", temperature=0.5)`
**When** the scorer runs
**Then** `my_client` is used; `model`, `api_key`, `base_url`, and `temperature` are ignored

### Scenario: Scores logged to experiment tracker
**Given** a user runs `evaluate()` with built-in scorers and an `ExperimentTracker`
**When** evaluation completes
**Then** `log_eval_sample` is called with `scores` containing only numeric scores and `metadata` containing `{**eval_item.metadata, "<name>_reasoning": ...}`, and all data is visible in the evaluation table

### Scenario: Aggregated scores include built-in scorer results
**Given** an evaluation runs with `Relevancy()` across 3 eval items producing scores `[0.9, 0.7, 0.8]`
**When** `_aggregate_scores` processes the results
**Then** `aggregated_scores` contains `{"relevancy_mean": 0.8, "relevancy_min": 0.7, "relevancy_max": 0.9, "relevancy_count": 3}` (reasoning was already routed to metadata and never reaches aggregation)

### Scenario: Multi-threaded evaluation with built-in scorers
**Given** `evaluate(..., n_threads=4)` with built-in scorers
**When** evaluation runs
**Then** each thread issues its own judge LLM call via the sync OpenAI client, and results are collected correctly without race conditions

## Edge Cases

### Scenario: Correctness scorer without expected_output
**Given** `Correctness()` and `EvalItem(inputs={"request": "..."}, expected_output=None)`
**When** `_call_scorer` is called
**Then** it raises `ValueError` "Supervised scorer 'correctness' requires expected_output, but it is not provided." (existing `_call_scorer` behavior)

### Scenario: Relevancy scorer with non-standard input keys (no input_key set)
**Given** `Relevancy()` (no `input_key`) and `EvalItem(inputs={"foo": "What is RAG?"})`
**When** `_extract_input` finds neither `question` nor `query`
**Then** it falls back to `str(inputs)` and the scorer still produces a result

### Scenario: input_key set but missing from inputs
**Given** `Relevancy(input_key="prompt")` and `EvalItem(inputs={"question": "What is RAG?"})` (no `prompt` key)
**When** `_extract_input` runs
**Then** `input_key` is absent, so it falls back through default keys and uses `inputs["question"]`

### Scenario: Judge returns score outside 0.0–1.0
**Given** the judge returns `{"reasoning": "...", "score": 1.5}`
**When** `parse_judgment` runs
**Then** the score is clamped to `1.0`; a `-0.3` would clamp to `0.0`

### Scenario: Judge returns boolean score
**Given** the judge returns `{"reasoning": "...", "score": true}`
**When** `_try_parse` validates the response
**Then** `score` is rejected (bool is excluded from numeric), triggering the corrective retry

### Scenario: Judge omits reasoning field
**Given** the judge returns `{"score": 0.8}` (valid score, no reasoning)
**When** `parse_judgment` runs and `_evaluate_single_item` routes the result
**Then** `scores` contains `{"relevancy": 0.8}` and `metadata` contains `{"relevancy_reasoning": ""}` (reasoning defaults to empty string; no error)

### Scenario: Duplicate scorer names
**Given** `scorers=[Relevancy(), Relevancy()]`
**When** both produce the key `"relevancy"`
**Then** the existing duplicate-key warning fires: "Duplicate score keys {'relevancy'} from scorer 'relevancy'. Previous values will be overwritten."

### Scenario: Duplicate scorer names avoided with custom name
**Given** `scorers=[Relevancy(name="relevancy_1"), Relevancy(name="relevancy_2")]`
**When** evaluation completes
**Then** `scores` contain `{"relevancy_1", "relevancy_2"}`, `metadata` contains `{"relevancy_1_reasoning", "relevancy_2_reasoning"}`, and there are no duplicate warnings

### Scenario: Empty inputs dict
**Given** a built-in scorer with `EvalItem(inputs={})`
**When** `_extract_input` finds no keys
**Then** it falls back to `str(inputs)` (`"{}"`) and the scorer still returns a result

### Scenario: Non-string output coercion
**Given** the inference function returns a dict `{"answer": "Amsterdam"}`
**When** `build_prompt` interpolates the output
**Then** `str(output)` is used and the judge call proceeds normally

## Error Conditions

### Scenario: openai package not installed (default client)
**Given** a user installed `luml_sdk` without the `llm` extra
**When** they instantiate `Relevancy()` without a custom `client`
**Then** `OpenAIClient.__init__` raises `ImportError` "The default OpenAI client requires the 'openai' package. Install with: pip install luml_sdk[llm]\n  Or pass a custom client: Relevancy(client=MyCustomClient())"

### Scenario: openai package not installed (custom client)
**Given** a user installed `luml_sdk` without the `llm` extra
**When** they instantiate `Relevancy(client=my_custom_client)`
**Then** no `ImportError` is raised — `openai` is never imported because `OpenAIClient` is not used

### Scenario: Invalid or missing API key
**Given** `openai` installed, no `OPENAI_API_KEY`, no `api_key` passed
**When** the scorer makes a judge call
**Then** `OpenAIClient.complete()` raises `LLMError` wrapping the OpenAI auth error, caught by `_evaluate_single_item` and logged as `{"__error__relevancy": "..."}`

### Scenario: LLM API rate limit survives SDK retries
**Given** the OpenAI SDK exhausts its `max_retries` on rate-limit errors
**When** `OpenAIClient.complete()` is called
**Then** it raises `LLMError`, logged as `__error__<scorer_name>`, and evaluation continues with remaining items and other scorers

### Scenario: Judge returns invalid JSON, retry succeeds
**Given** the judge first returns plain text, then valid JSON on the corrective retry
**When** `_call_judge` runs
**Then** it issues a second call with `CORRECTIVE_REMINDER` appended, parses the valid JSON, and returns the score — no error surfaced

### Scenario: Judge returns invalid JSON twice
**Given** the judge returns non-JSON on both the initial call and the corrective retry
**When** `_call_judge` runs
**Then** it raises `JudgeModelError` with the last raw response included, logged as `__error__<scorer_name>`

### Scenario: Judge returns JSON missing score, retry fails
**Given** the judge returns `{"result": 0.5}` (no `score`) on both attempts
**When** `_call_judge` runs
**Then** `_try_parse` rejects both responses and it raises `JudgeModelError`, logged as `__error__<scorer_name>`

### Scenario: One scorer fails, others succeed
**Given** `scorers=[Relevancy(), Correctness()]` and the judge fails JSON parsing for Relevancy but succeeds for Correctness on one item
**When** evaluation completes for that item
**Then** `scores` contain `{"__error__relevancy": "...", "correctness": 0.85}` and `metadata` contains `{"correctness_reasoning": "..."}` — the failing scorer doesn't block others

---

# Tasks

> **Definition of done (applies to every task).** Each task is complete only when, from `sdk/python/sdk/`:
> - `ruff check .` and `ruff format --check .` pass (repo pins `ruff==0.11.5`; follow the existing `# noqa: ANN401` convention for `Any`-typed scorer signatures).
> - `mypy` passes (repo pins `mypy==1.15.0`); the `LLMClient` `Protocol`/`@runtime_checkable`, lazy `import openai`, and new public exports must type-check cleanly.
> - The task's own new tests pass and no existing tests regress (`pytest`).

- [ ] **Task 1: `luml.llm` — LLMClient protocol and OpenAIClient**
  - [ ] Create `sdk/python/sdk/luml/llm/_exceptions.py` — define `LLMError(Exception)`
  - [ ] Create `sdk/python/sdk/luml/llm/_client.py`:
    - `LLMClient` Protocol with `complete(self, system_prompt: str, user_prompt: str) -> str` (use `typing.Protocol`, `@runtime_checkable`)
    - `OpenAIClient` default implementation:
      - Lazy `import openai` in `__init__` with `ImportError` message pointing to `pip install luml_sdk[llm]` and suggesting a custom client
      - `__init__(self, model="gpt-4.1-mini", api_key=None, base_url=None, response_format=None, temperature=0.0, max_tokens=None, max_retries=2)`; constructs `openai.OpenAI(api_key=..., base_url=..., max_retries=...)`
      - `complete(...)` — builds system+user messages, calls `chat.completions.create` with `temperature`, optional `response_format`, optional `max_tokens`; returns `choices[0].message.content or ""`; wraps SDK exceptions in `LLMError`
  - [ ] Create `sdk/python/sdk/luml/llm/__init__.py` — export `LLMClient`, `OpenAIClient`, `LLMError`
  - [ ] Add `llm` optional dependency to `sdk/python/sdk/pyproject.toml`: `openai>=1.0.0,<3.0.0`
  - [ ] Write tests in `sdk/python/sdk/tests/llm/test_client.py`:
    - `OpenAIClient` with a mocked `openai.OpenAI` (valid response, API error → `LLMError`, content `None` → `""`)
    - `temperature` (default 0.0 and override), `max_tokens`, `base_url`, `response_format`, and `max_retries` are forwarded correctly
    - `ImportError` when `openai` is not importable (patch the import)
    - any object with a `complete()` method satisfies `isinstance(obj, LLMClient)` via `@runtime_checkable`

- [ ] **Task 2: Scorer base classes, helpers, reasoning routing, and JudgeModelError**
  - [ ] Add `REASONING_SUFFIX = "_reasoning"` to `sdk/python/sdk/luml/experiments/evaluation/types.py`
  - [ ] Modify `_evaluate_single_item` in `.../evaluation/evaluate.py` to split `all_scores` into `metric_scores` and `reasoning_metadata` (keys ending in `REASONING_SUFFIX`); call `log_eval_sample(scores=metric_scores, metadata={**eval_item.metadata, **reasoning_metadata})` and build `EvalResult(scores=metric_scores, ...)`. Leave `_call_scorer` and `_aggregate_scores` untouched.
  - [ ] Create `sdk/python/sdk/luml/experiments/evaluation/scorers/builtin/__init__.py` (exports added in later tasks)
  - [ ] Create `.../builtin/_exceptions.py` — `JudgeModelError(LLMError)` (import `LLMError` from `luml.llm`)
  - [ ] Create `.../builtin/_prompts.py` — `JSON_OUTPUT_INSTRUCTION`, `CORRECTIVE_REMINDER` constants
  - [ ] Create `.../builtin/_base.py`:
    - `_try_parse(raw) -> dict | None` (JSON parse; require numeric non-bool `score`)
    - `_call_judge(client, system_prompt, user_prompt) -> dict` (one corrective retry with `CORRECTIVE_REMINDER`, else `JudgeModelError`)
    - `_init_client(client, model, api_key, base_url, temperature) -> LLMClient`
    - `_extract_input(inputs, input_key, default_keys) -> str`
    - `LLMJudgeScorer(UnsupervisedScorer)`: `__init__(client, model, api_key, base_url, temperature, input_key, name)`, abstract `default_name`/`build_prompt`, concrete `parse_judgment` (clamp + `f"{name}{REASONING_SUFFIX}"`), concrete `score`/`get_name`
    - `SupervisedLLMJudgeScorer(SupervisedScorer)`: same `__init__`, abstract `default_name`/`build_prompt(inputs, expected_output, output)`, concrete `parse_judgment`/`score`/`get_name`
  - [ ] Write tests in `sdk/python/sdk/tests/experiments/evaluation/scorers/test_base.py`:
    - `_try_parse`: valid dict with numeric score; invalid JSON → `None`; missing score → `None`; bool score → `None`
    - `_call_judge`: success first try; success on retry (assert second call uses corrective reminder); failure twice → `JudgeModelError`
    - `_init_client`: returns provided client; creates `OpenAIClient` with `response_format={"type": "json_object"}` and `temperature` when `None`
    - `_extract_input`: `input_key` present; `input_key` missing → default chain; no keys → `str(inputs)`
    - `parse_judgment`: clamps score to [0,1]; missing reasoning → `""`; key names `<name>`/`<name>_reasoning`
    - concrete stub subclasses of both base classes: `score` calls `build_prompt → _call_judge → parse_judgment`; supervised passes `expected_output` through; custom `name` honored
  - [ ] Add tests in `.../evaluation/test_evaluate.py` for reasoning routing: a stub scorer returning `{name, f"{name}_reasoning"}` results in `log_eval_sample` getting numeric-only `scores` and reasoning under `metadata`; `EvalResult.scores` excludes reasoning; `error`/`__error__` keys stay in `scores`

- [ ] **Task 3: Relevancy scorer**
  - [ ] Create `.../builtin/relevancy.py` — `Relevancy(LLMJudgeScorer)`: `default_name` → `"relevancy"`; `build_prompt` uses `_extract_input(inputs, self._input_key, ("question", "query"))` + the specified system/user prompts (output coerced via `str`)
  - [ ] Export `Relevancy` from `builtin/__init__.py`
  - [ ] Write tests in `.../scorers/test_relevancy.py`:
    - Mock `LLMClient.complete` to return controlled JSON
    - input key extraction: `question`, `query`, fallback, and `input_key` override
    - output dict has `relevancy` (float) and `relevancy_reasoning` (str)
    - score clamping; reasoning default `""`

- [ ] **Task 4: Correctness scorer**
  - [ ] Create `.../builtin/correctness.py` — `Correctness(SupervisedLLMJudgeScorer)`: `default_name` → `"correctness"`; `build_prompt` uses `_extract_input(inputs, self._input_key, ("request", "question"))`; `expected_output` dict with `expected_facts` → bulleted block, else `str(expected_output)`; specified prompts
  - [ ] Export `Correctness` from `builtin/__init__.py`
  - [ ] Write tests in `.../scorers/test_correctness.py`:
    - Mock `LLMClient.complete`
    - `expected_output={"expected_facts": [...]}` and `expected_output="plain string"`
    - `isinstance(Correctness(), SupervisedScorer)` is `True`
    - integration with `_call_scorer`: a `Correctness()` + `EvalItem` with `expected_output` routes to the supervised branch and returns `{"correctness", "correctness_reasoning"}`

- [ ] **Task 5: Summarization, PromptAlignment, and Completeness scorers**
  - [ ] Create `.../builtin/summarization.py` — `Summarization(LLMJudgeScorer)`: keys `("text",)`, specified prompts
  - [ ] Create `.../builtin/prompt_alignment.py` — `PromptAlignment(LLMJudgeScorer)`: keys `("instructions",)`, specified prompts
  - [ ] Create `.../builtin/completeness.py` — `Completeness(LLMJudgeScorer)`: keys `("question", "task")`, specified prompts
  - [ ] Export all three from `builtin/__init__.py` (so `builtin/__init__.py` now exports all five)
  - [ ] Re-export the five built-ins from `luml/experiments/evaluation/scorers/__init__.py` (add to its `__all__`)
  - [ ] Re-export the five built-ins from `luml/experiments/evaluation/__init__.py` alongside the existing exports (add to its `__all__`); verify all three import paths in *Public API* resolve to the same classes
  - [ ] Write tests `.../scorers/test_summarization.py`, `test_prompt_alignment.py`, `test_completeness.py`: same pattern as Relevancy (mock client, input-key extraction with fallback, output dict structure with `_reasoning`)

- [ ] **Task 6: Integration tests and end-to-end validation**
  - [ ] Write `.../scorers/test_integration.py`:
    - Mixed built-in + custom scorers in one `evaluate()` call (mock client, real `_call_scorer`/`evaluate`)
    - `Correctness` (supervised) and `Relevancy` (unsupervised) coexist in one `scorers` list
    - reasoning routing end-to-end: `log_eval_sample` receives numeric-only `scores` and `<name>_reasoning` under `metadata`; `aggregated_scores` contains only numeric metrics
    - duplicate scorer-name warning with two `Relevancy()`; avoided with custom names
    - error isolation: one scorer's `JudgeModelError` doesn't block others (`__error__<name>` present)
    - corrective retry path: client returns bad JSON then good JSON → score returned, no error
    - multi-threaded evaluation (`n_threads=2`) with built-in scorers
    - built-in scorers with a custom `LLMClient` (no `openai` dependency needed); multiple scorers sharing one client instance
  - [ ] Verify existing tests in `.../test_evaluate.py` still pass (no regressions)
  - [ ] Add a runnable example `sdk/python/sdk/examples/builtin_scorers_example.py` mirroring `evals_example.py` but using built-in scorers

- [ ] **Task 7: Documentation for the new public API**
  - [ ] Register the new modules for API-reference generation in `docs/generate_docs.py` `sdk_modules` (the `generate-docs` entrypoint drives the SDK docs):
    - Add an `"LLM"` category → `"luml.llm": ("llm", "client")` (or similar subdir/file)
    - Add the built-in scorers under the existing `"Experiments"` (or a new `"Evaluation"`) category → e.g. `"luml.experiments.evaluation.scorers.builtin": ("experiments/evaluation", "builtin_scorers")`
  - [ ] Run `uv run docs/generate_docs.py` and commit the generated `.md` pages (consistent with the existing `docs/docs/sdk/experiments/evaluation/evaluate.md` and `types.md`)
  - [ ] Add a short guide section covering built-in scorers — import paths, the default `OpenAIClient`, `temperature`/`model`/`input_key`/custom-client options, the score-vs-reasoning (metadata) split, and a copy-pasteable example — alongside `lumlflow/frontend/src/docs/llm_evaluation_lumlflow.md` (extend it or add a sibling doc, matching that file's style)
  - [ ] Ensure module/class docstrings on `OpenAIClient`, `LLMClient`, and the five scorers are complete enough that pydoc-markdown renders useful reference pages (the generator turns docstrings into the `.md`)
