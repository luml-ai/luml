import json
from pathlib import Path

import pytest

from luml_prisma.demo.scenario import (
    DEBUG,
    FORK,
    IMPLEMENT,
    Scenario,
    ScenarioError,
    apply_step,
    builtin_scenarios_dir,
    detect_step_type,
    lint_scenario,
    load_scenario,
    load_state,
    match_step,
    resolve_scenario_dir,
    save_state,
)
from luml_prisma.services.orchestrator.prompts import (
    build_debug_prompt,
    build_fork_prompt,
    build_implement_prompt,
)

_CONFIG = {"run_command_template": "uv run main.py", "max_children_per_fork": 3}


def _autorag() -> Scenario:
    return load_scenario(builtin_scenarios_dir() / "autorag")


def _write_minimal_scenario(root: Path, toml: str) -> Path:
    (root / "steps/one/files").mkdir(parents=True)
    (root / "steps/one/narration.txt").write_text("hello\n@sleep 0.1\nworld\n")
    (root / "steps/one/files/code.py").write_text("x = 1\n")
    (root / "scenario.toml").write_text(toml)
    return root


_MINIMAL_TOML = """
[scenario]
name = "mini"

[[steps]]
id = "one"
type = "implement"
root = true
variant = "one"
files = "steps/one/files"
narration = "steps/one/narration.txt"

[[steps]]
id = "fork-one"
type = "fork"
after_variant = "one"

[[steps.proposals]]
title = "next"
prompt = "Do the next thing"
"""


class TestLoader:
    def test_autorag_loads_and_lints_clean(self) -> None:
        scenario = _autorag()
        assert scenario.agent_id == "demo-autorag"
        assert len(scenario.steps) == 7
        assert lint_scenario(scenario) == []

    def test_minimal_scenario(self, tmp_path: Path) -> None:
        scenario = load_scenario(_write_minimal_scenario(tmp_path, _MINIMAL_TOML))
        assert scenario.name == "mini"
        assert scenario.agent_id == "demo-mini"

    def test_missing_steps_rejected(self, tmp_path: Path) -> None:
        (tmp_path / "scenario.toml").write_text('[scenario]\nname = "x"\n')
        with pytest.raises(ScenarioError, match="no steps"):
            load_scenario(tmp_path)

    def test_bad_step_type_rejected(self, tmp_path: Path) -> None:
        (tmp_path / "scenario.toml").write_text(
            '[[steps]]\nid = "s"\ntype = "bogus"\n'
        )
        with pytest.raises(ScenarioError, match="type must be one of"):
            load_scenario(tmp_path)

    def test_fork_without_proposals_rejected(self, tmp_path: Path) -> None:
        (tmp_path / "scenario.toml").write_text(
            '[[steps]]\nid = "f"\ntype = "fork"\n'
        )
        with pytest.raises(ScenarioError, match="at least one proposal"):
            load_scenario(tmp_path)

    def test_missing_files_dir_rejected(self, tmp_path: Path) -> None:
        (tmp_path / "scenario.toml").write_text(
            '[[steps]]\nid = "s"\ntype = "implement"\nfiles = "nope"\n'
        )
        with pytest.raises(ScenarioError, match="files dir not found"):
            load_scenario(tmp_path)

    def test_resolve_by_name_finds_builtin(self) -> None:
        assert resolve_scenario_dir("autorag") == builtin_scenarios_dir() / "autorag"

    def test_resolve_unknown_raises(self) -> None:
        with pytest.raises(ScenarioError, match="not found"):
            resolve_scenario_dir("does-not-exist")


class TestLint:
    def test_ambiguous_proposal_matchers_flagged(self, tmp_path: Path) -> None:
        toml = """
[[steps]]
id = "a"
type = "implement"
root = true
proposal = "alpha beta"

[[steps]]
id = "b"
type = "implement"
proposal = "beta"

[[steps]]
id = "f"
type = "fork"
after_variant = "*"

[[steps.proposals]]
title = "p"
prompt = "do the alpha beta thing"
"""
        (tmp_path / "scenario.toml").write_text(toml)
        problems = lint_scenario(load_scenario(tmp_path))
        assert any("matches multiple implement steps" in p for p in problems)

    def test_unmatched_proposal_flagged(self, tmp_path: Path) -> None:
        scenario = load_scenario(_write_minimal_scenario(tmp_path, _MINIMAL_TOML))
        problems = lint_scenario(scenario)
        assert any("matches no implement step" in p for p in problems)


