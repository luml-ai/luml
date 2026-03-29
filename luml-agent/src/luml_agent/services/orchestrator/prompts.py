from typing import Any

_GUIDE_REF = (
    "Refer to `.luml-agent/guide.md` in the worktree root "
    "for tooling, CLI usage, and output conventions."
)

_ENVIRONMENT_BLOCK = """\
## Environment
- Package manager: `uv`
- Worktree path: {worktree_path}
- Base branch: {base_branch}"""

_IMPLEMENT_ROOT = """\
# Objective

{objective}

{environment}

## Reference

{guide_ref}

## Guidelines
- Inspect the repository to understand the existing structure before writing code.
- Keep a persistent entrypoint (e.g. `main.py`) that can be run \
with the configured run command.
- Prefer simple, working solutions over complex ones.
- Write experiment tracking code using `luml` (see guide.md for details)."""

_IMPLEMENT_FORK_CHILD = """\
# Task

{proposal}

## Background Context

The original objective for this run (for context only — follow the task above):

> {objective}

{environment}

## Reference

{guide_ref}

## Metric Consistency

You MUST use the same metric name(s) and calculation as the parent experiment \
so results are comparable.
Required metric(s): {metric_keys}

## Parent Experiments

The following experiment IDs are from the parent run. \
Use `luml-inspect show <id>` or `luml-inspect metrics <id> <key>` to explore them:
{experiment_ids}"""

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
) -> str:
    return _ENVIRONMENT_BLOCK.format(
        worktree_path=worktree_path,
        base_branch=base_branch,
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
    environment = _format_environment(worktree_path, base_branch)

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
            proposal=prompt_text,
            objective=objective,
            environment=environment,
            guide_ref=_GUIDE_REF,
            metric_keys=metric_keys_str,
            experiment_ids=exp_ids_str,
        )

    objective = payload.get("prompt", "")
    return _IMPLEMENT_ROOT.format(
        objective=objective,
        environment=environment,
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
        objective=objective,
        git_diff=git_diff,
        log_tail=log_tail,
        max_log_tail=max_log_tail,
        guide_ref=_GUIDE_REF,
    )
