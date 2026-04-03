from typing import Any


def _esc(s: str) -> str:
    return s.replace("{", "{{").replace("}", "}}")


_GUIDE_REF = (
    "Refer to `.luml-agent/guide.md` in the worktree root "
    "for tooling, CLI usage, and output conventions."
)

_ENVIRONMENT_BLOCK = """\
## Environment
- Package manager: `uv`
- Worktree path: {worktree_path}
- Base branch: {base_branch}
- Run command: `{run_command}`"""

_IMPLEMENT_ROOT = """\
# Objective

{objective}

{environment}

## How This Works

Your job is to **write the code** that accomplishes the objective. \
You do NOT run the training yourself — after you finish, the orchestrator \
will automatically execute the run command (`{run_command}`) in a separate \
step. So implement everything needed so that the run command works \
end-to-end when executed from the worktree root.

## Reference

{guide_ref}

## Guidelines
- Inspect the repository to understand the existing structure before \
writing code.
- Ensure the entrypoint file referenced by the run command exists and \
works when invoked from the worktree root.
- Prefer simple, working solutions over complex ones.
- Write experiment tracking code using the `luml-sdk` package \
(import as `luml`, install as `luml-sdk`; see guide.md for details).
- Save the trained model as a LUML artifact at \
`.luml-agent/artifact.luml` using \
`save_sklearn(model, X, path=".luml-agent/artifact.luml")` \
(or the equivalent for your framework).

## Metric Rules (CRITICAL)

The orchestrator **always maximizes** the reported metric to select the best run. \
You must follow these rules:

1. **Higher is always better.** If your natural metric should be minimized \
(e.g. loss, error rate, RMSE), **invert it** before reporting \
(e.g. report `1 - error_rate`, or `-loss`, or `1 / (1 + rmse)`).
2. **Choose one primary metric** and add a code comment explaining what it is \
and how it is computed (e.g. `# Metric: neg_rmse = -RMSE, higher is better`).
3. **Never change the metric across runs.** If a metric is already defined in \
the codebase, use the exact same name and calculation. Check existing code \
and `.luml-agent/result.json` from prior runs before defining a new metric.
4. Report the metric in `.luml-agent/result.json` under `"metrics"` \
(see guide.md for the schema)."""

_IMPLEMENT_FORK_CHILD = """\
# Task

{proposal}

## Background Context

The original objective for this run (for context only — follow the \
task above):

> {objective}

{environment}

## How This Works

Your job is to **write the code** that accomplishes the task. \
You do NOT run the training yourself — after you finish, the \
orchestrator will automatically execute the run command shown above \
in a separate step. Implement everything needed so that the run \
command works end-to-end from the worktree root.

## Reference

{guide_ref}

## Metric Rules (CRITICAL)

The orchestrator **always maximizes** the reported metric. You MUST:
1. Use the **exact same metric name(s) and calculation** as the \
parent experiment. Required metric(s): {metric_keys}
2. If the metric inverts a natural loss (e.g. `-RMSE`), keep the \
same inversion.
3. Do NOT rename, redefine, or add new primary metrics — results \
must be comparable.
4. Check the parent experiment with `luml-inspect` if unsure \
about the metric definition.

## Output Requirements

Your code must produce these when run via the run command:
- `.luml-agent/result.json` with metrics and experiment IDs (see guide.md)
- `.luml-agent/artifact.luml` — the LUML model artifact \
(e.g. `save_sklearn(model, X, path=".luml-agent/artifact.luml")`)

## Parent Experiments

The following experiment IDs are from the parent run. \
Use `luml-inspect show <id>` or `luml-inspect metrics <id> <key>` to explore them:
{experiment_ids}"""

_FORK = """\
# Decomposition Task

Analyze the results of the previous experiment and propose up to {max_children} \
diverse approaches to improve on it.

## Original Objective

{objective}

## Parent Experiments

The following experiment IDs are from the parent run. \
Use the bash tool to run `luml-inspect` commands and investigate them:
{experiment_ids}

For example:
- `luml-inspect show <id>` — full experiment details
- `luml-inspect metrics <id> <key>` — metric history
- `luml-inspect params <id>` — parameters used
- `luml-inspect compare <id1> <id2>` — side-by-side comparison

## CRITICAL RULES

1. **Do NOT modify any code files.** No changes to `.py`, `.toml`, \
`.json`, or any other source files. The ONLY file you create is \
`.luml-agent/fork.json`.
2. **Use `luml-inspect` via bash** to understand what the parent \
experiment did, what metrics it achieved, and what parameters it used.
3. Based on your analysis, write diverse proposals to \
`.luml-agent/fork.json`.

## Guidelines
- Explore diverse strategies (e.g. different algorithms, hyperparameter \
ranges, data preprocessing, feature engineering).
- Each proposal must be self-contained — an agent receiving only that \
proposal and the original objective should be able to implement it.
- Preserve metric consistency: instruct each proposal to use the exact \
same metric name(s) and calculation as the parent (the orchestrator \
always maximizes). Metric(s) to preserve: {metric_keys}
- Do NOT simply re-run the same approach with minor tweaks — each \
proposal should represent a meaningfully different direction.

## Output Format

Write ONLY `.luml-agent/fork.json` in the worktree root. \
No other files may be created or modified.

It must be a JSON array of objects with `"prompt"` (str) and \
`"title"` (str):

```json
[
  {{"prompt": "Detailed instruction for approach 1...", "title": "Short title"}},
  {{"prompt": "Detailed instruction for approach 2...", "title": "Short title"}}
]
```"""

