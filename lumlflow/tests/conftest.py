import importlib.util

import pytest


@pytest.fixture(autouse=True)
def plain_cli_output(monkeypatch: pytest.MonkeyPatch) -> None:
    # typer forces a rich terminal (ANSI styling) when GITHUB_ACTIONS or
    # FORCE_COLOR is set, which breaks substring assertions on CliRunner output.
    # The kernel tests run without project dependencies, so typer may be absent.
    if importlib.util.find_spec("typer") is None:
        return
    import typer.rich_utils

    monkeypatch.setattr(typer.rich_utils, "FORCE_TERMINAL", False)
