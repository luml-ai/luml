import importlib.resources
import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def _copy_guide_md(dest_dir: Path) -> None:
    dest = dest_dir / "guide.md"
    if dest.exists():
        return
    source = importlib.resources.files("luml_agent.data").joinpath("guide.md")
    with importlib.resources.as_file(source) as src_path:
        shutil.copy2(src_path, dest)


def ensure_luml_agent_dir(worktree_path: str) -> Path:
    p = Path(worktree_path) / ".luml-agent"
    p.mkdir(exist_ok=True)
    _copy_guide_md(p)
    return p


def ensure_global_luml_dir() -> Path:
    home = Path.home() / ".luml-agent"
    (home / "experiments").mkdir(parents=True, exist_ok=True)
    return home


def _has_luml_dependency(pyproject_path: Path) -> bool:
    text = pyproject_path.read_text()
    for line in text.splitlines():
        stripped = line.strip().rstrip(",").strip().strip('"').strip("'")
        if (
            stripped == "luml"
            or stripped.startswith("luml>=")
            or stripped.startswith("luml[")
        ):
            return True
    return False


def ensure_luml_dependency(worktree_path: str) -> None:
    pyproject = Path(worktree_path) / "pyproject.toml"
    if not pyproject.exists():
        logger.info(
            "No pyproject.toml in %s, skipping luml injection",
            worktree_path,
        )
        return

    if _has_luml_dependency(pyproject):
        return

    try:
        subprocess.run(
            ["uv", "add", "luml"],
            cwd=worktree_path,
            check=True,
            capture_output=True,
            timeout=60,
        )
    except FileNotFoundError:
        logger.warning("uv not available, skipping luml dependency injection")
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(errors="replace") if exc.stderr else ""
        logger.warning("uv add luml failed: %s", stderr or exc)
    except subprocess.TimeoutExpired:
        logger.warning("uv add luml timed out in %s", worktree_path)
