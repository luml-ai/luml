import json
import os
import random
import string
import sys
from pathlib import Path
from time import sleep
from typing import Any

_DEBUG_ENV_VAR = "LUML_PRISMA_ENABLE_MOCK_AGENT"

STATE_DIR = ".prisma"
STATE_FILE = "mock-state.json"
RESULT_FILE = "result.json"



def detect_step_type(args: list[str]) -> str:
    if not args:
        return "implement"
    prompt = " ".join(args)
    if args[0] == "run":
        return "run"
    if "Decompose the following objective" in prompt:
        return "fork"
    if "previous run command failed" in prompt:
        return "debug"
    return "implement"



class StepHandler:
    step_type: str = "base"

    def execute(self, cwd: Path, step_number: int) -> int:
        _write_result(cwd, {"success": True})
        return 0


class ImplementStepHandler(StepHandler):
    step_type = "implement"

    def execute(self, cwd: Path, step_number: int) -> int:
        (cwd / "step.py").write_text(f"# implement step {step_number}\n")
        metric = round(random.uniform(0.5, 1.0), 4)
        _write_result(cwd, {"success": True, "artifacts": {"metric": metric}})
        return 0


class RunStepHandler(StepHandler):
    step_type = "run"

    def execute(self, cwd: Path, step_number: int) -> int:
        metric = round(random.uniform(0.5, 1.0), 4)
        print(json.dumps({"type": "prisma-message", "metric": metric}), flush=True)  # noqa: T201
        _write_result(cwd, {
            "success": True,
            "metrics": {"passed": 1, "failed": 0},
            "artifacts": {"metric": metric},
        })
        return 0


class DebugStepHandler(StepHandler):
    step_type = "debug"

    def execute(self, cwd: Path, step_number: int) -> int:
        (cwd / "step.py").write_text(f"# debug step {step_number}\n")
        _write_result(cwd, {"success": True})
        return 0


class ForkStepHandler(StepHandler):
    step_type = "fork"

    def execute(self, cwd: Path, step_number: int) -> int:
        labels = [
            "".join(random.choices(string.ascii_lowercase, k=8)) for _ in range(4)
        ]
        (cwd / ".luml-fork.json").write_text(json.dumps(labels))
        proposals = [{"title": s, "prompt": f"Implement {s}"} for s in labels]
        _write_result(cwd, {"success": True, "proposals": proposals})
        return 0


HANDLERS: dict[str, StepHandler] = {
    "implement": ImplementStepHandler(),
    "run": RunStepHandler(),
    "debug": DebugStepHandler(),
    "fork": ForkStepHandler(),
}



def _load_state(cwd: Path) -> dict[str, int]:
    path = cwd / STATE_DIR / STATE_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(cwd: Path, state: dict[str, int]) -> None:
    path = cwd / STATE_DIR / STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state))


def _write_result(cwd: Path, result: dict[str, Any]) -> None:
    path = cwd / STATE_DIR / RESULT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result))



def _interactive_loop() -> None:
    while True:
        try:
            line = input("> ")
        except EOFError:
            break
        if line == "/exit":
            break
        print(line)  # noqa: T201


def run(args: list[str] | None = None) -> int:
    if args is None:
        args = []

    cwd = Path.cwd()
    step_type = detect_step_type(args)

    state = _load_state(cwd)
    step_number = state.get(step_type, 0) + 1
    state[step_type] = step_number
    _save_state(cwd, state)

    handler = HANDLERS.get(step_type, StepHandler())
    print(f"[mock-agent] step_type={step_type} step={step_number}", flush=True)  # noqa: T201
    for i in range(10):
        sleep(1)
        print(f"[mock-agent] working... ({i + 1}/10)", flush=True)  # noqa: T201

    exit_code = handler.execute(cwd, step_number)
    _interactive_loop()
    return exit_code


_DEBUG_ENABLED_VALUES = {"1", "true", "yes", "on"}


def main() -> None:
    enabled = os.environ.get(_DEBUG_ENV_VAR, "").strip().lower()
    if enabled not in _DEBUG_ENABLED_VALUES:
        sys.stderr.write(
            f"mock-agent is a debug-only entry point; "
            f"set {_DEBUG_ENV_VAR}=1 to enable.\n"
        )
        sys.exit(2)
    sys.exit(run(sys.argv[1:]))
