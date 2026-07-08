"""`prisma-demo` — dev helpers for preparing scripted live demos.

Typical flow:

    prisma-demo list
    prisma-demo install-agent autorag
    prisma-demo init-repo autorag ~/demos/autorag-repo
    prisma-demo runbook autorag
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import typer

from luml_prisma.demo.scenario import (
    Scenario,
    ScenarioError,
    lint_scenario,
    list_scenario_dirs,
    load_scenario,
    resolve_scenario_dir,
    user_scenarios_dir,
)

AGENT_CLI = "prisma-demo-agent"

app = typer.Typer(
    name="prisma-demo",
    help="Prepare scripted prisma demos: scenario agents and demo repositories.",
    no_args_is_help=True,
)


def _custom_agents_path() -> Path:
    return Path.home() / ".luml-prisma" / "coding-clis.json"


def _load_scenario_or_exit(name: str) -> Scenario:
    try:
        return load_scenario(resolve_scenario_dir(name))
    except ScenarioError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc


def _read_custom_agents(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


@app.command("list")
def list_scenarios() -> None:
    """List resolvable demo scenarios and any lint problems."""
    dirs = list_scenario_dirs()
    if not dirs:
        typer.echo("No scenarios found.")
        return
    for name, path in dirs.items():
        try:
            scenario = load_scenario(path)
        except ScenarioError as exc:
            typer.secho(f"{name}: INVALID — {exc}", fg=typer.colors.RED)
            continue
        typer.echo(f"{name}: {scenario.title}")
        typer.echo(f"  dir: {path}")
        typer.echo(f"  agent: {scenario.agent_name} (id={scenario.agent_id})")
        typer.echo(f"  steps: {len(scenario.steps)}")
        for problem in lint_scenario(scenario):
            typer.secho(f"  lint: {problem}", fg=typer.colors.YELLOW)


@app.command("install-agent")
def install_agent(
    name: str,
    speed: float | None = typer.Option(
        None, help="Bake a playback speed multiplier into the agent entry."
    ),
) -> None:
    """Register the scenario as a selectable agent in the prisma UI."""
    scenario = _load_scenario_or_exit(name)
    path = _custom_agents_path()
    agents = _read_custom_agents(path)
    agents = [a for a in agents if a.get("id") != scenario.agent_id]
    default_args = ["--scenario", name]
    if speed is not None:
        default_args += ["--speed", str(speed)]
    agents.append({
        "id": scenario.agent_id,
        "name": scenario.agent_name,
        "cli": AGENT_CLI,
        "default_args": default_args,
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(agents, indent=2))
    typer.secho(
        f"Installed agent '{scenario.agent_name}' (id={scenario.agent_id})",
        fg=typer.colors.GREEN,
    )
    if shutil.which(AGENT_CLI) is None:
        typer.secho(
            f"WARNING: '{AGENT_CLI}' is not on PATH. The agent only appears in "
            "the UI when the prisma server can find it — start the server from "
            "an environment where luml-prisma is installed (e.g. `uv run`).",
            fg=typer.colors.YELLOW,
        )
    typer.echo(f"\nNext: prisma-demo runbook {name}")


@app.command("uninstall-agent")
def uninstall_agent(name: str) -> None:
    """Remove the scenario's agent entry."""
    scenario = _load_scenario_or_exit(name)
    path = _custom_agents_path()
    agents = _read_custom_agents(path)
    remaining = [a for a in agents if a.get("id") != scenario.agent_id]
    if len(remaining) == len(agents):
        typer.echo(f"No agent entry for id={scenario.agent_id}")
        return
    path.write_text(json.dumps(remaining, indent=2))
    typer.secho(f"Removed agent id={scenario.agent_id}", fg=typer.colors.GREEN)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True)


def _git_identity_args(repo: Path) -> list[str]:
    probe = subprocess.run(
        ["git", "-C", str(repo), "config", "user.email"],
        capture_output=True, text=True, check=False,
    )
    if probe.stdout.strip():
        return []
    return [
        "-c", "user.name=prisma-demo",
        "-c", "user.email=prisma-demo@localhost",
    ]


