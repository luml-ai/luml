import os
import threading
import time
import webbrowser

import typer
import uvicorn

app = typer.Typer(
    name="lumlflow",
    help="Local ML experiment tracking",
)


@app.command()
def ui(
    path: str | None = typer.Option(
        None,
        "--path",
        help="Backend store URI (e.g. sqlite://./experiments)",
    ),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to"),
    port: int = typer.Option(5000, "--port", "-p", help="Port to bind to"),
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Don't open browser automatically"
    ),
) -> None:
    if path is not None:
        os.environ["BACKEND_STORE_URI"] = path

    from lumlflow.settings import get_config

    typer.echo(f"Using experiment store: {get_config().BACKEND_STORE_URI}")
    url = f"http://{host}:{port}"

    def open_browser_delayed() -> None:
        time.sleep(1.0)
        webbrowser.open(url)

    if not no_browser:
        typer.echo(f"Opening {url} in browser...")
        thread = threading.Thread(target=open_browser_delayed, daemon=True)
        thread.start()
    else:
        typer.echo(f"Lumlflow UI available at {url}")

    uvicorn.run(
        "lumlflow.server:app",
        host=host,
        port=port,
        reload=False,
    )


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
