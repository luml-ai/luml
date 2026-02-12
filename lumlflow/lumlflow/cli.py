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
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(5000, "--port", "-p", help="Port to bind to"),
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Don't open browser automatically"
    ),
) -> None:
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


@app.command()
def version() -> None:
    from lumlflow import __version__

    typer.echo(f"lumlflow {__version__}")


if __name__ == "__main__":
    app()
