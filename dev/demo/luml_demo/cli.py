"""`luml-demo` — prepare, inspect and tear down the local end-to-end demo."""

from __future__ import annotations

import typer

from luml_demo import phases
from luml_demo.config import SCENARIOS, DemoConfig
from luml_demo.shell import say
from luml_demo.state import DemoState

app = typer.Typer(
    name="luml-demo",
    help="One command that prepares the whole LUML demo locally: platform, satellites, "
    "Prisma research runs, registry versions, deployments and monitoring history.",
    no_args_is_help=True,
)
prisma_app = typer.Typer(help="Manage the local Prisma engine used by the demo.")
app.add_typer(prisma_app, name="prisma")


def _load() -> tuple[DemoConfig, DemoState]:
    config = DemoConfig()
    return config, DemoState.load(config.state_path)


@app.command()
def up(
    skip_platform: bool = typer.Option(False, help="Assume the platform stack is already running."),
    skip_satellites: bool = typer.Option(False, help="Skip satellite stacks and deployments."),
    skip_prisma: bool = typer.Option(False, help="Skip the headless Prisma runs (reuse recorded runs)."),
    skip_history: bool = typer.Option(False, help="Skip backfilling monitoring history."),
    rebuild_images: bool = typer.Option(False, help="Rebuild the satellite and model images."),
) -> None:
    """Prepare everything: platform, account, satellites, Prisma runs, registry, deployments, history."""
    config, state = _load()
    phases.ensure_platform(config, state, skip=skip_platform)
    phases.ensure_account(config, state)
    phases.ensure_orbit(config, state)
    if not skip_satellites:
        phases.ensure_satellites(config, state, rebuild_images=rebuild_images)
    if not skip_prisma:
        phases.run_prisma_scenarios(config, state)
    phases.publish_registry(config, state)
    if not skip_satellites:
        phases.ensure_deployments(config, state)
        if not skip_history:
            phases.backfill_history(config, state)
    phases.start_live_engine(config, state)
    typer.echo(phases.runbook_text(config, state))


@app.command()
def down(
    volumes: bool = typer.Option(False, help="Also delete the platform and satellite data volumes."),
    keep_platform: bool = typer.Option(False, help="Leave the platform stack running."),
) -> None:
    """Stop the demo: undeploy, stop satellites and the Prisma engine, stop the platform."""
    config, state = _load()
    phases.teardown(config, state, volumes=volumes, keep_platform=keep_platform)


@app.command()
def status() -> None:
    """Show what is prepared and where to click."""
    config, state = _load()
    typer.echo(phases.status_text(config, state))


@app.command()
def runbook() -> None:
    """Print the live-demo runbook: URLs, logins and the order of screens."""
    config, state = _load()
    typer.echo(phases.runbook_text(config, state))


@app.command()
def traffic(
    scenario: str = typer.Option("churn", help=f"One of {[s.name for s in SCENARIOS]}."),
    minutes: float = typer.Option(10.0, help="How long to keep sending requests."),
    per_minute: float = typer.Option(90.0, help="Average requests per minute (keep well above 60: "
                                                "drift is scored per five-minute window)."),
    drift: bool = typer.Option(True, help="Send the drifted traffic mix instead of the reference mix."),
) -> None:
    """Send live inference traffic through a deployment while the demo is on screen."""
    config, state = _load()
    phases.live_traffic(config, state, scenario=scenario, minutes=minutes, per_minute=per_minute,
                        drift=drift)


@app.command()
def history(
    scenario: str = typer.Option("churn", help=f"One of {[s.name for s in SCENARIOS]}."),
    hours: int = typer.Option(0, help="Hours of history to backfill (0 = configured default)."),
) -> None:
    """(Re)backfill monitoring history for a scenario's production deployment."""
    config, state = _load()
    phases.backfill_history(config, state, only=scenario, hours=hours or None)


@prisma_app.command("start")
def prisma_start(speed: float = typer.Option(0.0, help="Narration speed; 0 = configured default.")) -> None:
    """Start the Prisma engine with the demo agents on its PATH."""
    config, state = _load()
    phases.start_live_engine(config, state, speed=speed or None)


@prisma_app.command("stop")
def prisma_stop() -> None:
    """Stop the Prisma engine started by luml-demo."""
    config, _ = _load()
    phases.stop_engine(config)
    say("done")


def main() -> None:
    app()
