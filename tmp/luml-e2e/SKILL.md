---
name: luml-e2e
description: Guide the user through the LUML loop end to end - instrument an LLM system (plain OpenAI SDK or LangChain/LangGraph) with luml-sdk, run experiments that capture traces and LLM-as-judge eval scores, and inspect them in lumlflow (Flow). Works standalone; optionally hands the same eval script to Prisma so coding agents optimize the system automatically. Use when the user wants to add tracing/experiment tracking to an LLM app, run and inspect evals locally, demo Flow, or connect that loop to Prisma.
---

# LUML end to end: trace + evaluate with Flow, then (optionally) optimize with Prisma

You are guiding the user through building this themselves, in a **new project
repo**. Work phase by phase; verify each phase actually works before moving to
the next; do the mechanical work (writing files, running commands) yourself and
narrate the load-bearing facts. Ask the user only for genuine decisions: what
system to build, and whether to launch things that cost money or subscription
usage (eval runs, the Prisma run).

The guide has two parts. **Part A needs no Prisma** and is complete on its
own: instrument the system, run an experiment, look at the traces and scores
in Flow, iterate by hand. **Part B** plugs Prisma into the exact same eval
script so coding agents do the iterating. Stop after Part A if the user only
wants tracking/tracing.

```
Part A (standalone)                                    Part B (optional)
                                                       
pipeline (OpenAI SDK or LangChain/LangGraph)           Prisma engine + coding agents
   | instrumented: OTel spans -> luml-sdk                  | git worktrees, edit prompts/pipeline,
   | run_eval.py: evaluate() + LLM judges                  | re-run run_eval.py, merge the winner
   v                                                       v
Flow store  ~/.luml/experiments  <--- reads ---  luml-inspect + tools/traces.py
   ^                                                       ^
   | lumlflow ui / tui (traces, evals, judge reasoning)    | .prisma/result.json (metrics contract)
```

---

# Part A — Instrument, run, inspect (no Prisma)

## A0 — Preflight

- `python3 --version` >= 3.12 (hard floor: the SDK uses PEP 695 syntax), `uv`,
  `git`.
- `OPENAI_API_KEY` available (env or a project `.env`). Used by the pipeline
  and, later, by the built-in judges (default judge `gpt-4.1-mini`,
  temperature 0).
- **Store location decision (do not skip):** use `~/.luml/experiments`. It is
  the shared default of `lumlflow ui`/`tui` and of the Prisma tooling. The
  SDK's own default is **different** (`./experiments` in CWD) — always pass
  the connection string explicitly:

  ```python
  STORE = f"sqlite://{Path.home()}/.luml/experiments"
  ```

  Mismatched stores are the #1 "my UI is empty" cause.

## A1 — Scaffold the project

Create the project as its own directory (`git init` + initial commit; useful
even without Prisma, and required by it later), then a uv project:

- Always: `luml-sdk[llm,tracing]>=0.2.0,<0.3.0`, `python-dotenv`;
  dev group: `lumlflow>=0.2.0,<0.3.0`, `pytest`, `ruff`.
  `luml-sdk[tracing]` already pulls `opentelemetry-sdk` and
  `opentelemetry-instrumentation-openai`.
- If the system is LangChain/LangGraph: add `langchain-openai`, `langgraph`
  (for graphs), and `opentelemetry-instrumentation-langchain`. The repo docs
  install it alongside `wrapt==1.17.0`; add that pin if the instrumentor
  import fails.
- `.gitignore`: `.venv/`, `.env`, `.prisma/`, `__pycache__/`.
- `.env` with `OPENAI_API_KEY`.
- Eval dataset and any knowledge base under `data/`.
- `uv sync`.

Ask the user what system they want to instrument. Anything with >= 2 LLM
steps plus a deterministic step gives interesting traces. Default if they have
no preference: a support-ticket assistant (classify ticket -> retrieve policy
snippets from a small KB -> draft reply), judged on factual correctness
against `expected_facts`. Design the dataset so scores are diagnosable: ~10
items, each with the facts the reply must convey.

