"""``luml-mlflow`` CLI.

Two commands cover the operational surface:

* ``sync`` — upload one or more pending runs to their orbit. Selects work via
  ``--run``, ``--experiment``, or ``--all`` (mutually exclusive); ``--force``
  re-uploads runs that are already ``uploaded``.
* ``status`` — print a run's current upload state (``not_uploaded`` /
  ``uploading`` / ``uploaded`` / ``failed`` / ``unknown``) and any recorded
  artifact urls.

Local-only runs (``luml://local``) are honored across every path: the sync
layer no-ops on them and the CLI surfaces that as a ``skipped`` line.
"""

from __future__ import annotations

import importlib

import typer

from luml_mlflow.sync import SyncResult

# ``luml_mlflow.sync`` is overloaded — the package re-exports a function with the
# same name as the submodule. ``importlib`` gives the module explicitly.
_sync_mod = importlib.import_module("luml_mlflow.sync")

app = typer.Typer(
    name="luml-mlflow",
    help="Sync MLflow runs tracked by luml-mlflow to a luml orbit.",
    no_args_is_help=True,
)


@app.command()
def sync(
    run: str | None = typer.Option(
        None, "--run", help="Sync a single MLflow run by id."
    ),
    experiment: str | None = typer.Option(
        None,
        "--experiment",
        help="Sync every pending run of an MLflow experiment (name or id).",
    ),
    all_runs: bool = typer.Option(
        False, "--all", help="Sync every pending run across every experiment."
    ),
    tracking_uri: str | None = typer.Option(
        None,
        "--tracking-uri",
        help="Tracking URI used to resolve the target if the run has none.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-upload runs that are already 'uploaded'.",
    ),
) -> None:
    """Upload pending runs to their orbit."""
    selectors = sum([run is not None, experiment is not None, all_runs])
    if selectors == 0:
        raise typer.BadParameter("Pass exactly one of --run, --experiment, or --all.")
    if selectors > 1:
        raise typer.BadParameter(
            "--run, --experiment, and --all are mutually exclusive."
        )

    if run is not None:
        results = [_sync_mod.sync(run, tracking_uri=tracking_uri, force=force)]
    elif experiment is not None:
        results = _sync_mod.sync_experiment(
            experiment, tracking_uri=tracking_uri, force=force
        )
    else:
        results = _sync_all(tracking_uri=tracking_uri, force=force)

    if not results:
        typer.echo("No runs to sync.")
        return

    failures = 0
    for result in results:
        if result.skipped_reason is not None:
            typer.echo(f"{result.run_id}: skipped ({result.skipped_reason})")
        elif result.error is not None:
            failures += 1
            typer.echo(f"{result.run_id}: failed ({result.error})", err=True)
        else:
            urls = ", ".join(result.artifact_urls) or "(no urls)"
            typer.echo(f"{result.run_id}: {result.status} -> {urls}")

    if failures:
        raise typer.Exit(code=1)


@app.command()
def status(
    run: str = typer.Option(..., "--run", help="The MLflow run id to inspect."),
) -> None:
    """Print a run's current upload state."""
    snap = _sync_mod.status(run)
    typer.echo(f"run: {snap.run_id}")
    typer.echo(f"status: {snap.status}")
    if snap.collection_id:
        typer.echo(f"collection: {snap.collection_id}")
    if snap.artifact_ids:
        typer.echo(f"artifact_ids: {', '.join(snap.artifact_ids)}")
    if snap.artifact_urls:
        typer.echo(f"artifact_urls: {', '.join(snap.artifact_urls)}")
    if snap.error:
        typer.echo(f"error: {snap.error}", err=True)


def _sync_all(*, tracking_uri: str | None, force: bool) -> list[SyncResult]:
    """Sync every pending, non-local run across every experiment."""
    from luml_mlflow._tracker import get_tracker

    tracker = get_tracker()
    results: list[SyncResult] = []
    for record in tracker.list_experiments():
        results.append(
            _sync_mod.sync(record.id, tracking_uri=tracking_uri, force=force)
        )
    return results


if __name__ == "__main__":
    app()
