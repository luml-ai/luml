import os
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import typer

from lumlflow.flow import cli as flow_cli
from lumlflow.flow.daemon import workspace as daemon_workspace

if TYPE_CHECKING:
    from lumlflow.flow.daemon.workspace import DaemonRecord

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
NON_LOOPBACK_WARNING = daemon_workspace.NON_LOOPBACK_WARNING

app = typer.Typer(
    name="lumlflow",
    help="Local ML experiment tracking",
)

flow_cli.register(app)


@app.command()
def ui(
    directory: Path | None = typer.Argument(
        None,
        exists=True,
        file_okay=False,
        resolve_path=True,
        help="Directory whose flows to list.",
    ),
    path: str | None = typer.Option(
        None,
        "--path",
        help="Backend store URI (e.g. sqlite://./experiments)",
    ),
    host: str = typer.Option(
        DEFAULT_HOST,
        "--host",
        help=f"Host to serve on. {NON_LOOPBACK_WARNING}",
    ),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="Port to serve on."),
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Do not open the browser."
    ),
) -> None:
    """Open lumlflow on DIRECTORY's flows, starting the daemon when needed.

    With no daemon running, it serves http://127.0.0.1:5000 until Ctrl+C. When
    one is already running, it opens that daemon and exits.
    """
    from lumlflow.flow.daemon import client
    from lumlflow.flow.daemon import main as server
    from lumlflow.flow.errors import FlowError

    previous_store_environment: dict[str, str | None] = {}
    if path is not None:
        # The legacy alias has higher settings precedence, so an explicit CLI
        # value must override both aliases while this server is alive.
        for name in ("BACKEND_STORE_URI", "LUML_BACKEND_STORE_URI"):
            previous_store_environment[name] = os.environ.get(name)
            os.environ[name] = path

    launch_directory = (directory or Path.cwd()).resolve()
    try:
        tracker_store = _tracker_store()
        warning = daemon_workspace.network_filesystem_warning()
        if warning is not None:
            typer.echo(warning)
        serving = client.discover()
        if serving is not None:
            _attach(
                serving,
                directory=launch_directory,
                host=host,
                port=port,
                tracker_store=tracker_store,
                no_browser=no_browser,
            )
            return
        code = server.serve_here(
            launch_directory,
            web_host=host,
            web_port=port,
            announce=lambda record: _serving(
                record, directory=launch_directory, no_browser=no_browser
            ),
        )
        if code == server.ALREADY_RUNNING:
            serving = client.discover()
            if serving is not None:
                _attach(
                    serving,
                    directory=launch_directory,
                    host=host,
                    port=port,
                    tracker_store=tracker_store,
                    no_browser=no_browser,
                )
                return
    except FlowError as failure:
        typer.echo(str(failure), err=True)
        raise typer.Exit(1) from failure
    finally:
        for name, value in previous_store_environment.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    if code:
        raise typer.Exit(code)


def _serving(record: "DaemonRecord", *, directory: Path, no_browser: bool) -> None:
    """Said once this process is answering, from inside its own event loop."""
    _warn_if_non_loopback(record.web_host)
    typer.echo(f"directory: {directory}")
    typer.echo(f"lumlflow at {_url(record, directory)}")
    _show_log_path()
    typer.echo("press Ctrl+C to stop")
    if not no_browser:
        webbrowser.open(_url(record, directory))


def _attach(
    record: "DaemonRecord",
    *,
    directory: Path,
    host: str,
    port: int,
    tracker_store: str,
    no_browser: bool,
) -> None:
    """Point the browser at the daemon that is already serving.

    A port belongs to the process that bound it, so one that answers on
    another is said plainly rather than papered over — and never taken from
    a session somebody is using or a run somebody is waiting on.
    """
    from lumlflow.flow.errors import FlowError

    if record.tracker_store != tracker_store or record.web_host != host:
        raise FlowError(
            "lumlflow is already serving tracker store "
            f"`{record.tracker_store}` on host `{record.web_host}`. "
            "run `lumlflow daemon stop` before changing either setting"
        )
    if not record.web_port:
        typer.echo(
            "lumlflow is already running without a browser endpoint",
            err=True,
        )
        raise typer.Exit(1)
    _warn_if_non_loopback(record.web_host)
    typer.echo(f"lumlflow already at {_url(record, directory)}")
    _show_log_path()
    if record.web_port != port:
        typer.echo(f"it is serving port {record.web_port}, not {port}")
    if not no_browser:
        webbrowser.open(_url(record, directory))


