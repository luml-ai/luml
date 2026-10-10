from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from lumlflow.cli import app
from lumlflow.server import app as server_app
from typer.testing import CliRunner


def test_no_browser_launch_url_matches_the_running_session() -> None:
    with patch("lumlflow.cli.uvicorn.run") as run:
        result = CliRunner().invoke(app, ["ui", "--no-browser"])
    assert result.exit_code == 0
    url = result.output.split("Lumlflow UI available at ", 1)[1].strip()
    assert parse_qs(urlsplit(url).fragment)["session-token"] == [
        server_app.state.session_token
    ]
    assert run.call_args.args[0] is server_app


def test_automatic_browser_launch_uses_the_session_url() -> None:
    with (
        patch("lumlflow.cli.uvicorn.run"),
        patch("lumlflow.cli.time.sleep"),
        patch("lumlflow.cli.webbrowser.open") as browser,
        patch("lumlflow.cli.threading.Thread") as thread,
    ):
        result = CliRunner().invoke(app, ["ui"])
        thread.call_args.kwargs["target"]()
    assert result.exit_code == 0
    assert server_app.state.session_token not in result.output
    url = browser.call_args.args[0]
    assert parse_qs(urlsplit(url).fragment)["session-token"] == [
        server_app.state.session_token
    ]
