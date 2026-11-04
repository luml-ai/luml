import contextlib
import importlib.util
from collections.abc import AsyncIterator
from typing import Any

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


@pytest.fixture(autouse=True)
def settled_tui_apps(monkeypatch: pytest.MonkeyPatch) -> None:
    if importlib.util.find_spec("textual") is None:
        return
    from textual.app import App
    from textual.pilot import Pilot

    from tests.tui_helpers import settle_workers

    run_test = App.run_test

    @contextlib.asynccontextmanager
    async def settled(
        self: App[Any], *args: Any, **kwargs: Any
    ) -> AsyncIterator[Pilot[Any]]:
        async with run_test(self, *args, **kwargs) as pilot:
            yield pilot
            await settle_workers(pilot)

    monkeypatch.setattr(App, "run_test", settled)
