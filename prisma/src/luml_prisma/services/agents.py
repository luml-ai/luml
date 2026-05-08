import json
import shlex
import shutil
from dataclasses import dataclass, field
from pathlib import Path

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
        id="gemini",
        name="Gemini CLI",
        cli="gemini",
        prompt_flag="-i",
        auto_approve_flag="--yolo",
    ),
    AgentDef(
        id="cursor",
        name="Cursor Agent",
        cli="cursor-agent",
        auto_approve_flag="--force",
    ),
    AgentDef(
        id="copilot",
        name="GitHub Copilot CLI",
        cli="copilot",
        prompt_flag="-i",
        auto_approve_flag="--allow-all-tools",
    ),
    AgentDef(
        id="opencode",
        name="opencode",
        cli="opencode",
        prompt_flag="--prompt",
        auto_approve_flag="--dangerously-skip-permissions",
    ),
    AgentDef(
        id="mock",
        name="Mock Agent",
        cli="mock-agent",
    ),
]

_DEBUG_ONLY_AGENT_IDS: frozenset[str] = frozenset({"mock"})


def _custom_agents_path() -> Path:
    return Path.home() / ".luml-prisma" / "coding-clis.json"


def _coerce_str(v: object) -> str | None:
    return v if isinstance(v, str) else None


def _parse_custom_agent(entry: object) -> AgentDef | None:
    if not isinstance(entry, dict):
        return None
    id_ = _coerce_str(entry.get("id"))
    name = _coerce_str(entry.get("name"))
    cli = _coerce_str(entry.get("cli"))
    if not id_ or not name or not cli:
        return None
    default_args_raw = entry.get("default_args", [])
    if not isinstance(default_args_raw, list) or not all(
        isinstance(a, str) for a in default_args_raw
    ):
        return None
    return AgentDef(
        id=id_,
        name=name,
        cli=cli,
        prompt_flag=_coerce_str(entry.get("prompt_flag")) or "",
        auto_approve_flag=_coerce_str(entry.get("auto_approve_flag")) or "",
        resume_flag=_coerce_str(entry.get("resume_flag")) or "",
        default_args=list(default_args_raw),
    )


def _load_custom_agents() -> list[AgentDef]:
    path = _custom_agents_path()
    if not path.exists():
        return []
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    builtin_ids = {a.id for a in _BUILTIN_AGENTS}
    seen: set[str] = set()
    agents: list[AgentDef] = []
    for entry in data:
        agent = _parse_custom_agent(entry)
        if agent is None:
            continue
        if agent.id in builtin_ids or agent.id in seen:
            continue
        seen.add(agent.id)
        agents.append(agent)
    return agents


def _all_agents() -> list[AgentDef]:
    return list(_BUILTIN_AGENTS) + _load_custom_agents()


def _visible_agents() -> list[AgentDef]:
    if is_mock_agent_enabled():
        return _all_agents()
    return [a for a in _all_agents() if a.id not in _DEBUG_ONLY_AGENT_IDS]


def get_agent(agent_id: str) -> AgentDef | None:
    for a in _all_agents():
        if a.id == agent_id:
            return a
    return None


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


def build_agent_command(
    agent: AgentDef, prompt: str, auto_approve: bool = False,
) -> str:
    parts = [agent.cli]
    parts.extend(agent.default_args)
    if auto_approve and agent.auto_approve_flag:
        parts.append(agent.auto_approve_flag)
    if prompt:
        if agent.prompt_flag:
            parts.append(agent.prompt_flag)
        parts.append(shlex.quote(prompt))
    return " ".join(parts)
