"""`prisma-demo-agent` — scripted stand-in for a coding agent CLI.

Invoked by the prisma orchestrator exactly like a real agent
(`prisma-demo-agent --scenario <name> '<prompt>'`). It detects the step type
from the orchestrator prompt, matches a scenario step, plays its narration
into the PTY, applies the step's file tree to the worktree, and writes the
`.prisma/fork.json` / `.prisma/result.json` contract files.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from luml_prisma.demo.playback import play_narration, resolve_speed
from luml_prisma.demo.scenario import (
    RESULT_FILENAME,
    STATE_DIR,
    Scenario,
    ScenarioError,
    ScenarioStep,
    apply_step,
    detect_step_type,
    load_scenario,
    load_state,
    match_step,
    resolve_scenario_dir,
)


@dataclass(frozen=True)
class AgentInvocation:
    scenario: str
    speed: float | None
    prompt: str


def parse_args(argv: list[str]) -> AgentInvocation:
    scenario = ""
    speed: float | None = None
    prompt_parts: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--scenario" and i + 1 < len(argv):
            scenario = argv[i + 1]
            i += 2
        elif arg == "--speed" and i + 1 < len(argv):
            try:
                speed = float(argv[i + 1])
            except ValueError:
                speed = None
            i += 2
        else:
            prompt_parts.append(arg)
            i += 1
    return AgentInvocation(
        scenario=scenario,
        speed=speed,
        prompt=" ".join(prompt_parts),
    )


def _write_failure(cwd: Path, message: str) -> None:
    prisma_dir = cwd / STATE_DIR
    prisma_dir.mkdir(parents=True, exist_ok=True)
    (prisma_dir / RESULT_FILENAME).write_text(
        json.dumps({"success": False, "error_message": message})
    )


def _fail(cwd: Path, message: str) -> int:
    sys.stderr.write(f"prisma-demo-agent: {message}\n")
    _write_failure(cwd, message)
    return 1


def execute_step(
    scenario: Scenario,
    step: ScenarioStep,
    cwd: Path,
    speed: float,
) -> None:
    narration = scenario.narration_path(step)
    if narration is not None:
        play_narration(narration, scenario.playback, speed)
    apply_step(scenario, step, cwd)


def run(argv: list[str]) -> int:
    invocation = parse_args(argv)
    cwd = Path.cwd()
    if not invocation.scenario:
        sys.stderr.write(
            "prisma-demo-agent: missing --scenario <name>. "
            "Install via `prisma-demo install-agent <name>`.\n"
        )
        return 2
    try:
        scenario = load_scenario(resolve_scenario_dir(invocation.scenario))
    except ScenarioError as exc:
        return _fail(cwd, str(exc))

    step_type = detect_step_type(invocation.prompt)
    variant = str(load_state(cwd).get("variant", ""))
    step = match_step(scenario, step_type, invocation.prompt, variant)
    if step is None:
        return _fail(
            cwd,
            f"scenario '{scenario.name}' has no {step_type} step for "
            f"variant='{variant or '(none)'}'. Check the workflow settings "
            "against `prisma-demo runbook`.",
        )

    execute_step(scenario, step, cwd, resolve_speed(invocation.speed))
    return 0


def main() -> None:
    sys.exit(run(sys.argv[1:]))
