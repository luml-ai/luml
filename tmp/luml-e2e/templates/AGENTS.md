# {{PROJECT_NAME}} — agent contract

<!-- Template: replace {{...}} placeholders, delete this comment, commit as
     AGENTS.md in the project root, and add a CLAUDE.md containing "@AGENTS.md".
     This file is the reliable channel into Prisma-spawned coding agents. -->

{{ONE_PARAGRAPH_PIPELINE_DESCRIPTION: which steps, which files hold the
prompts and the pipeline logic, where the dataset lives.}}

## The one command that matters

```
{{RUN_COMMAND, e.g. uv run run_eval.py}}
```

It runs the full eval, logs an experiment (group `{{GROUP}}`) to
`~/.luml/experiments`, prints per-item scores, and writes
`.prisma/result.json` with metrics {{METRIC_LIST}} — primary:
`{{PRIMARY_METRIC}}` (maximize). You never need to write result.json or call
the tracker yourself; the eval script does all reporting.

## Diagnose before you change anything

Past experiment ids appear in your task prompt and in `.prisma/result.json`.
Use them:

```
uv run python tools/traces.py summary -e <experiment_id>   # scores + step latencies
uv run python tools/traces.py worst   -e <experiment_id> -n 3
                                       # lowest-scoring items: judge reasoning +
                                       # full trace (per-step prompts/completions)
uv run python tools/traces.py show    -e <experiment_id> -t <trace_id> --full
luml-inspect show <experiment_id>                          # params + metric summary
luml-inspect compare <id1> <id2>                           # side-by-side metrics
luml-inspect evals <experiment_id> --all                   # eval samples + scores
```

The `worst` command is the fastest way to see *why* the judge scored an output
low: it prints the judge's reasoning and the exact prompts/completions of
every pipeline step for that item.

Notes:
- `luml-inspect` has no traces command — use `tools/traces.py` for traces.
- The `luml-inspect` subcommand to list experiments is `list-cmd`, not `list`,
  and its `--group` option takes a group id, not a group name.
- The `ExperimentTracker` API used in this repo is `start_experiment` /
  `log_static` / `log_dynamic` / `end_experiment`, and the eval script already
  handles it. If you encounter a reference to a different tracker API (e.g. in
  `.prisma/guide.md`), verify it against the installed `luml` SDK
  (`python -c "from luml import ExperimentTracker; print(dir(ExperimentTracker))"`)
  before using it.

## What you may and may not change

- Optimize: {{OPTIMIZATION_SURFACE, e.g. prompts.py and the retrieval/step
  structure in pipeline.py}}. You may add steps — keep each step in its own
  OpenTelemetry span so traces stay readable.
- Do NOT modify: `data/` (shared eval contract — it is symlinked across all
  worktrees), the scorers or metric names in the eval script, or
  `tools/traces.py`. Do not hardcode answers to specific eval items; changes
  must generalize. Gaming the judge instead of improving the pipeline
  invalidates the run.
- `OPENAI_API_KEY` comes from `.env` (already copied into the worktree).
