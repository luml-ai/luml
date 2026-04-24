import shlex
import shutil
from dataclasses import dataclass, field

from luml_prisma.mock_agent import is_mock_agent_enabled


@dataclass(frozen=True)
class AgentDef:
    id: str
    name: str
    cli: str
    prompt_flag: str = ""
    auto_approve_flag: str = ""
    resume_flag: str = ""
    default_args: list[str] = field(default_factory=list)


_BUILTIN_AGENTS: list[AgentDef] = [
    AgentDef(
        id="claude",
        name="Claude Code",
        cli="claude",
        auto_approve_flag="--dangerously-skip-permissions",
    ),
    AgentDef(
        id="codex",
        name="Codex",
        cli="codex",
        auto_approve_flag="--yolo",
    ),
    AgentDef(
        id="mock",
        name="Mock Agent",
        cli="mock-agent",
    ),
]

_AGENTS_BY_ID: dict[str, AgentDef] = {a.id: a for a in _BUILTIN_AGENTS}

_DEBUG_ONLY_AGENT_IDS: frozenset[str] = frozenset({"mock"})


def _visible_agents() -> list[AgentDef]:
    if is_mock_agent_enabled():
        return list(_BUILTIN_AGENTS)
    return [a for a in _BUILTIN_AGENTS if a.id not in _DEBUG_ONLY_AGENT_IDS]


def get_agent(agent_id: str) -> AgentDef | None:
    return _AGENTS_BY_ID.get(agent_id)


def list_agents() -> list[AgentDef]:
    return _visible_agents()


def is_agent_available(agent_id: str) -> bool:
    agent = get_agent(agent_id)
    if agent is None:
        return False
    if agent.id in _DEBUG_ONLY_AGENT_IDS and not is_mock_agent_enabled():
        return False
    return shutil.which(agent.cli) is not None


def list_available_agents() -> list[AgentDef]:
    return [a for a in _visible_agents() if shutil.which(a.cli) is not None]


def build_agent_command(agent: AgentDef, prompt: str) -> str:
    parts = [agent.cli]
    parts.extend(agent.default_args)
    if agent.auto_approve_flag:
        parts.append(agent.auto_approve_flag)
    if prompt:
        if agent.prompt_flag:
            parts.append(agent.prompt_flag)
        parts.append(shlex.quote(prompt))
    return " ".join(parts)
