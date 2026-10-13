from pathlib import Path
from typing import cast

import yaml

WORKFLOW = (
    Path(__file__).resolve().parents[2]
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

    jobs = cast(dict[str, object], workflow["jobs"])
    frontend = cast(dict[str, object], jobs["frontend"])
    steps = cast(list[dict[str, object]], frontend["steps"])

    commands: list[str] = []
    for step in steps:
        run = step.get("run")
        if isinstance(run, str):
            commands.extend(line.strip() for line in run.splitlines() if line.strip())

    assert commands == [
        "npm ci",
        "npm run build --workspace=@luml/experiments",
        "npm run build --workspace=@luml/attachments",
        "npx vue-tsc --build",
        "npx eslint .",
        "npx vitest run --config vitest.config.ts",
        "npx vite build",
    ]
    assert all("continue-on-error" not in step for step in steps)
    assert all(
        step.get("working-directory") == "lumlflow/frontend" for step in steps[-4:]
    )
