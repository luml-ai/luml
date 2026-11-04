from pathlib import Path
from typing import cast

import yaml

WORKFLOW = (
    Path(__file__).resolve().parents[4]
    / ".github"
    / "workflows"
    / "[lumlflow] tests-and-linters.yml"
)


def test_frontend_ci_runs_required_checks_in_order() -> None:
    workflow = cast(
        dict[str, object],
        yaml.load(WORKFLOW.read_text("utf-8"), Loader=yaml.BaseLoader),
    )
    triggers = cast(dict[str, object], workflow["on"])
    pull_request = cast(dict[str, object], triggers["pull_request"])
    paths = cast(list[str], pull_request["paths"])
    assert "lumlflow/**" in paths

    jobs = cast(dict[str, dict[str, object]], workflow["jobs"])
    assert _commands(jobs["lint"]) == [
        "npm ci",
        "npx eslint .",
        "npm run format:check",
    ]
    assert _commands(jobs["unit"]) == [
        "npm ci --include=optional",
        "npm install @rollup/rollup-linux-x64-gnu --workspace=lumlflow/frontend",
        "npm run build-only --workspace=@luml/attachments",
        "npm run build-only --workspace=@luml/experiments",
        "npm run type-check",
        "npm run test:ci",
        "npx vite build",
    ]
    unit_steps = cast(list[dict[str, object]], jobs["unit"]["steps"])
    assert all("continue-on-error" not in step for step in unit_steps)
    assert all(
        step.get("working-directory") == "lumlflow/frontend" for step in unit_steps[-3:]
    )


def _commands(job: dict[str, object]) -> list[str]:
    commands: list[str] = []
    for step in cast(list[dict[str, object]], job["steps"]):
        run = step.get("run")
        if isinstance(run, str):
            commands.extend(line.strip() for line in run.splitlines() if line.strip())
    return commands