## A2 — Instrument the system

Everything below routes OpenTelemetry spans into the Flow store, attached to
whichever experiment is currently open on the tracker. The tracker API:

```python
from luml.experiments.tracker import ExperimentTracker
tracker = ExperimentTracker(STORE)
tracker.enable_tracing()                      # installs the OTel provider -> store
exp_id = tracker.start_experiment(name=..., group=..., tags=[...])
tracker.log_static(key, value)                # params (model, git commit, knobs)
tracker.log_dynamic(key, value, step=0)       # metrics
tracker.end_experiment()                      # or fail_experiment()
```

If any other reference — including `.prisma/guide.md` in Part B — shows a
different method set, check it against the installed SDK with
`dir(ExperimentTracker)` before relying on it.

Instrumentors and `enable_tracing()` must run **before** any model client or
graph is constructed and before the first call; do it at module import time.

### A2a — Plain OpenAI SDK

```python
from opentelemetry import trace
from luml.experiments.tracing import instrument_openai

instrument_openai()                           # every client.chat.completions.create -> Chat span
tracer = trace.get_tracer("myproject.pipeline")

def classify(client, text: str) -> dict:
    with tracer.start_as_current_span("classify") as span:
        ...                                   # OpenAI call becomes a child span
        span.set_attribute("ticket.category", category)
        return {...}

def retrieve(category: str, text: str) -> list[dict]:
    with tracer.start_as_current_span("retrieve") as span:
        span.set_attribute("gen_ai.operation.name", "execute_tool")   # renders as Tool span
        span.set_attribute("retrieval.selected_ids", json.dumps(ids))
        ...
```

Rules: one function per step, each in its own span; non-LLM steps get
`gen_ai.operation.name = "execute_tool"`; record every decision the step
makes as an attribute — that's what makes a bad score diagnosable later.

How Flow types a span (`luml.experiments.utils.guess_span_type`):
`llm.request.type == "chat"` or `gen_ai.operation.name == "chat"` -> Chat;
`invoke_agent` -> Agent; `execute_tool` -> Tool; `embeddings` -> Embedder;
anything else -> generic span. The OpenAI instrumentor writes the **new**
GenAI conventions (`gen_ai.input.messages` / `gen_ai.output.messages` JSON
arrays); the bundled `templates/traces.py` parses both new and legacy forms.

### A2b — LangChain / LangGraph

Two instrumentors: `instrument_openai()` for the API calls,
`LangchainInstrumentor` for chains, nodes and graph invocations. No manual
spans are needed for LangChain-managed steps.

```python
from opentelemetry.instrumentation.langchain import LangchainInstrumentor
from luml.experiments.tracing import instrument_openai
from luml.experiments.tracker import ExperimentTracker

instrument_openai()
LangchainInstrumentor().instrument()          # BEFORE ChatOpenAI(...) / graph.compile()

tracker = ExperimentTracker(STORE)
tracker.enable_tracing()

llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)
graph = build_graph(llm).compile()

exp_id = tracker.start_experiment(name="smoke", group="my-app")
result = graph.invoke({"question": "..."})    # one trace: graph -> node spans -> Chat spans
tracker.end_experiment()
```

- Each `graph.invoke` / `chain.invoke` yields one trace with a parent-child
  tree of node/chain spans and the LLM calls under them; the LLM spans carry
  prompts, completions and token counts. Node spans render as generic spans.
- To make a node's decisions visible, set attributes on the current span from
  inside the node: `trace.get_current_span().set_attribute("route", q_type)`.
- Steps that run outside LangChain (custom retrieval, post-processing) still
  get a manual span as in A2a.
- Reference implementations in the monorepo:
  `docs/docs/guides/Integrations/langgraph_tutorial.md` and
  `lumlflow/frontend/src/docs/llm_evaluation_lumlflow.md`.

### A2c — Smoke-test the instrumentation