@app.command("init-repo")
def init_repo(
    name: str,
    path: Path,
    sync: bool = typer.Option(
        True, help="Run `uv lock` + `uv sync` to warm caches for fast run nodes."
    ),
) -> None:
    """Materialize the scenario's demo repository at PATH (git init + commit)."""
    scenario = _load_scenario_or_exit(name)
    if not scenario.repo_dir.is_dir():
        typer.secho(
            f"Scenario '{name}' has no repo/ directory", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(1)
    if path.exists() and any(path.iterdir()):
        typer.secho(f"{path} exists and is not empty", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    shutil.copytree(scenario.repo_dir, path, dirs_exist_ok=True)
    _git(path, "init", "-b", "main")
    if sync and shutil.which("uv") is not None and (path / "pyproject.toml").exists():
        typer.echo("Running uv lock && uv sync (warms caches for run nodes)...")
        subprocess.run(["uv", "lock"], cwd=path, check=True)
        subprocess.run(["uv", "sync"], cwd=path, check=True)
    _git(path, "add", "-A")
    identity = _git_identity_args(path)
    subprocess.run(
        ["git", "-C", str(path), *identity, "commit", "-m",
         f"Initial commit — {scenario.title}"],
        check=True,
    )
    typer.secho(f"Demo repository ready at {path}", fg=typer.colors.GREEN)
    typer.echo("Register it in the prisma UI (Repositories → Add) using this path.")


def _check_experiments_store() -> str | None:
    """Initialize the shared experiments store the way run nodes will.

    Returns an error message when the store cannot be opened/migrated (e.g. a
    meta.db created by an older luml-sdk whose migration path fails).
    """
    try:
        from luml.experiments.tracker import ExperimentTracker
    except ImportError as exc:
        return f"luml-sdk not importable: {exc}"
    store = Path.home() / ".prisma" / "experiments"
    try:
        store.mkdir(parents=True, exist_ok=True)
        ExperimentTracker(f"sqlite://{store}")
    except Exception as exc:  # any store failure must be reported, not raised
        return f"{type(exc).__name__}: {exc}"
    return None


@app.command("doctor")
def doctor(name: str = typer.Argument("autorag")) -> None:
    """Preflight checks — run this before going live."""
    failures: list[str] = []

    def report(label: str, error: str | None) -> None:
        if error is None:
            typer.secho(f"  ok    {label}", fg=typer.colors.GREEN)
        else:
            typer.secho(f"  FAIL  {label}: {error}", fg=typer.colors.RED)
            failures.append(label)

    scenario: Scenario | None = None
    try:
        scenario = load_scenario(resolve_scenario_dir(name))
        report(f"scenario '{name}'", None)
    except ScenarioError as exc:
        report(f"scenario '{name}'", str(exc))

    if scenario is not None:
        lint = lint_scenario(scenario)
        report("scenario lint", "; ".join(lint) if lint else None)
        agents = _read_custom_agents(_custom_agents_path())
        installed = any(a.get("id") == scenario.agent_id for a in agents)
        report(
            f"agent entry '{scenario.agent_id}'",
            None if installed
            else f"not installed — run: prisma-demo install-agent {name}",
        )

    report(
        f"'{AGENT_CLI}' on PATH",
        None if shutil.which(AGENT_CLI) else
        "not found — start the prisma server from an env with luml-prisma installed",
    )
    for tool in ("uv", "git"):
        report(f"'{tool}' on PATH", None if shutil.which(tool) else "not found")

    store_error = _check_experiments_store()
    report("experiments store (~/.prisma/experiments)", store_error)
    if store_error is not None:
        typer.echo(
            "        The store cannot be opened by the luml-sdk version the demo "
            "uses.\n        Remedy: back it up out of the way and let a fresh one "
            "be created:\n"
            "          mv ~/.prisma/experiments ~/.prisma/experiments.bak",
        )

    if failures:
        typer.secho(f"\n{len(failures)} check(s) failed.", fg=typer.colors.RED)
        raise typer.Exit(1)
    typer.secho("\nAll checks passed — demo ready.", fg=typer.colors.GREEN)


@app.command("runbook")
def runbook(name: str) -> None:
    """Print the exact settings and commands for running this demo live."""
    scenario = _load_scenario_or_exit(name)
    max_children = max(
        (len(s.proposals) for s in scenario.steps if s.proposals), default=2,
    )
    lines = [
        f"# Runbook — {scenario.title}",
        "",
        "0. Preflight (catches broken experiment stores, missing tools):",
        f"     prisma-demo doctor {scenario.name}",
        "",
        "1. Install the agent and demo repository:",
        f"     prisma-demo install-agent {scenario.name}",
        f"     prisma-demo init-repo {scenario.name} <repo-path>",
        "",
        "2. Start the prisma server from an env where luml-prisma is installed",
        "   (the agent CLI must be on the server's PATH):",
        "     uv run luml-prisma",
        "   Optional pacing override for rehearsal: PRISMA_DEMO_SPEED=0.3",
        "",
        "3. In the platform UI (/prisma): register <repo-path> under",
        "   Repositories, then create a Workflow with:",
        f"     Agent:                  {scenario.agent_name}",
        f"     Run command:            {scenario.run_command}",
        "     Max depth:              2",
        f"     Max children per fork:  {max_children}",
        "     Auto mode:              on",
        "     Collection:             (pick one to demo the registry upload)",
        "",
    ]
    if scenario.objective:
        lines += [
            "4. Objective to paste:",
            "",
            *(f"     {ln}" for ln in scenario.objective.strip().splitlines()),
            "",
        ]
    lines += [
        "5. Experiments & traces (written by the run nodes for real):",
        "     uvx lumlflow ui --path ~/.prisma/experiments",
    ]
    typer.echo("\n".join(lines))


_SCENARIO_TEMPLATE = """\
[scenario]
name = "{name}"
title = "{name} demo"
agent_name = "Demo Agent — {name}"
# agent_id = "demo-{name}"          # id used in coding-clis.json
# objective = "Paste-ready objective shown by `prisma-demo runbook`."
# run_command = "uv run main.py"

[playback]
line_delay_ms = 200
jitter_ms = 150
char_delay_ms = 5

# Root implement step: plays when the orchestrator sends the initial objective.
[[steps]]
id = "baseline"
type = "implement"
root = true
variant = "baseline"                # recorded in .prisma/demo-state.json
files = "steps/baseline/files"      # tree copied over the worktree
narration = "steps/baseline/narration.txt"

# Fork step: matched by the variant recorded by the previous implement step.
# Writes .prisma/fork.json; each proposal spawns an implement child whose
# prompt contains the proposal text, matched via the child step's `proposal`.
[[steps]]
id = "fork-1"
type = "fork"
after_variant = "baseline"
narration = "steps/fork-1/narration.txt"

[[steps.proposals]]
title = "improved-approach"
prompt = "Implement the improved approach ..."

[[steps]]
id = "improved"
type = "implement"
proposal = "improved-approach"      # substring of the child prompt
variant = "improved"
files = "steps/improved/files"
narration = "steps/improved/narration.txt"

# Optional: a debug step plays when a run node fails for the given variant.
# [[steps]]
# id = "improved-debug"
# type = "debug"
# after_variant = "improved"
# files = "steps/improved-debug/files"
# narration = "steps/improved-debug/narration.txt"
"""

_NARRATION_TEMPLATE = """\
Reading the repository structure...
@sleep 0.8
Implementing the {step} step.
"""


@app.command("new-scenario")
def new_scenario(name: str) -> None:
    """Scaffold a new scenario under ~/.luml-prisma/demo-scenarios/."""
    target = user_scenarios_dir() / name
    if target.exists():
        typer.secho(f"{target} already exists", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    for step in ("baseline", "fork-1", "improved"):
        (target / "steps" / step / "files").mkdir(parents=True)
        (target / "steps" / step / "narration.txt").write_text(
            _NARRATION_TEMPLATE.format(step=step)
        )
    (target / "repo").mkdir()
    (target / "scenario.toml").write_text(_SCENARIO_TEMPLATE.format(name=name))
    typer.secho(f"Scenario scaffold created at {target}", fg=typer.colors.GREEN)
    typer.echo("Fill in repo/, steps/*/files/, and the narrations, then:")
    typer.echo(f"  prisma-demo install-agent {name}")


def main() -> None:
    try:
        app()
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(f"Command failed: {exc}\n")
        sys.exit(1)