_DEBUG = """\
# Debug Task

The previous run command failed.

## Failure Details
- Exit code: {exit_code}

## Original Objective

{objective}

## Changes Since Base Branch

```diff
{git_diff}
```

## Failure Logs (last {max_log_tail} chars)

```
{log_tail}
```

## Reference

{guide_ref}

## Guidelines
- Analyze the failure logs and the diff to identify the root cause.
- Fix the code so the run command succeeds.
- Preserve any existing experiment tracking code \
(ExperimentTracker usage, result.json output)."""


def _format_environment(
    worktree_path: str,
    base_branch: str,
    run_command: str = "",
) -> str:
    return _ENVIRONMENT_BLOCK.format(
        worktree_path=worktree_path,
        base_branch=base_branch,
        run_command=run_command or "(not configured)",
    )


def _is_fork_child(payload: dict[str, Any]) -> bool:
    return "proposal" in payload and isinstance(payload["proposal"], dict)


def build_implement_prompt(
    payload: dict[str, Any],
    run_config: dict[str, Any],
    *,
    worktree_path: str = "",
    base_branch: str = "",
) -> str:
    run_command = run_config.get("run_command_template", "")
    environment = _format_environment(worktree_path, base_branch, run_command)

    if _is_fork_child(payload):
        proposal = payload["proposal"]
        prompt_text = proposal.get("prompt", "")
        objective = payload.get("objective", "")
        metric_keys = payload.get("discovered_metric_keys", [])
        experiment_ids = payload.get("experiment_ids", [])

        metric_keys_str = ", ".join(metric_keys) if metric_keys else "(none specified)"
        exp_ids_str = (
            "\n".join(f"- {eid}" for eid in experiment_ids)
            if experiment_ids
            else "- (none available)"
        )

        return _IMPLEMENT_FORK_CHILD.format(
            proposal=_esc(prompt_text),
            objective=_esc(objective),
            environment=environment,
            guide_ref=_GUIDE_REF,
            metric_keys=_esc(metric_keys_str),
            experiment_ids=_esc(exp_ids_str),
        )

    objective = payload.get("prompt", "")
    return _IMPLEMENT_ROOT.format(
        objective=_esc(objective),
        environment=environment,
        run_command=_esc(run_command or "(not configured)"),
        guide_ref=_GUIDE_REF,
    )


def build_debug_prompt(
    payload: dict[str, Any],
    git_diff: str,
    failure_logs: str,
    run_config: dict[str, Any],
) -> str:
    max_log_tail = run_config.get("max_log_tail", 10000)
    failure_context = payload.get("failure_context", {})
    exit_code = failure_context.get("exit_code", "unknown")
    objective = payload.get("objective", "")

    if len(failure_logs) > max_log_tail:
        log_tail = failure_logs[-max_log_tail:]
    else:
        log_tail = failure_logs

    return _DEBUG.format(
        exit_code=exit_code,
        objective=_esc(objective),
        git_diff=_esc(git_diff),
        log_tail=_esc(log_tail),
        max_log_tail=max_log_tail,
        guide_ref=_GUIDE_REF,
    )


def build_fork_prompt(
    payload: dict[str, Any],
    run_config: dict[str, Any],
) -> str:
    objective = payload.get("objective", "")
    experiment_ids = payload.get("experiment_ids", [])
    metric_keys = payload.get("discovered_metric_keys", [])
    max_children = run_config.get("max_children_per_fork", 3)

    exp_ids_str = (
        "\n".join(f"- {eid}" for eid in experiment_ids)
        if experiment_ids
        else "- (none available)"
    )
    metric_keys_str = ", ".join(metric_keys) if metric_keys else "(none specified)"

    return _FORK.format(
        max_children=max_children,
        objective=_esc(objective),
        experiment_ids=_esc(exp_ids_str),
        metric_keys=_esc(metric_keys_str),
    )