class TestStepDetection:
    def test_orchestrator_prompts_detected(self) -> None:
        implement = build_implement_prompt({"prompt": "objective"}, _CONFIG)
        fork = build_fork_prompt({"objective": "objective"}, _CONFIG)
        debug = build_debug_prompt({"objective": "objective"}, "", "logs", _CONFIG)
        assert detect_step_type(implement) == IMPLEMENT
        assert detect_step_type(fork) == FORK
        assert detect_step_type(debug) == DEBUG

    def test_fork_child_prompt_is_implement(self) -> None:
        prompt = build_implement_prompt(
            {"proposal": {"title": "t", "prompt": "p"}, "objective": "o"}, _CONFIG,
        )
        assert detect_step_type(prompt) == IMPLEMENT


class TestMatching:
    def test_autorag_full_story(self) -> None:
        scenario = _autorag()

        root_prompt = build_implement_prompt({"prompt": "objective"}, _CONFIG)
        root = match_step(scenario, IMPLEMENT, root_prompt, variant="")
        assert root is not None
        assert root.id == "baseline"

        fork = match_step(scenario, FORK, "prompt", variant="baseline")
        assert fork is not None
        assert fork.id == "fork-1"

        for proposal, expected in [
            (fork.proposals[0], "hybrid"),
            (fork.proposals[1], "chunking"),
            (fork.proposals[2], "query-expansion"),
        ]:
            child_prompt = build_implement_prompt(
                {"proposal": {"title": proposal.title, "prompt": proposal.prompt},
                 "objective": "o"},
                _CONFIG,
            )
            step = match_step(scenario, IMPLEMENT, child_prompt, variant="")
            assert step is not None
            assert step.id == expected

        debug = match_step(scenario, DEBUG, "prompt", variant="query-expansion")
        assert debug is not None
        assert debug.id == "query-expansion-debug"

        deep_fork = match_step(scenario, FORK, "prompt", variant="hybrid")
        assert deep_fork is not None
        assert deep_fork.id == "fork-revalidate"

    def test_no_match_returns_none(self, tmp_path: Path) -> None:
        scenario = load_scenario(_write_minimal_scenario(tmp_path, _MINIMAL_TOML))
        assert match_step(scenario, DEBUG, "prompt", variant="one") is None


class TestApplyStep:
    def test_implement_applies_files_result_state(self, tmp_path: Path) -> None:
        scenario = load_scenario(_write_minimal_scenario(tmp_path, _MINIMAL_TOML))
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        apply_step(scenario, scenario.steps[0], worktree)

        assert (worktree / "code.py").read_text() == "x = 1\n"
        result = json.loads((worktree / ".prisma/result.json").read_text())
        assert result == {"success": True}
        assert load_state(worktree)["variant"] == "one"
        assert load_state(worktree)["played"] == ["one"]

    def test_fork_writes_proposals(self, tmp_path: Path) -> None:
        scenario = load_scenario(_write_minimal_scenario(tmp_path, _MINIMAL_TOML))
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        apply_step(scenario, scenario.steps[1], worktree)

        fork = json.loads((worktree / ".prisma/fork.json").read_text())
        assert fork == [{"title": "next", "prompt": "Do the next thing"}]

    def test_result_overrides_merge(self, tmp_path: Path) -> None:
        toml = _MINIMAL_TOML + '\n[steps.result]\nnote = "extra"\n'
        scenario = load_scenario(_write_minimal_scenario(tmp_path, toml))
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        apply_step(scenario, scenario.steps[-1], worktree)

        result = json.loads((worktree / ".prisma/result.json").read_text())
        assert result["success"] is True
        assert result["note"] == "extra"


class TestState:
    def test_roundtrip(self, tmp_path: Path) -> None:
        save_state(tmp_path, {"variant": "v", "played": ["a"]})
        assert load_state(tmp_path) == {"variant": "v", "played": ["a"]}

    def test_missing_or_corrupt_state_is_empty(self, tmp_path: Path) -> None:
        assert load_state(tmp_path) == {}
        (tmp_path / ".prisma").mkdir()
        (tmp_path / ".prisma/demo-state.json").write_text("{broken")
        assert load_state(tmp_path) == {}
