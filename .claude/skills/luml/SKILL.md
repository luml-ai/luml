---
name: luml
description: Work with the LUML Python SDKs - track ML experiments, log models and metrics, run LLM evals and tracing (`luml`, the Flow SDK), and manage the platform registry - artifacts, collections, tracks, deployments, monitoring and lineage (`luml_api`, the Core client). Use whenever the task involves LUML, lumlflow, ExperimentTracker, LumlClient, or when writing training/eval code that should be tracked.
---

# LUML SDKs

LUML has two Python packages. Pick by what the task needs:

| Need | Package | Import | Entry point |
| --- | --- | --- | --- |
| Track experiments, metrics, models, traces, evals — locally | `luml_sdk` | `luml` | `ExperimentTracker` |
| Registry, collections, tracks, deployments, monitoring, lineage — on the platform | `luml_api` | `luml_api` | `LumlClient` |

`lumlflow` bundles the Flow SDK and adds the local dashboard: `pip install lumlflow && lumlflow ui` (UI at http://127.0.0.1:5000).

Both packages require Python >= 3.12.

## Rules

1. **Never invent API surface.** Every method below is verified. If you need something not listed here, read the reference file first, then the source (`sdk/python/sdk/luml/`, `sdk/python/api/luml_api/`) — do not guess method names or kwargs.
2. **One tracker per script, wrapped in `with`.** `ExperimentTracker.__exit__` ends the experiment on success and calls `fail_experiment()` on an exception, so runs never stay stuck in `running`.
3. **`log_static` for values fixed for the run** (hyperparameters, config, dataset name); **`log_dynamic` for series** (loss/accuracy per step). `log_dynamic` takes numbers only.
4. **Never hardcode credentials.** `LumlClient()` with no arguments reads `LUML_API_KEY` and `LUML_BASE_URL` from the environment — prefer that form.
5. **Don't add a tracker to code the user didn't ask to instrument.** Adding tracking changes what a training script writes to disk.

## Minimal tracking run

```python
from luml.experiments.tracker import ExperimentTracker

with ExperimentTracker() as tracker:  # default: "sqlite://./experiments"
    tracker.start_experiment(name="gbm_baseline", group="churn", tags=["baseline"])
    tracker.log_static("n_estimators", 100)

    model = GradientBoostingClassifier(n_estimators=100).fit(X_train, y_train)

    for step, probs in enumerate(model.staged_predict_proba(X_test)):
        tracker.log_dynamic("loss", log_loss(y_test, probs), step=step)

    tracker.log_model(model, name="gbm_final", inputs=X_train)
```

`start_experiment` returns the experiment id; every logging call takes an optional
`experiment_id` and otherwise targets the current one.

## References

Read the file that matches the task before writing code:

- `references/flow-tracking.md` — `ExperimentTracker` in full: experiments, groups, static/dynamic metrics, `log_model` and its flavors, attachments, and the read/query API used to inspect past runs.
- `references/evals-tracing.md` — `evaluate()`, built-in and custom scorers, `log_eval_sample`, annotations, OpenTelemetry tracing and `instrument_openai`.
- `references/artifacts.md` — packaging datasets (`save_tabular_dataset`, `save_hf_dataset`, `load_dataset`), experiment snapshots (`save_experiment`), model cards (`CardBuilder`), reference profiles for monitoring.
- `references/repro.md` — reproducing and debugging API behaviour: HTTP tracing, the repro-script scaffold in `scripts/`, the local dev stack, reading failures. Read this whenever the task is "why does this call fail", "reproduce this bug", or "see what the SDK actually sends".
- `references/core-api.md` — `LumlClient`: organizations/orbits/collections, artifact upload/download, tracks and stages, deployments, monitoring dashboards, lineage.
- `references/api-shapes.md` — the raw REST API for curl/httpx: list response shapes, bodies that need `organization_id`/`orbit_id`, the artifact delete lifecycle, cursor rules, and the Flow local API (`lumlflow ui`). Read it before calling the backend without `LumlClient`.
- `references/dev-stack.md` — running the platform locally and its traps: alembic drift between branches, the frontend not starting in docker on macOS, port 5000, Secure/Lax cookies, identical JWTs within one second, broken SendGrid and how to create a second user in psql. Read it before `docker compose up`.
- `references/frontend-map.md` — where each SPA and Flow UI feature lives (routes, components, hooks, stores) and what to check first when reading a UI bug. Read it before code-reviewing a frontend finding.

## QA against the dev stack

```bash
source ~/.claude/skills/luml/scripts/dev_api.sh   # signs in, sets API/TOKEN/ORG/ORBIT, defines a/A/j/psql/backend_errors
```

Verify a reported bug at runtime when the stack is up (curl for the API,
`localhost:5173` for the SPA); fall back to code review with `frontend-map.md`
when it is not. Say which of the two you did.

## Install

```bash
pip install luml_sdk                  # Flow SDK
pip install "luml_sdk[tracing]"       # + OpenTelemetry tracing and OpenAI instrumentation
pip install "luml_sdk[datasets]"      # + pandas/pyarrow for tabular datasets
pip install "luml_sdk[datasets-hf]"   # + HuggingFace datasets
pip install "luml_sdk[llm]"           # + openai, for LLM-judge scorers
pip install luml_api                  # Core platform client
```

## Maintaining this skill

`scripts/check_docs.py` verifies every symbol, method and keyword argument the
references quote against the SDK source. Run it after the SDK changes:

```bash
sdk/python/sdk/.venv/bin/python .claude/skills/luml/scripts/check_docs.py
```

It needs an environment where both `luml` and `luml_api` import — the SDK's own
venv has all the optional dependencies; the shared `sdk/python/.venv` does not.
