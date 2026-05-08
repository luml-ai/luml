import json
from pathlib import Path

import pytest

from luml_prisma.services import agents as agents_module
from luml_prisma.services.agents import (
    AgentDef,
    build_agent_command,
    get_agent,
    is_agent_available,
    list_agents,
    list_available_agents,
)


@pytest.fixture
def mock_agent_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUML_PRISMA_ENABLE_MOCK_AGENT", "1")


@pytest.fixture(autouse=True)
def _mock_agent_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LUML_PRISMA_ENABLE_MOCK_AGENT", raising=False)


@pytest.fixture(autouse=True)
def _isolate_custom_agents(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> Path:
    """Point custom-agents loader at an empty tmp dir by default."""
    custom_path = tmp_path / "coding-clis.json"
    monkeypatch.setattr(
        agents_module, "_custom_agents_path", lambda: custom_path,
    )
    return custom_path


@pytest.fixture
def custom_agents_path(_isolate_custom_agents: Path) -> Path:
    return _isolate_custom_agents


def test_get_agent_exists() -> None:
    agent = get_agent("claude")
    assert agent is not None
    assert agent.id == "claude"
    assert agent.name == "Claude Code"
    assert agent.cli == "claude"


def test_get_agent_missing() -> None:
    assert get_agent("nonexistent") is None


def test_list_agents_not_empty() -> None:
    agents = list_agents()
    assert len(agents) >= 2


def test_mock_agent_hidden_by_default() -> None:
    ids = {a.id for a in list_agents()}
    assert "mock" not in ids
    available_ids = {a.id for a in list_available_agents()}
    assert "mock" not in available_ids
    assert is_agent_available("mock") is False


def test_mock_agent_visible_when_enabled(mock_agent_enabled: None) -> None:
    ids = {a.id for a in list_agents()}
    assert "mock" in ids


def test_all_agents_have_required_fields() -> None:
    for agent in list_agents():
        assert agent.id
        assert agent.name
        assert agent.cli


def test_unique_ids() -> None:
    agents = list_agents()
    ids = [a.id for a in agents]
    assert len(ids) == len(set(ids))


def test_unique_cli_names() -> None:
    agents = list_agents()
    clis = [a.cli for a in agents]
    assert len(clis) == len(set(clis))


def test_known_agents_present(mock_agent_enabled: None) -> None:
    expected_ids = {
        "claude", "codex", "gemini", "cursor", "copilot", "opencode", "mock",
    }
    actual_ids = {a.id for a in list_agents()}
    assert expected_ids.issubset(actual_ids)


def test_gemini_agent_flags() -> None:
    agent = get_agent("gemini")
    assert agent is not None
    assert agent.cli == "gemini"
    # `-i`/`--prompt-interactive` seeds the interactive TUI;
    # `-p`/`--prompt` would be headless.
    assert agent.prompt_flag == "-i"
    assert agent.auto_approve_flag == "--yolo"


def test_cursor_agent_flags() -> None:
    agent = get_agent("cursor")
    assert agent is not None
    assert agent.cli == "cursor-agent"
    # cursor-agent takes the prompt as a positional arg in interactive mode;
    # -p/--print is the headless variant we don't want.
    assert agent.prompt_flag == ""
    assert agent.auto_approve_flag == "--force"


def test_copilot_agent_flags() -> None:
    agent = get_agent("copilot")
    assert agent is not None
    assert agent.cli == "copilot"
    # `-i`/`--interactive` seeds the interactive TUI and auto-runs the
    # prompt; `-p`/`--prompt` would be headless.
    assert agent.prompt_flag == "-i"
    assert agent.auto_approve_flag == "--allow-all-tools"


def test_opencode_agent_seeds_interactive_tui() -> None:
    agent = get_agent("opencode")
    assert agent is not None
    assert agent.cli == "opencode"
    # No `run` subcommand — that's headless. Bare `opencode --prompt`
    # opens the TUI with the prompt seeded.
    assert agent.default_args == []
    assert agent.prompt_flag == "--prompt"
    assert agent.auto_approve_flag == "--dangerously-skip-permissions"
    cmd = build_agent_command(agent, "fix bug", auto_approve=True)
    assert cmd == (
        "opencode --dangerously-skip-permissions --prompt 'fix bug'"
    )
    cmd_no_auto = build_agent_command(agent, "fix bug")
    assert cmd_no_auto == "opencode --prompt 'fix bug'"


def test_gemini_build_command() -> None:
    agent = get_agent("gemini")
    assert agent is not None
    cmd = build_agent_command(agent, "explain", auto_approve=True)
    assert cmd == "gemini --yolo -i explain"
    assert build_agent_command(agent, "explain") == "gemini -i explain"


def test_cursor_build_command_uses_positional() -> None:
    agent = get_agent("cursor")
    assert agent is not None
    cmd = build_agent_command(agent, "fix bug", auto_approve=True)
    assert cmd == "cursor-agent --force 'fix bug'"
    assert (
        build_agent_command(agent, "fix bug")
        == "cursor-agent 'fix bug'"
    )


def test_agent_def_is_frozen() -> None:
    agent = get_agent("claude")
    try:
        agent.id = "other"
        raise AssertionError("Should have raised FrozenInstanceError")
    except AttributeError:
        pass


def test_list_available_agents_returns_subset() -> None:
    available = list_available_agents()
    all_agents = list_agents()
    available_ids = {a.id for a in available}
    all_ids = {a.id for a in all_agents}
    assert available_ids.issubset(all_ids)


def test_build_agent_command_basic() -> None:
    agent = AgentDef(id="claude", name="Claude", cli="claude")
    cmd = build_agent_command(agent, "fix the bug")
    assert cmd == "claude 'fix the bug'"


def test_build_agent_command_with_auto_approve() -> None:
    agent = AgentDef(
        id="claude",
        name="Claude",
        cli="claude",
        auto_approve_flag="--dangerously-skip-permissions",
    )
    cmd = build_agent_command(agent, "fix bug", auto_approve=True)
    assert "--dangerously-skip-permissions" in cmd
    assert "'fix bug'" in cmd


def test_build_agent_command_omits_auto_approve_by_default() -> None:
    agent = AgentDef(
        id="claude",
        name="Claude",
        cli="claude",
        auto_approve_flag="--dangerously-skip-permissions",
    )
    cmd = build_agent_command(agent, "fix bug")
    assert "--dangerously-skip-permissions" not in cmd
    assert cmd == "claude 'fix bug'"


def test_build_agent_command_omits_auto_approve_when_false() -> None:
    agent = AgentDef(
        id="claude",
        name="Claude",
        cli="claude",
        auto_approve_flag="--dangerously-skip-permissions",
    )
    cmd = build_agent_command(agent, "fix bug", auto_approve=False)
    assert "--dangerously-skip-permissions" not in cmd


def test_build_agent_command_with_prompt_flag() -> None:
    agent = AgentDef(
        id="aider",
        name="Aider",
        cli="aider",
        prompt_flag="--message",
        auto_approve_flag="--yes",
    )
    cmd = build_agent_command(agent, "refactor code", auto_approve=True)
    assert cmd == "aider --yes --message 'refactor code'"


def test_build_agent_command_with_default_args() -> None:
    agent = AgentDef(
        id="test",
        name="Test",
        cli="test-cli",
        default_args=["--verbose", "--color"],
    )
    cmd = build_agent_command(agent, "hello")
    assert cmd == "test-cli --verbose --color hello"


def test_build_agent_command_empty_prompt() -> None:
    agent = AgentDef(id="claude", name="Claude", cli="claude")
    cmd = build_agent_command(agent, "")
    assert cmd == "claude"


def test_build_agent_command_special_chars_in_prompt() -> None:
    agent = AgentDef(id="claude", name="Claude", cli="claude")
    cmd = build_agent_command(agent, "fix the 'auth' bug & deploy")
    assert "fix the" in cmd
    assert "auth" in cmd


def test_build_agent_command_no_flags() -> None:
    agent = AgentDef(id="goose", name="Goose", cli="goose")
    cmd = build_agent_command(agent, "do stuff")
    assert cmd == "goose 'do stuff'"


def test_custom_agents_loaded_from_json(custom_agents_path: Path) -> None:
    custom_agents_path.parent.mkdir(parents=True, exist_ok=True)
    custom_agents_path.write_text(json.dumps([
        {
            "id": "myagent",
            "name": "My Agent",
            "cli": "my-cli",
            "prompt_flag": "--prompt",
            "auto_approve_flag": "--yes",
            "resume_flag": "--resume",
            "default_args": ["--verbose"],
        },
    ]))

    agent = get_agent("myagent")
    assert agent is not None
    assert agent.name == "My Agent"
    assert agent.cli == "my-cli"
    assert agent.prompt_flag == "--prompt"
    assert agent.auto_approve_flag == "--yes"
    assert agent.resume_flag == "--resume"
    assert agent.default_args == ["--verbose"]
    assert "myagent" in {a.id for a in list_agents()}


def test_custom_agents_minimal_entry(custom_agents_path: Path) -> None:
    custom_agents_path.parent.mkdir(parents=True, exist_ok=True)
    custom_agents_path.write_text(json.dumps([
        {"id": "minimal", "name": "Minimal", "cli": "minimal-cli"},
    ]))

    agent = get_agent("minimal")
    assert agent is not None
    assert agent.prompt_flag == ""
    assert agent.auto_approve_flag == ""
    assert agent.default_args == []


def test_custom_agents_missing_file_is_silent() -> None:
    # Default fixture points at a non-existent path.
    assert get_agent("anything-non-existent") is None
    # Built-ins still work.
    assert get_agent("claude") is not None


def test_custom_agents_invalid_json_silently_skipped(
    custom_agents_path: Path,
) -> None:
    custom_agents_path.parent.mkdir(parents=True, exist_ok=True)
    custom_agents_path.write_text("{not valid json")
    assert get_agent("claude") is not None
    assert "claude" in {a.id for a in list_agents()}


def test_custom_agents_non_list_root_skipped(
    custom_agents_path: Path,
) -> None:
    custom_agents_path.parent.mkdir(parents=True, exist_ok=True)
    custom_agents_path.write_text(json.dumps({"agents": []}))
    # No custom agent should be loaded; built-ins still work.
    assert get_agent("claude") is not None


def test_custom_agents_bad_entries_skipped(
    custom_agents_path: Path,
) -> None:
    custom_agents_path.parent.mkdir(parents=True, exist_ok=True)
    custom_agents_path.write_text(json.dumps([
        "not a dict",
        {"name": "missing id", "cli": "x"},
        {"id": "missing-name", "cli": "x"},
        {"id": "missing-cli", "name": "x"},
        {"id": "bad-default-args", "name": "x", "cli": "x",
         "default_args": "not a list"},
        {"id": "good", "name": "Good", "cli": "good-cli"},
    ]))

    assert get_agent("good") is not None
    for bad_id in (
        "missing-id", "missing-name", "missing-cli", "bad-default-args",
    ):
        assert get_agent(bad_id) is None


def test_custom_agents_cannot_shadow_builtin(
    custom_agents_path: Path,
) -> None:
    custom_agents_path.parent.mkdir(parents=True, exist_ok=True)
    custom_agents_path.write_text(json.dumps([
        {
            "id": "claude",
            "name": "Hijacked Claude",
            "cli": "evil-cli",
        },
    ]))

    agent = get_agent("claude")
    assert agent is not None
    assert agent.name == "Claude Code"
    assert agent.cli == "claude"


def test_custom_agents_duplicate_ids_first_wins(
    custom_agents_path: Path,
) -> None:
    custom_agents_path.parent.mkdir(parents=True, exist_ok=True)
    custom_agents_path.write_text(json.dumps([
        {"id": "dup", "name": "First", "cli": "first"},
        {"id": "dup", "name": "Second", "cli": "second"},
    ]))

    agent = get_agent("dup")
    assert agent is not None
    assert agent.name == "First"


def test_custom_agents_appear_in_list_agents(
    custom_agents_path: Path,
) -> None:
    custom_agents_path.parent.mkdir(parents=True, exist_ok=True)
    custom_agents_path.write_text(json.dumps([
        {"id": "extra", "name": "Extra", "cli": "extra-cli"},
    ]))

    ids = [a.id for a in list_agents()]
    assert ids.index("claude") < ids.index("extra")
    assert "extra" in ids


def test_custom_agent_build_command(custom_agents_path: Path) -> None:
    custom_agents_path.parent.mkdir(parents=True, exist_ok=True)
    custom_agents_path.write_text(json.dumps([
        {
            "id": "aider",
            "name": "Aider",
            "cli": "aider",
            "prompt_flag": "--message",
            "auto_approve_flag": "--yes",
        },
    ]))

    agent = get_agent("aider")
    assert agent is not None
    cmd = build_agent_command(agent, "refactor code", auto_approve=True)
    assert cmd == "aider --yes --message 'refactor code'"
    assert (
        build_agent_command(agent, "refactor code")
        == "aider --message 'refactor code'"
    )
