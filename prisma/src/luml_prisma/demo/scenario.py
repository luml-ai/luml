"""Scenario model for scripted demo agents.

A scenario is a directory:

    <scenario>/
      scenario.toml        # metadata, playback config, steps
      repo/                # initial demo repository contents (init-repo)
      steps/<id>/
        narration.txt      # terminal playback script
        files/             # tree copied over the worktree when the step plays

Steps are matched against the orchestrator prompt (implement / fork / debug)
and the per-worktree state recorded in .prisma/demo-state.json.
"""

import json
import os
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STATE_DIR = ".prisma"
STATE_FILENAME = "demo-state.json"
FORK_FILENAME = "fork.json"
RESULT_FILENAME = "result.json"

IMPLEMENT = "implement"
FORK = "fork"
DEBUG = "debug"
_STEP_TYPES = frozenset({IMPLEMENT, FORK, DEBUG})

_FORK_MARKER = "# Decomposition Task"
_DEBUG_MARKER = "# Debug Task"


class ScenarioError(Exception):
    pass


@dataclass(frozen=True)
class Proposal:
    title: str
    prompt: str


@dataclass(frozen=True)
class PlaybackConfig:
    line_delay_ms: int = 200
    jitter_ms: int = 150
    char_delay_ms: int = 5


@dataclass(frozen=True)
class ScenarioStep:
    id: str
    step_type: str
    root: bool = False
    proposal: str = ""
    after_variant: str = ""
    variant: str = ""
    files_dir: str = ""
    narration_file: str = ""
    proposals: tuple[Proposal, ...] = ()
    result: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Scenario:
    name: str
    title: str
    agent_id: str
    agent_name: str
    objective: str
    run_command: str
    playback: PlaybackConfig
    steps: tuple[ScenarioStep, ...]
    root_dir: Path

    def step_dir(self, step: ScenarioStep) -> Path | None:
        if not step.files_dir:
            return None
        return self.root_dir / step.files_dir

    def narration_path(self, step: ScenarioStep) -> Path | None:
        if not step.narration_file:
            return None
        return self.root_dir / step.narration_file

    @property
    def repo_dir(self) -> Path:
        return self.root_dir / "repo"


def builtin_scenarios_dir() -> Path:
    return Path(__file__).parent / "scenarios"


def user_scenarios_dir() -> Path:
    return Path.home() / ".luml-prisma" / "demo-scenarios"


def scenario_search_dirs() -> list[Path]:
    dirs: list[Path] = []
    env_dir = os.environ.get("PRISMA_DEMO_SCENARIOS_DIR", "").strip()
    if env_dir:
        dirs.append(Path(env_dir))
    dirs.append(user_scenarios_dir())
    dirs.append(builtin_scenarios_dir())
    return dirs


def resolve_scenario_dir(name_or_path: str) -> Path:
    direct = Path(name_or_path)
    if direct.is_dir() and (direct / "scenario.toml").exists():
        return direct
    for base in scenario_search_dirs():
        candidate = base / name_or_path
        if (candidate / "scenario.toml").exists():
            return candidate
    raise ScenarioError(
        f"Scenario '{name_or_path}' not found. Searched: "
        + ", ".join(str(d) for d in scenario_search_dirs())
    )


def _parse_proposals(raw: list[dict[str, Any]], step_id: str) -> tuple[Proposal, ...]:
    proposals: list[Proposal] = []
    for entry in raw:
        title = entry.get("title", "")
        prompt = entry.get("prompt", "")
        if not title or not prompt:
            raise ScenarioError(
                f"Step '{step_id}': each proposal needs 'title' and 'prompt'"
            )
        proposals.append(Proposal(title=str(title), prompt=str(prompt)))
    return tuple(proposals)


def _parse_step(raw: dict[str, Any]) -> ScenarioStep:
    step_id = str(raw.get("id", ""))
    step_type = str(raw.get("type", ""))
    if not step_id:
        raise ScenarioError("Every step needs an 'id'")
    if step_type not in _STEP_TYPES:
        raise ScenarioError(
            f"Step '{step_id}': type must be one of {sorted(_STEP_TYPES)}"
        )
    result = raw.get("result", {})
    if not isinstance(result, dict):
        raise ScenarioError(f"Step '{step_id}': 'result' must be a table")
    return ScenarioStep(
        id=step_id,
        step_type=step_type,
        root=bool(raw.get("root", False)),
        proposal=str(raw.get("proposal", "")),
        after_variant=str(raw.get("after_variant", "")),
        variant=str(raw.get("variant", "")),
        files_dir=str(raw.get("files", "")),
        narration_file=str(raw.get("narration", "")),
        proposals=_parse_proposals(raw.get("proposals", []), step_id),
        result=result,
    )


def _validate(scenario: Scenario) -> None:
    seen: set[str] = set()
    for step in scenario.steps:
        if step.id in seen:
            raise ScenarioError(f"Duplicate step id '{step.id}'")
        seen.add(step.id)
        files_dir = scenario.step_dir(step)
        if files_dir is not None and not files_dir.is_dir():
            raise ScenarioError(
                f"Step '{step.id}': files dir not found: {files_dir}"
            )
        narration = scenario.narration_path(step)
        if narration is not None and not narration.is_file():
            raise ScenarioError(
                f"Step '{step.id}': narration file not found: {narration}"
            )
        if step.step_type == FORK and not step.proposals:
            raise ScenarioError(f"Fork step '{step.id}' needs at least one proposal")