Before building an eval, run the system once inside an experiment
(`smoke.py`: start experiment -> one invocation -> end experiment), then open
Flow (A4) and confirm: one experiment in the group, one trace, one span per
step, prompts and completions visible on the Chat spans, your attributes on
the step spans. Fix the instrumentation now — it is much harder once ten eval
items are interleaved.

## A3 — Run an experiment: eval harness with LLM-as-judge

One script (e.g. `run_eval.py`) that runs the whole dataset through the
system inside one experiment and scores each output. Skeleton:

```python
from luml.experiments.evaluation import Correctness, EvalItem, Relevancy, unsupervised_scorer
from luml.experiments.evaluation.evaluate import evaluate

tracker = ExperimentTracker(STORE)
tracker.enable_tracing()                      # + instrumentors, see A2
exp_id = tracker.start_experiment(name=args.name, group=GROUP, tags=[...])
# log_static: model, git commit, knobs

results = evaluate(
    eval_dataset=[EvalItem(id=..., inputs={"ticket": ...},
                           expected_output={"expected_facts": [...]},
                           metadata={...}), ...],
    inference_fn=lambda inputs: answer(inputs["ticket"]),
    scorers=[Correctness(input_key="ticket"), Relevancy(input_key="ticket"),
             my_custom_scorer],
    dataset_id="...-v1", experiment_tracker=tracker, n_threads=4,
)
for k, v in results.aggregated_scores.items():
    tracker.log_static(f"eval_{k}", v)
tracker.log_dynamic("correctness_mean", results.aggregated_scores["correctness_mean"], step=0)
tracker.end_experiment()
```

Facts to apply:

- `evaluate()` wraps each item in an `eval_request` span (`inference_fn` and
  `eval_scoring` children), auto-logs one eval sample per item and links it to
  that trace. That link is what lets Flow jump from a low score to the trace
  that produced it.
- `Correctness` is supervised (needs `expected_output`; a dict with an
  `expected_facts` list gets special formatting for the judge). `Relevancy`,
  `Completeness`, `PromptAlignment`, `Summarization` are unsupervised. All
  default to keys like `question`/`request` — pass `input_key=` to match your
  inputs dict. Each judge also emits `<name>_reasoning`, which `evaluate()`
  routes into eval metadata — gold for diagnosis. Custom scorers:
  `@supervised_scorer` / `@unsupervised_scorer`.
- Aggregates come back as `results.aggregated_scores`
  (`<name>_mean/_min/_max/_count`) and are NOT logged automatically — log
  them as above. Pick ONE headline metric (e.g. `correctness_mean`) and keep
  its name stable across runs so experiments stay comparable.
- Give every run a `--name` and log the git commit + the knobs you changed as
  static params; that is how you'll tell runs apart in Flow.
- Minimal alternative without `evaluate()`: loop over items yourself and call
  `tracker.log_eval_sample(eval_id, dataset_id, inputs, outputs, references,
  scores)`; you lose the automatic trace link unless you wrap each item in a
  span and call `link_eval_sample_to_trace` yourself.

Run the baseline (confirm cost with the user first — ~10 items x (pipeline
calls + 2 judge calls) of mini models, cents). Verify scores have spread and
the worst items are the ones you expected to fail.

## A4 — Inspect in Flow

- **Web UI:** `uv run lumlflow ui` -> http://127.0.0.1:5000 (`--port`,
  `--no-browser`, `--path sqlite://<dir>` to point elsewhere). Walk the user
  through: group -> experiment -> params/metrics; Evals tab sorted by score
  ascending -> judge reasoning in metadata -> linked trace; Traces tab ->
  per-step waterfall with prompts, completions, tokens, and your step
  attributes.
- **Terminal:** `uv run lumlflow tui` (needs `lumlflow[tui]`). Bonus:
  `uv run lumlflow tui run_eval.py --name baseline` launches the script with
  the shared store and auto-attaches to the experiment it creates, so the
  user watches metrics/traces arrive live.
- **Programmatic / scriptable:** copy `templates/traces.py` from this skill
  into the project as `tools/traces.py` and set its `GROUP` constant.
  `summary` (scores + per-step latencies), `worst -n 3` (lowest-scoring items
  with judge reasoning + full span tree incl. prompts/completions), `show -t
  <trace>` (one trace). Useful for humans in a terminal and essential for
  agents in Part B.
