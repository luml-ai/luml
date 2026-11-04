import pytest

from luml_prisma.services.orchestrator.prompts import (
    build_debug_prompt,
    build_fork_prompt,
    build_implement_prompt,
)


@pytest.mark.parametrize(
    "text",
    ['{"a": 1}', "{1, 2}", 'f"{value}"', "{{literal}}", "{unfinished"],
)
def test_debug_prompt_preserves_braces(text: str) -> None:
    objective = f"tune {text}"
    diff = f"+cfg = {text}"
    logs = f"failed with {text}"

    result = build_debug_prompt({"objective": objective}, diff, logs, {})

    assert f"\n{objective}\n" in result
    assert f"```diff\n{diff}\n```" in result
    assert f"```\n{logs}\n```" in result


def test_debug_prompt_preserves_braces_in_truncated_logs() -> None:
    log_tail = 'cfg = {"lr": 0.01}'

    result = build_debug_prompt(
        {}, "", f"discarded logs\n{log_tail}", {"max_log_tail": len(log_tail)}
    )

    assert f"```\n{log_tail}\n```" in result
    assert "discarded logs" not in result


def test_root_implement_prompt_preserves_braces() -> None:
    objective = 'tune {"a": 1}'
    run_command = "python train.py --config '{\"lr\": 0.01}'"

    result = build_implement_prompt(
        {"prompt": objective},
        {"run_command_template": run_command},
        worktree_path="/tmp/{worktree}",
        base_branch="feature/{branch}",
    )

    assert f"\n{objective}\n" in result
    assert result.count(f"`{run_command}`") == 2
    assert "- Worktree path: /tmp/{worktree}\n" in result
    assert "- Base branch: feature/{branch}\n" in result


def test_fork_child_implement_prompt_preserves_braces() -> None:
    proposal = 'use {"lr": 0.01}'
    objective = 'tune {"a": 1}'

    result = build_implement_prompt(
        {
            "proposal": {"prompt": proposal},
            "objective": objective,
            "discovered_metric_keys": ["accuracy_{split}"],
            "experiment_ids": ["exp-{id}"],
        },
        {},
    )

    assert f"\n{proposal}\n" in result
    assert f"\n> {objective}\n" in result
    assert "Required metric(s): accuracy_{split}\n" in result
    assert result.endswith("\n- exp-{id}")


def test_fork_prompt_preserves_braces_in_values_and_json_example() -> None:
    objective = 'tune {"a": 1}'

    result = build_fork_prompt(
        {
            "objective": objective,
            "discovered_metric_keys": ["accuracy_{split}"],
            "experiment_ids": ["exp-{id}"],
        },
        {},
    )

    assert f"\n{objective}\n" in result
    assert "\n- exp-{id}\n" in result
    assert "Metric(s) to preserve: accuracy_{split}\n" in result
    assert (
        '  {"prompt": "Detailed instruction for approach 1...", '
        '"title": "Short title"},'
    ) in result