def lint_scenario(scenario: Scenario) -> list[str]:
    """Soft checks beyond structural validation, for tests and `prisma-demo list`."""
    problems: list[str] = []
    implement_steps = [s for s in scenario.steps if s.step_type == IMPLEMENT]
    if not any(s.root for s in implement_steps):
        problems.append("No root implement step (root = true)")
    proposal_matchers = [s.proposal for s in implement_steps if s.proposal]
    for step in scenario.steps:
        for proposal in step.proposals:
            hits = [m for m in proposal_matchers
                    if m in proposal.title or m in proposal.prompt]
            if not hits:
                problems.append(
                    f"Fork step '{step.id}': proposal '{proposal.title}' "
                    "matches no implement step"
                )
            elif len(hits) > 1:
                problems.append(
                    f"Fork step '{step.id}': proposal '{proposal.title}' "
                    f"matches multiple implement steps ({', '.join(hits)}) — "
                    "make the matchers unique"
                )
    variants = {s.variant for s in scenario.steps if s.variant}
    for step in scenario.steps:
        if step.after_variant and step.after_variant not in variants | {"*"}:
            problems.append(
                f"Step '{step.id}': after_variant '{step.after_variant}' "
                "is never produced by any step"
            )
    return problems


def load_scenario(scenario_dir: Path) -> Scenario:
    toml_path = scenario_dir / "scenario.toml"
    try:
        data = tomllib.loads(toml_path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ScenarioError(f"Cannot read {toml_path}: {exc}") from exc

    meta = data.get("scenario", {})
    name = str(meta.get("name", scenario_dir.name))
    playback_raw = data.get("playback", {})
    playback = PlaybackConfig(
        line_delay_ms=int(playback_raw.get("line_delay_ms", 200)),
        jitter_ms=int(playback_raw.get("jitter_ms", 150)),
        char_delay_ms=int(playback_raw.get("char_delay_ms", 5)),
    )
    steps = tuple(_parse_step(raw) for raw in data.get("steps", []))
    if not steps:
        raise ScenarioError(f"Scenario '{name}' defines no steps")

    scenario = Scenario(
        name=name,
        title=str(meta.get("title", name)),
        agent_id=str(meta.get("agent_id", f"demo-{name}")),
        agent_name=str(meta.get("agent_name", f"Demo Agent — {name}")),
        objective=str(meta.get("objective", "")),
        run_command=str(meta.get("run_command", "uv run main.py")),
        playback=playback,
        steps=steps,
        root_dir=scenario_dir,
    )
    _validate(scenario)
    return scenario


def list_scenario_dirs() -> dict[str, Path]:
    """Scenario name -> dir; earlier search dirs shadow later ones."""
    found: dict[str, Path] = {}
    for base in scenario_search_dirs():
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if (child / "scenario.toml").exists() and child.name not in found:
                found[child.name] = child
    return found


def detect_step_type(prompt: str) -> str:
    if _FORK_MARKER in prompt:
        return FORK
    if _DEBUG_MARKER in prompt:
        return DEBUG
    return IMPLEMENT


def match_step(
    scenario: Scenario,
    step_type: str,
    prompt: str,
    variant: str,
) -> ScenarioStep | None:
    candidates = [s for s in scenario.steps if s.step_type == step_type]
    if step_type == IMPLEMENT:
        with_proposal = [s for s in candidates if s.proposal and s.proposal in prompt]
        if with_proposal:
            return max(with_proposal, key=lambda s: len(s.proposal))
        for step in candidates:
            if step.root:
                return step
        return _catch_all(candidates)
    for step in candidates:
        if step.after_variant and step.after_variant == variant:
            return step
    return _catch_all(candidates)


def _catch_all(candidates: list[ScenarioStep]) -> ScenarioStep | None:
    for step in candidates:
        if step.after_variant == "*":
            return step
    return None


def load_state(cwd: Path) -> dict[str, Any]:
    path = cwd / STATE_DIR / STATE_FILENAME
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(cwd: Path, state: dict[str, Any]) -> None:
    path = cwd / STATE_DIR / STATE_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))


def apply_step(scenario: Scenario, step: ScenarioStep, cwd: Path) -> None:
    """Apply a matched step's effects to the worktree (everything but narration)."""
    files_dir = scenario.step_dir(step)
    if files_dir is not None:
        shutil.copytree(files_dir, cwd, dirs_exist_ok=True)

    prisma_dir = cwd / STATE_DIR
    prisma_dir.mkdir(parents=True, exist_ok=True)

    if step.step_type == FORK:
        fork_payload = [{"title": p.title, "prompt": p.prompt} for p in step.proposals]
        (prisma_dir / FORK_FILENAME).write_text(json.dumps(fork_payload, indent=2))

    result: dict[str, Any] = {"success": True}
    result.update(step.result)
    (prisma_dir / RESULT_FILENAME).write_text(json.dumps(result, indent=2))

    state = load_state(cwd)
    if step.variant:
        state["variant"] = step.variant
    played = state.setdefault("played", [])
    if isinstance(played, list):
        played.append(step.id)
    save_state(cwd, state)