- If the UI is empty, the store paths are mismatched (A0 decision).

## A5 — Iterate by hand

This is the loop Prisma automates in Part B; do at least one turn manually so
the user understands what the agents will be doing:

1. `uv run python tools/traces.py worst -n 3` (or the Evals tab) -> read the
   judge reasoning and the step prompts/attributes for the worst items.
2. Form a hypothesis (e.g. "the draft step only sees snippet titles").
3. Change the prompt/pipeline, `git commit`, re-run with a new `--name`.
4. Compare in Flow (group view) — did the headline metric move, did the worst
   items change?

Part A is complete here. Everything in Part B builds on this exact script and
store.

---

# Part B — Let Prisma run the loop (optional)

Prisma spawns coding agents in git worktrees, each of which edits the system,
runs your `run_eval.py`, and reports the metric; Prisma forks the promising
branches and merges the winner. It reads an attempt's metrics **only** from
`.prisma/result.json` written by the run command; agents learn from past
experiments via `luml-inspect` and your `tools/traces.py`.

## B0 — Extra preflight

- An agent CLI on PATH: `claude` (or `codex`, `cursor-agent`, ...).
- Prisma source. Prefer the monorepo checkout (`~/github/luml/luml/prisma` on
  this machine): PyPI `luml-prisma` (0.1.2) is behind the source (0.2.0) and
  this guide matches 0.2.0. `pip install luml-prisma` is the fallback — verify
  endpoints against `reference/prisma-api.md` if used.
- **Headroom.** The run only lands if the baseline has room to improve AND
  the cause is visible in traces. If you built the Part A system for a demo,
  make the baseline honestly mediocre: a draft step that receives titles/ids
  instead of full reference text; retrieval hard-filtered by a classified
  category; a category enum missing a value the dataset needs. Verified
  expectation: ~0.55–0.7 correctness baseline.

## B1 — Make the repo Prisma-ready

- The project must be its own git repo (Prisma refuses paths without `.git`)
  and must live **outside** any other repo: worktrees go in a sibling
  `../worktrees/` directory.
- `data/` is symlinked from the main repo into every worktree
  (`shared_paths` default), so all attempts share one dataset. Corollary:
  agents must never edit it. `.env` is copied into every worktree.
- **The metrics contract.** Add this to the end of `run_eval.py` (harmless
  outside Prisma):

  ```python
  Path(".prisma").mkdir(exist_ok=True)
  Path(".prisma/result.json").write_text(json.dumps({
      "success": True, "experiment_id": exp_id,
      "metrics": {"correctness_mean": ..., "relevancy_mean": ...},
  }))
  print(json.dumps({"type": "prisma-message", "metric": primary}))  # stdout fallback
  ```

  Prisma's winner selection is a pure argmax on the `primary_metric` key
  you'll pass in the run config — never rename it. The Run node deletes any
  stale `result.json` before executing, so the script must write it fresh
  every run.
- **Trace access for agents.** `luml-inspect` (shipped with luml-prisma, what
  Prisma tells agents to use) covers metrics/params/evals but has **no traces
  command**; `tools/traces.py` from A4 closes that gap. Verify
  `uv run python tools/traces.py worst -n 2` works from the repo root.
- **Agent contract.** Copy `templates/AGENTS.md` into the project as
  `AGENTS.md`, fill the placeholders, and add a `CLAUDE.md` containing
  `@AGENTS.md`. This is the reliable channel into Prisma-spawned agents: it
  names the run command, the metric, the diagnosis tools, and the guardrails
  (don't touch `data/`, scorers, or metric names; don't game the judge).
- Commit everything — worktrees only see committed files.

## B2 — Optimize with Prisma

Full REST details: `reference/prisma-api.md` in this skill.

