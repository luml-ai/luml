import contextlib
import os
import shutil
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from lumlflow.flow import cli as flow_cli

if TYPE_CHECKING:
    from lumlflow.flow.daemon.workspace import DaemonRecord

DEFAULT_PORT = 5000

app = typer.Typer(
    name="lumlflow",
    help="Local ML experiment tracking",
)

flow_cli.register(app)


@app.command()
def ui(
    path: str | None = typer.Option(
        None,
        "--path",
        help="Backend store URI (e.g. sqlite://./experiments)",
    ),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="Port to serve on."),
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Do not open the browser."
    ),
) -> None:
    """Start lumlflow: Experiments, and this workspace's flows.

    It serves http://127.0.0.1:5000, or the port `--port` names. It keeps
    running until you stop it with Ctrl+C. Start a second one in the same
    workspace and it opens the browser on the one already serving.
    """
    from lumlflow.flow.daemon import client, workspace
    from lumlflow.flow.daemon import main as server
    from lumlflow.flow.errors import FlowError

    if path is not None:
        # Read out of the environment by the store this process is about to
        # serve; one already serving keeps the store it was started with.
        os.environ["BACKEND_STORE_URI"] = path

    _refresh_web_app(Path(__file__).resolve().parent)

    root = workspace.resolve_root(Path.cwd())
    try:
        serving = client.live_record(root)
        if serving is not None and not client.stand_down(serving):
            _attach(serving, port=port, no_browser=no_browser)
            return
        code = server.serve_here(
            root,
            web_port=port,
            announce=lambda record: _serving(record, no_browser=no_browser),
        )
    except FlowError as failure:
        typer.echo(str(failure), err=True)
        raise typer.Exit(1) from failure
    if code:
        raise typer.Exit(code)


def _serving(record: "DaemonRecord", *, no_browser: bool) -> None:
    """Said once this process is answering, from inside its own event loop."""
    typer.echo(f"workspace: {record.workspace}")
    typer.echo(f"lumlflow at {_url(record)}")
    typer.echo("press Ctrl+C to stop")
    if not no_browser:
        webbrowser.open(_url(record))


def _attach(record: "DaemonRecord", *, port: int, no_browser: bool) -> None:
    """Point the browser at what is already serving this workspace.

    A port belongs to the process that bound it, so one that answers on
    another is said plainly rather than papered over — and never taken from
    a session somebody is using or a run somebody is waiting on.
    """
    if not record.web_port:
        typer.echo(
            f"lumlflow is already running for {record.workspace}. it is not "
            "serving a browser endpoint",
            err=True,
        )
        raise typer.Exit(1)
    typer.echo(f"workspace: {record.workspace}")
    typer.echo(f"lumlflow already at {_url(record)}")
    if record.web_port != port:
        typer.echo(f"it is serving port {record.web_port}, not {port}")
    if not no_browser:
        webbrowser.open(_url(record))


def _url(record: "DaemonRecord") -> str:
    """The authenticated address: the flow API asks every caller for the
    workspace's token, and the SPA is the one caller with no other way to
    have it."""
    return f"http://127.0.0.1:{record.web_port}/?token={record.token}"


_REBUILD = (
    "run `npm run build --workspace=lumlflow-ui` from the repo root. the next "
    "`lumlflow ui` serves what it makes"
)


@dataclass(frozen=True)
class WebAppCheck:
    """What is owed the built web app before it is served."""

    sync_from: Path | None = None
    warning: str | None = None


def _web_app_check(package_dir: Path) -> WebAppCheck:
    """Whether the web app about to be served still stands for its sources.

    Only a source checkout has a `frontend` beside the package; an installed
    wheel carries a build made at packaging time and no sources to be behind.
    """
    frontend = package_dir.parent / "frontend"
    if not frontend.is_dir():
        return WebAppCheck()

    sources = _latest(
        _newest_under(frontend / "src"),
        _stamp(frontend / "package.json"),
        _stamp(frontend / "vite.config.ts"),
    )
    if sources is None:
        return WebAppCheck()
    built = _newest_under(frontend / "dist")
    served = _stamp(package_dir / "static" / "index.html")

    syncable = built is not None and (served is None or built > served)
    behind = (served is None or sources > served) and (built is None or sources > built)
    warning = None
    if behind and served is None and not syncable:
        warning = (
            f"the web app has not been built, so a browser gets nothing. {_REBUILD}"
        )
    elif behind:
        warning = f"the web app being served is older than frontend/src. {_REBUILD}"
    return WebAppCheck(
        sync_from=frontend / "dist" if syncable else None, warning=warning
    )


def _refresh_web_app(package_dir: Path) -> None:
    """Keep a source checkout from silently serving yesterday's web app.

    A build somebody already made is copied into place here — that step costs
    nothing and needs no node. A build nobody made is said once, on the way
    past: `ui` is never the thing that runs npm, and never fails for this.

    Both lines are the checkout talking, not the server: they go to stderr, so
    stdout stays what it was — the address, said once it is serving.
    """
    check = _web_app_check(package_dir)
    if check.sync_from is not None and _copy_web_app(
        check.sync_from, package_dir / "static"
    ):
        typer.echo("web app updated from frontend/dist", err=True)
    if check.warning is not None:
        typer.echo(check.warning, err=True)


def _copy_web_app(dist: Path, static: Path) -> bool:
    """Replace the served build with `dist`, whole or not at all.

    Two workspaces starting at once are two of these over one checkout, so the
    copy is made beside what it replaces and swapped in: a browser reads one
    build or the other, never half of each, and a lost race is not an error.
    """
    staging = static.with_name(f".{static.name}.{os.getpid()}")
    replaced = static.with_name(f".{static.name}.{os.getpid()}.replaced")
    shutil.rmtree(staging, ignore_errors=True)
    copied = False
    try:
        shutil.copytree(dist, staging)
        if static.exists():
            os.replace(static, replaced)
        os.replace(staging, static)
        copied = True
    except OSError:
        with contextlib.suppress(OSError):
            if replaced.is_dir() and not static.exists():
                os.replace(replaced, static)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(replaced, ignore_errors=True)
    return copied


def _newest_under(root: Path) -> float | None:
    """The newest mtime among the files below a directory, if it holds any."""
    newest: float | None = None
    for parent, dirs, names in os.walk(root):
        dirs[:] = [name for name in dirs if name != "node_modules"]
        for name in names:
            stamp = _stamp(Path(parent) / name)
            if stamp is not None and (newest is None or stamp > newest):
                newest = stamp
    return newest


def _stamp(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _latest(*stamps: float | None) -> float | None:
    return max((stamp for stamp in stamps if stamp is not None), default=None)


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