def _tracker_store() -> str:
    from lumlflow.settings import Settings

    return Settings().BACKEND_STORE_URI  # type: ignore[call-arg]


def _url(record: "DaemonRecord", directory: Path) -> str:
    query = urlencode(
        {
            "token": record.token,
            "directory": str(directory.resolve()),
            "log": str(daemon_workspace.log_path()),
        }
    )
    return f"http://{record.web_host}:{record.web_port}/flow?{query}"


def _show_log_path() -> None:
    typer.echo(f"daemon log: {daemon_workspace.log_path()}")


def _warn_if_non_loopback(host: str) -> None:
    if not daemon_workspace.is_loopback_host(host):
        typer.echo(f"warning: {NON_LOOPBACK_WARNING}")


@app.command(
    context_settings={
        # The TUI accepts an optional positional script + arbitrary
        # pass-through args; we collect them via `script_args` and let
        # Typer ignore unknown options that belong to the script
        # (rather than treating `--epochs 10` as a `tui` option).
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    }
)
def tui(
    ctx: typer.Context,
    script: str | None = typer.Argument(
        None,
        help=(
            "Optional training script to run; the TUI shares its SQLite "
            "store via BACKEND_STORE_URI and auto-attaches to the experiment "
            "the script creates."
        ),
    ),
    path: str | None = typer.Option(
        None,
        "--path",
        help="Backend store URI (e.g. sqlite://./experiments)",
    ),
    refresh_interval: float = typer.Option(
        2.0,
        "--refresh-interval",
        help="Live auto-refresh interval (seconds)",
        min=0.1,
    ),
    no_auto_refresh: bool = typer.Option(
        False,
        "--no-auto-refresh",
        help="Start with auto-refresh disabled",
    ),
    attach_timeout: float = typer.Option(
        60.0,
        "--attach-timeout",
        help=(
            "Max seconds to wait for the launched script to create a "
            "new experiment before giving up auto-attach."
        ),
        min=1.0,
    ),
) -> None:
    if path is not None:
        os.environ["BACKEND_STORE_URI"] = path

    from lumlflow.settings import get_config

    try:
        from lumlflow.tui import LumlflowApp
        from lumlflow.tui.run_manager import RunSpec
    except ModuleNotFoundError as exc:
        # Only translate missing optional deps into a friendly hint;
        # re-raise genuine import bugs inside lumlflow itself.
        if exc.name is None or not exc.name.startswith(("textual", "plotext")):
            raise
        typer.echo(
            "The TUI requires optional dependencies. "
            "Install them with: pip install 'lumlflow[tui]'",
            err=True,
        )
        raise typer.Exit(code=1) from exc

    # `BACKEND_STORE_URI` after `parse_uri` is a filesystem path; the child
    # process expects a fully-qualified `sqlite://...` URI so its tracker
    # reads from the same store. Always prefix here (idempotently).
    raw = get_config().BACKEND_STORE_URI
    store_uri = raw if "://" in raw else f"sqlite://{raw}"
    typer.echo(f"Using experiment store: {raw}")

    run_spec: RunSpec | None = None
    if script is not None:
        run_spec = RunSpec(script=script, args=tuple(ctx.args))

    app_instance = LumlflowApp(
        refresh_interval=refresh_interval,
        auto_refresh=not no_auto_refresh,
        run_spec=run_spec,
        store_uri=store_uri,
        attach_timeout=attach_timeout,
    )
    app_instance.run()


@app.command()
def version() -> None:
    from lumlflow import __version__

    typer.echo(f"lumlflow {__version__}")


if __name__ == "__main__":
    app()