1. **Engine**: `cd <prisma-checkout> && uv run luml-prisma` ->
   http://127.0.0.1:8420. Launching via `uv run` from the prisma package is
   load-bearing: agents inherit the engine's PATH, and that's how they find
   `luml-inspect`. Check `curl -s localhost:8420/api/agents/available`.
2. **Register + create + start** (confirm with the user first — this drives
   their agent CLI with permissions bypassed and burns subscription usage):
   `POST /api/repositories {name, path}`, then `POST /api/runs` (see reference
   for all fields), then `POST /api/runs/{id}/start`. Sensible demo config:
   `max_depth: 2`, `max_children_per_fork: 2`, `max_debug_retries: 2`,
   `max_concurrency: 1`, `auto_mode: true`, `auto_terminate_timeout: 60`,
   `run_command: "uv run run_eval.py"`, `primary_metric: <your metric>`.
3. **The objective text matters.** Include: what to maximize and the exact
   metric name; that the eval exists and must not be modified; an explicit
   instruction to diagnose parent experiments first via
   `uv run python tools/traces.py worst -e <id>` and `luml-inspect compare`;
   the guardrails ("do not modify data/, scorers, or metric names; changes
   must generalize, no per-item hardcoding").
4. **Watch**: the Prisma board (https://app.luml.ai -> Prisma, pointing at the
   local engine) or `GET /api/runs/{id}/graph` / `/events`. New experiments
   appear live in the Flow UI as attempts run — same group, same store as
   Part A.
5. **Winner**: when the run succeeds, `POST /api/runs/{id}/merge` (or the
   board button) merges the best branch — argmax of `primary_metric` over
   successful run nodes. Close the loop with
   `luml-inspect compare <baseline_id> <winner_id>` and the Flow UI.

---

## Troubleshooting

### Part A (tracking / tracing)

| Symptom | Cause / fix |
| --- | --- |
| Flow UI shows nothing | Store mismatch: SDK defaulted to `./experiments` (CWD). Pass `sqlite://~/.luml/experiments`-style path explicitly (expand `~` in code). |
| Traces exist but LLM spans have no prompts/completions | Instrumentor was enabled after the client/model was constructed. Move `instrument_openai()` / `LangchainInstrumentor().instrument()` to import time. |
| LangChain nodes missing from the trace (only raw OpenAI spans) | `opentelemetry-instrumentation-langchain` not installed or instrumented after `graph.compile()`. |
| `LangchainInstrumentor` import/instrument error | Add the `wrapt==1.17.0` pin the repo docs use. |
| Spans land in the wrong experiment or none | Spans attach to the experiment currently open on the tracker; call `start_experiment` before invoking and `end_experiment` after. One tracker per process. |
| Eval samples not linked to traces | You bypassed `evaluate()`; wrap each item in a span and call `link_eval_sample_to_trace`, or use `evaluate()`. |
| Code crashes with `AttributeError` on an `ExperimentTracker` method | It used a tracker method that isn't on the installed SDK. Use the API in A2 and verify any other reference with `dir(ExperimentTracker)`. |

### Part B (Prisma)

| Symptom | Cause / fix |
| --- | --- |
| `luml-inspect list` fails | The subcommand is `list-cmd`; also `--group` takes a group **id**, not a name. |
| Agent code crashes with `AttributeError` on an `ExperimentTracker` method | Same as above; the AGENTS.md template tells agents to verify against the SDK. |
| Prisma run finishes but "no best node" / merge refused | The run command never wrote `.prisma/result.json` with the exact `primary_metric` key, or wrote it before the Run node cleared it. |
| Agents can't find `luml-inspect` | Engine wasn't launched from an env with it on PATH. Restart engine via `uv run luml-prisma` from the prisma package. |
| Run hangs on an Implement node | Interactive CLI without `auto_mode: true`; also all `*_timeout` fields in the run payload are silently ignored (engine bug) — defaults apply (implement 3600s). |
| Registered repo rejected | Path must contain `.git`. |
| Mock agent (`LUML_PRISMA_ENABLE_MOCK_AGENT=1`) fork fails | Known drift between mock agent and the current fork prompt; don't use mock for the happy path. |
