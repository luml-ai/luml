import pytest
import typer.rich_utils


@pytest.fixture(autouse=True)
def plain_cli_output(monkeypatch: pytest.MonkeyPatch) -> None:
    # typer forces a rich terminal (ANSI styling) when GITHUB_ACTIONS or
    # FORCE_COLOR is set, which breaks substring assertions on CliRunner output.
    monkeypatch.setattr(typer.rich_utils, "FORCE_TERMINAL", False)
