import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from luml_prisma.demo.cli import app
from luml_prisma.demo.scenario import load_scenario

runner = CliRunner()


@pytest.fixture(autouse=True)
def demo_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


def _agents_file(home: Path) -> Path:
    return home / ".luml-prisma" / "coding-clis.json"


class TestInstallAgent:
    def test_install_writes_entry(self, demo_home: Path) -> None:
        result = runner.invoke(app, ["install-agent", "autorag"])
        assert result.exit_code == 0
        agents = json.loads(_agents_file(demo_home).read_text())
        entry = next(a for a in agents if a["id"] == "demo-autorag")
        assert entry["cli"] == "prisma-demo-agent"
        assert entry["default_args"] == ["--scenario", "autorag"]

    def test_install_preserves_other_entries_and_is_idempotent(
        self, demo_home: Path,
    ) -> None:
        path = _agents_file(demo_home)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps([{"id": "other", "name": "o", "cli": "o"}]))

        runner.invoke(app, ["install-agent", "autorag"])
        runner.invoke(app, ["install-agent", "autorag", "--speed", "0.5"])

        agents = json.loads(path.read_text())
        assert [a["id"] for a in agents] == ["other", "demo-autorag"]
        assert agents[1]["default_args"] == ["--scenario", "autorag", "--speed", "0.5"]

    def test_uninstall_removes_entry(self, demo_home: Path) -> None:
        runner.invoke(app, ["install-agent", "autorag"])
        result = runner.invoke(app, ["uninstall-agent", "autorag"])
        assert result.exit_code == 0
        assert json.loads(_agents_file(demo_home).read_text()) == []

    def test_unknown_scenario_fails(self) -> None:
        result = runner.invoke(app, ["install-agent", "nope"])
        assert result.exit_code == 1


class TestInitRepo:
    def test_creates_git_repo_with_commit(self, tmp_path: Path) -> None:
        target = tmp_path / "repo"
        result = runner.invoke(
            app, ["init-repo", "autorag", str(target), "--no-sync"],
        )
        assert result.exit_code == 0, result.output
        assert (target / "data" / "corpus.json").exists()
        assert (target / "pyproject.toml").exists()
        log = subprocess.run(
            ["git", "-C", str(target), "log", "--oneline"],
            capture_output=True, text=True, check=True,
        )
        assert "AutoRAG" in log.stdout

    def test_refuses_non_empty_target(self, tmp_path: Path) -> None:
        target = tmp_path / "repo"
        target.mkdir()
        (target / "existing.txt").write_text("x")
        result = runner.invoke(
            app, ["init-repo", "autorag", str(target), "--no-sync"],
        )
        assert result.exit_code == 1


class TestDoctor:
    def test_all_checks_pass_after_install(self, demo_home: Path) -> None:
        runner.invoke(app, ["install-agent", "autorag"])
        result = runner.invoke(app, ["doctor", "autorag"])
        assert result.exit_code == 0, result.output
        assert "demo ready" in result.output

    def test_missing_agent_entry_fails(self) -> None:
        result = runner.invoke(app, ["doctor", "autorag"])
        assert result.exit_code == 1
        assert "install-agent" in result.output

    def test_broken_experiments_store_fails(self, demo_home: Path) -> None:
        runner.invoke(app, ["install-agent", "autorag"])
        store = demo_home / ".prisma" / "experiments"
        store.mkdir(parents=True)
        (store / "meta.db").write_bytes(b"this is not a sqlite database")
        result = runner.invoke(app, ["doctor", "autorag"])
        assert result.exit_code == 1
        assert "experiments store" in result.output
        assert "mv ~/.prisma/experiments" in result.output


class TestScaffoldAndInfo:
    def test_new_scenario_scaffold_loads(self, demo_home: Path) -> None:
        result = runner.invoke(app, ["new-scenario", "myscn"])
        assert result.exit_code == 0
        scenario_dir = demo_home / ".luml-prisma" / "demo-scenarios" / "myscn"
        scenario = load_scenario(scenario_dir)
        assert scenario.name == "myscn"
        assert {s.step_type for s in scenario.steps} == {"implement", "fork"}

    def test_list_includes_builtin(self) -> None:
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "autorag" in result.output

    def test_runbook_prints_settings(self) -> None:
        result = runner.invoke(app, ["runbook", "autorag"])
        assert result.exit_code == 0
        assert "Demo Agent — AutoRAG" in result.output
        assert "Max children per fork:  3" in result.output
        assert "uv run main.py" in result.output
