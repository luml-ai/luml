"""The `lumlflow tui` command must fail gracefully when the optional
`tui` extra (textual, textual-plotext) is not installed."""

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from lumlflow.cli import app
from lumlflow.settings import get_config
from typer.testing import CliRunner

runner = CliRunner()


def _purge_tui_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(sys.modules):
        if name == "lumlflow.tui" or name.startswith("lumlflow.tui."):
            monkeypatch.delitem(sys.modules, name)


def test_tui_command_hints_extra_when_textual_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _purge_tui_modules(monkeypatch)
    # A None entry in sys.modules makes `import textual` raise
    # ModuleNotFoundError, simulating an install without the extra.
    monkeypatch.setitem(sys.modules, "textual", None)

    result = runner.invoke(app, ["tui"])

    assert result.exit_code == 1
    assert "lumlflow[tui]" in result.output + result.stderr


def test_tui_command_reraises_internal_import_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _purge_tui_modules(monkeypatch)
    monkeypatch.setitem(sys.modules, "lumlflow.tui.keymap", None)

    result = runner.invoke(app, ["tui"])

    assert result.exit_code != 0
    assert "lumlflow[tui]" not in result.output + result.stderr
    assert isinstance(result.exception, ModuleNotFoundError)


@pytest.fixture
def fresh_config() -> Iterator[None]:
    get_config.cache_clear()
    yield
    get_config.cache_clear()


@pytest.mark.usefixtures("fresh_config")
def test_tui_path_wins_over_the_store_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import lumlflow.tui

    opened: list[str] = []

    class App:
        def __init__(self, *, store_uri: str, **_: object) -> None:
            opened.append(store_uri)

        def run(self) -> None:
            return None

    monkeypatch.setattr(lumlflow.tui, "LumlflowApp", App)
    monkeypatch.setenv("BACKEND_STORE_URI", str(tmp_path / "from_variable"))
    monkeypatch.setenv("LUML_BACKEND_STORE_URI", str(tmp_path / "from_variable"))

    result = runner.invoke(app, ["tui", "--path", str(tmp_path / "from_path")])

    assert result.exit_code == 0
    assert opened == [f"sqlite://{tmp_path / 'from_path'}"]
