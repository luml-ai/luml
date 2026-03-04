from luml_agent.agents import (
    AgentDef,
    build_agent_command,
    get_agent,
    list_agents,
    list_available_agents,
)


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
    assert len(agents) >= 3


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


def test_known_agents_present() -> None:
    expected_ids = {"claude", "codex", "mock"}
    actual_ids = {a.id for a in list_agents()}
    assert expected_ids.issubset(actual_ids)


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
    cmd = build_agent_command(agent, "fix bug")
    assert "--dangerously-skip-permissions" in cmd
    assert "'fix bug'" in cmd


def test_build_agent_command_with_prompt_flag() -> None:
    agent = AgentDef(
        id="aider",
        name="Aider",
        cli="aider",
        prompt_flag="--message",
        auto_approve_flag="--yes",
    )
    cmd = build_agent_command(agent, "refactor code")
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
