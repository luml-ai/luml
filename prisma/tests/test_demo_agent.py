import json
from pathlib import Path

import pytest

from luml_prisma.demo.agent import parse_args, run
from luml_prisma.services.orchestrator.prompts import (
    build_fork_prompt,
    build_implement_prompt,
)

_CONFIG = {"run_command_template": "uv run main.py", "max_children_per_fork": 3}


@pytest.fixture(autouse=True)
def _fast_playback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISMA_DEMO_SPEED", "0")


@pytest.fixture
def worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cwd = tmp_path / "worktree"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return cwd


class TestParseArgs:
    def test_scenario_speed_and_prompt(self) -> None:
        inv = parse_args(["--scenario", "autorag", "--speed", "0.5", "# Objective"])
        assert inv.scenario == "autorag"
        assert inv.speed == 0.5
        assert inv.prompt == "# Objective"

    def test_prompt_parts_joined(self) -> None:
        inv = parse_args(["--scenario", "s", "part one", "part two"])
        assert inv.prompt == "part one part two"

    def test_invalid_speed_ignored(self) -> None:
        assert parse_args(["--speed", "abc"]).speed is None


class TestRun:
    def test_missing_scenario_flag(self, worktree: Path) -> None:
        assert run(["some prompt"]) == 2

    def test_unknown_scenario_writes_failure(self, worktree: Path) -> None:
        assert run(["--scenario", "nope", "prompt"]) == 1
        result = json.loads((worktree / ".prisma/result.json").read_text())
        assert result["success"] is False

    def test_root_implement(
        self, worktree: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        prompt = build_implement_prompt({"prompt": "objective"}, _CONFIG)
        assert run(["--scenario", "autorag", prompt]) == 0
        assert (worktree / "main.py").exists()
        assert (worktree / "rag" / "retrieval.py").exists()
        result = json.loads((worktree / ".prisma/result.json").read_text())
        assert result["success"] is True
        assert "LangGraph" in capsys.readouterr().out

    def test_fork_after_baseline(self, worktree: Path) -> None:
        prompt = build_implement_prompt({"prompt": "objective"}, _CONFIG)
        assert run(["--scenario", "autorag", prompt]) == 0
        fork_prompt = build_fork_prompt({"objective": "objective"}, _CONFIG)
        assert run(["--scenario", "autorag", fork_prompt]) == 0
        fork = json.loads((worktree / ".prisma/fork.json").read_text())
        assert [p["title"] for p in fork] == [
            "hybrid-bm25-rrf", "paragraph-chunking", "query-expansion",
        ]

    def test_fork_catch_all_fires_for_unknown_variant(self, worktree: Path) -> None:
        fork_prompt = build_fork_prompt({"objective": "objective"}, _CONFIG)
        assert run(["--scenario", "autorag", fork_prompt]) == 0
        fork = json.loads((worktree / ".prisma/fork.json").read_text())
        assert fork[0]["title"] == "revalidate-hybrid"
