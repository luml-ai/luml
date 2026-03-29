from pathlib import Path


def ensure_luml_agent_dir(worktree_path: str) -> Path:
    p = Path(worktree_path) / ".luml-agent"
    p.mkdir(exist_ok=True)
    return p


def ensure_global_luml_dir() -> Path:
    home = Path.home() / ".luml-agent"
    (home / "experiments").mkdir(parents=True, exist_ok=True)
    return home
