import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _default_preserve_patterns() -> list[str]:
    return [".env", ".env.local", ".env.development", ".env.production"]


def _default_exclude_patterns() -> list[str]:
    return ["node_modules", ".git", "__pycache__", ".venv", "venv"]


def _default_cors_origins() -> list[str]:
    return ["http://localhost:*", "https://*.luml.ai"]


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path
    db_path: Path
    branch_prefix: str = "luml-agent"
    default_agent_id: str = "claude"
    preserve_patterns: list[str] = field(default_factory=_default_preserve_patterns)
    exclude_patterns: list[str] = field(default_factory=_default_exclude_patterns)
    cors_origins: list[str] = field(default_factory=_default_cors_origins)


def get_data_dir() -> Path:
    xdg = Path.home() / ".local" / "share" / "luml-agent"
    xdg.mkdir(parents=True, exist_ok=True)
    return xdg


def get_config_path() -> Path:
    return Path.home() / ".config" / "luml-agent" / "config.toml"


def load_config() -> AppConfig:
    data_dir = get_data_dir()
    db_path = data_dir / "luml-agent.db"

    defaults: dict[str, Any] = {
        "branch_prefix": "luml-agent",
        "default_agent_id": "claude",
        "preserve_patterns": _default_preserve_patterns(),
        "exclude_patterns": _default_exclude_patterns(),
        "cors_origins": _default_cors_origins(),
    }

    config_path = get_config_path()
    if config_path.exists():
        with open(config_path, "rb") as f:
            user_conf = tomllib.load(f)
        defaults.update(user_conf)

    env_cors = os.environ.get("LUML_AGENT_CORS_ORIGINS")
    if env_cors:
        defaults["cors_origins"] = [o.strip() for o in env_cors.split(",")]

    return AppConfig(
        data_dir=data_dir,
        db_path=db_path,
        branch_prefix=defaults["branch_prefix"],
        default_agent_id=defaults["default_agent_id"],
        preserve_patterns=defaults["preserve_patterns"],
        exclude_patterns=defaults["exclude_patterns"],
        cors_origins=defaults["cors_origins"],
    )
