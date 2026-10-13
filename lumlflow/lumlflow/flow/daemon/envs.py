import asyncio
import shutil
import sys
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from lumlflow.flow.errors import EnvError
from lumlflow.flow.hashing import hash_json
from lumlflow.flow.store.models import EnvChanged

if TYPE_CHECKING:
    from lumlflow.flow.daemon.hub import FlowSession

PROJECT_FILE = "pyproject.toml"
LOCK_FILE = "uv.lock"
VENV_DIRNAME = ".venv"
_SYNC_TIMEOUT_S = 600.0
_OUTPUT_TAIL_CHARS = 2000


@dataclass(frozen=True)
class Interpreter:
    python: Path
    source: Literal["venv", "lumlflow"]


def venv_python(workspace_dir: Path) -> Path | None:
    venv = workspace_dir / VENV_DIRNAME
    candidates = (
        venv / "Scripts" / "python.exe",
        venv / "bin" / "python",
        venv / "bin" / "python3",
    )
    return next((path for path in candidates if path.exists()), None)


def describe(workspace_dir: Path) -> Interpreter:
    environment_dir = _environment_dir(workspace_dir)
    python = venv_python(environment_dir) if environment_dir is not None else None
    if python is not None:
        return Interpreter(python=python, source="venv")
    return Interpreter(python=Path(sys.executable), source="lumlflow")


async def ensure_interpreter(workspace_dir: Path) -> Interpreter:
    environment_dir = _environment_dir(workspace_dir)
    if environment_dir is None:
        return Interpreter(python=Path(sys.executable), source="lumlflow")
    python = venv_python(environment_dir)
    if python is not None:
        return Interpreter(python=python, source="venv")
    if not (environment_dir / VENV_DIRNAME).exists():
        if shutil.which("uv") is None:
            raise EnvError(
                f"could not find `uv` on PATH to prepare {environment_dir}; "
                "install `uv` and try again"
            )
        await uv_sync(environment_dir)
        python = venv_python(environment_dir)
        if python is not None:
            return Interpreter(python=python, source="venv")
    return Interpreter(python=Path(sys.executable), source="lumlflow")


def _environment_dir(workspace_dir: Path) -> Path | None:
    start = workspace_dir.resolve()
    return next(
        (
            directory
            for directory in (start, *start.parents)
            if (directory / VENV_DIRNAME).exists()
            or (directory / PROJECT_FILE).is_file()
        ),
        None,
    )


async def uv_sync(workspace_dir: Path) -> None:
    """Install what the workspace declares. A failure here is the user's to fix.

    Falling back to another interpreter would run cells against dependencies
    the workspace does not have and blame the cell for the ImportError.
    """
    await uv(workspace_dir, "sync")


def packages(workspace_dir: Path) -> dict[str, str]:
    environment_dir = _environment_dir(workspace_dir) or workspace_dir.resolve()
    path = environment_dir / LOCK_FILE
    try:
        status = path.stat()
    except OSError:
        _PINNED.pop(path, None)
        return {}
    stamp = (status.st_mtime_ns, status.st_size)
    cached = _PINNED.get(path)
    if cached is None or cached[0] != stamp:
        cached = (stamp, _read_lock(path))
        _PINNED[path] = cached
    return dict(cached[1])


_PINNED: dict[Path, tuple[tuple[int, int], dict[str, str]]] = {}


def _read_lock(path: Path) -> dict[str, str]:
    try:
        parsed = tomllib.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    entries = parsed.get("package")
    if not isinstance(entries, list):
        return {}
    return {
        normalize(str(entry["name"])): str(entry.get("version") or "")
        for entry in entries
        if isinstance(entry, dict) and entry.get("name")
    }


def lock_hash(pinned: Mapping[str, str]) -> str | None:
    return hash_json(dict(pinned)) if pinned else None


def normalize(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def drift(before: Mapping[str, str], after: Mapping[str, str]) -> list[str]:
    return sorted(
        name for name in {*before, *after} if before.get(name) != after.get(name)
    )


def summary(before: Mapping[str, str], after: Mapping[str, str]) -> str:
    added = [f"{name} {after[name]}" for name in sorted(after) if name not in before]
    dropped = sorted(name for name in before if name not in after)
    moved = [
        f"{name} {before[name]} → {after[name]}"
        for name in sorted(after)
        if name in before and before[name] != after[name]
    ]
    parts = [
        *([f"added {', '.join(added)}"] if added else []),
        *([f"removed {', '.join(dropped)}"] if dropped else []),
        *([f"updated {', '.join(moved)}"] if moved else []),
    ]
    return "; ".join(parts)


def sync(
    root: Path,
    sessions: Iterable["FlowSession"],
    *,
    actor: str = "system",
    intent: str | None = None,
) -> bool:
    pinned = packages(root)
    current = lock_hash(pinned)
    if current is None:
        return False
    changed = False
    for session in sessions:
        known = session.store.index.env()
        if known is not None and known.lock_hash == current:
            continue
        changes = (
            summary(known.packages, pinned)
            if known is not None
            else "recorded the workspace env"
        )
        session.store.commit(
            [EnvChanged(lock_hash=current, packages=pinned, summary=changes)],
            intent=intent or changes,
            actor=actor,
        )
        changed = True
    return changed


async def uv(workspace_dir: Path, *args: str) -> str:
    spelled = " ".join(("uv", *args))
    try:
        process = await asyncio.create_subprocess_exec(
            "uv",
            *args,
            cwd=str(workspace_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError:
        raise EnvError(
            f"could not find `uv` on PATH to prepare {workspace_dir}; "
            "install `uv` and try again"
        ) from None
    try:
        stdout, _ = await asyncio.wait_for(
            process.communicate(), timeout=_SYNC_TIMEOUT_S
        )
    except TimeoutError as timeout:
        process.kill()
        raise EnvError(
            f"`{spelled}` did not finish in {int(_SYNC_TIMEOUT_S)}s in {workspace_dir}"
        ) from timeout
    output = stdout.decode("utf-8", "replace")
    if process.returncode != 0:
        tail = output[-_OUTPUT_TAIL_CHARS:].strip()
        raise EnvError(f"`{spelled}` failed in {workspace_dir}:\n{tail}")
    return output
