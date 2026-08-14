"""The workspace venv: one interpreter, every flow in the workspace shares it.

The venv holds no lumlflow code — the kernel is path-injected from the tool
install — so all the daemon needs from it is a Python. uv owns it: a workspace
that declares dependencies gets them synced before the first kernel starts. A
bare directory declares nothing, so there is nothing to sync and the daemon's
own interpreter runs the kernel; `status` reports which of the two it is rather
than claiming a venv that does not exist.

The lockfile is also the flow's record of what it computed under. Every
materialization stores the hash of the pins that were live when it ran, so a
result computed before an upgrade says so instead of quietly passing for
current.
"""

import asyncio
import re
import shutil
import sys
import tomllib
from collections.abc import Iterable, Mapping, Sequence
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
SDK_PACKAGE = "luml-sdk"
_SYNC_TIMEOUT_S = 600.0
_OUTPUT_TAIL_CHARS = 2000
_REQUIREMENT_NAME = re.compile(r"^[A-Za-z0-9._-]+")


@dataclass(frozen=True)
class Interpreter:
    python: Path
    source: Literal["venv", "lumlflow"]


def venv_python(workspace_dir: Path) -> Path | None:
    """The workspace venv's interpreter, if the venv is already there."""
    venv = workspace_dir / VENV_DIRNAME
    candidates = (
        venv / "Scripts" / "python.exe",
        venv / "bin" / "python",
        venv / "bin" / "python3",
    )
    return next((path for path in candidates if path.exists()), None)


def describe(workspace_dir: Path) -> Interpreter:
    """What would run a kernel right now, without syncing anything."""
    python = venv_python(workspace_dir)
    if python is not None:
        return Interpreter(python=python, source="venv")
    return Interpreter(python=Path(sys.executable), source="lumlflow")


async def ensure_interpreter(workspace_dir: Path) -> Interpreter:
    python = venv_python(workspace_dir)
    if python is not None:
        return Interpreter(python=python, source="venv")
    if (workspace_dir / PROJECT_FILE).exists() and shutil.which("uv"):
        await uv_sync(workspace_dir)
        python = venv_python(workspace_dir)
        if python is not None:
            return Interpreter(python=python, source="venv")
    return Interpreter(python=Path(sys.executable), source="lumlflow")


async def uv_sync(workspace_dir: Path) -> None:
    """Install what the workspace declares. A failure here is the user's to fix.

    Falling back to another interpreter would run cells against dependencies
    the workspace does not have and blame the cell for the ImportError.
    """
    await uv(workspace_dir, "sync")


async def ensure_sdk(workspace_dir: Path) -> bool:
    """Put the luml SDK in the workspace env — what a published output needs.

    Scaffolded rather than assumed, because the SDK is an ordinary workspace
    dependency: the venv holds no lumlflow code, so a flow that declares a
    `model`, `dataset` or `experiment` output has to declare the library that
    talks to the platform too. A workspace with no `pyproject.toml` declares
    nothing and is left alone, and one that already asks for the SDK is not
    asked again — `uv add` would rewrite the user's lockfile for nothing.
    """
    project = workspace_dir / PROJECT_FILE
    if not project.exists() or shutil.which("uv") is None:
        return False
    if _declares(project, SDK_PACKAGE):
        return False
    await uv(workspace_dir, "add", SDK_PACKAGE)
    return True


async def add(workspace_dir: Path, names: Sequence[str]) -> str:
    """Put packages in the workspace env. Every flow under it shares them."""
    if not names:
        raise EnvError("name a package to add")
    return await uv(workspace_dir, "add", *names)


async def remove(workspace_dir: Path, names: Sequence[str]) -> str:
    if not names:
        raise EnvError("name a package to remove")
    return await uv(workspace_dir, "remove", *names)


def packages(workspace_dir: Path) -> dict[str, str]:
    """What the lockfile pins, by distribution name.

    The lockfile is what the env means across kernel restarts — `uv sync`
    rebuilds the venv from it — so it, rather than the directory a `pip install`
    could have reached into, is the one file read here.

    Read once per version of the file. Every verb records the env before it
    resolves anything, and a real workspace's `uv.lock` is a quarter of a
    megabyte of TOML — parsing it twenty times while a notebook opens is twenty
    parses of bytes that cannot have changed. The file's `(mtime_ns, size)` is
    what says it did: `uv` writes a new lockfile rather than editing one, so a
    changed pin always arrives as a changed stamp.
    """
    path = workspace_dir / LOCK_FILE
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
    # A fresh mapping per call, as reading the file gave: the cache is an
    # optimization, not a shared object callers have to know not to touch.
    return dict(cached[1])


# Keyed by lockfile path: one daemon hosts flows from more than one workspace.
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
    """The env as a fact a run can record. `None` where nothing is declared.

    Over the pinned versions rather than the lockfile's bytes: a lockfile
    rewritten to the same pins is the same environment, and journalling a
    transition for a reformat would put a change in the history that never
    happened.
    """
    return hash_json(dict(pinned)) if pinned else None


def normalize(name: str) -> str:
    """A distribution name as PyPI compares them."""
    return name.strip().lower().replace("_", "-")


def drift(before: Mapping[str, str], after: Mapping[str, str]) -> list[str]:
    """The distributions whose pinned version moved between two observations."""
    return sorted(
        name for name in {*before, *after} if before.get(name) != after.get(name)
    )


def summary(before: Mapping[str, str], after: Mapping[str, str]) -> str:
    """What moved, in the words the journal and the banner both use."""
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
) -> None:
    """Fold the workspace env into every flow that runs under it.

    Appended to each hosted flow's own journal, for the reason shared code is: a
    flow rebuilds its index standalone, and a materialization recording a lock
    hash its flow never observed records provenance nothing can read back.

    Recording it is all this does. The env is provenance, not a memo-key
    ingredient — an install mid-session must not invalidate what already ran —
    so nothing here marks a cell, and only a cell that declared itself
    `env_sensitive` keys on the hash at all.
    """
    pinned = packages(root)
    current = lock_hash(pinned)
    if current is None:
        return
    for session in sessions:
        known = session.store.index.env()
        if known is not None and known.lock_hash == current:
            continue
        # The first observation names no transition: there is no env it moved
        # from, and listing the whole lockfile as "added" would read as an
        # install the user never ran.
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


async def uv(workspace_dir: Path, *args: str) -> str:
    """Run uv in the workspace and hand back what it said."""
    spelled = " ".join(("uv", *args))
    process = await asyncio.create_subprocess_exec(
        "uv",
        *args,
        cwd=str(workspace_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
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


def _declares(project: Path, package: str) -> bool:
    try:
        declared = tomllib.loads(project.read_text("utf-8"))
    except (OSError, ValueError):
        return False
    project_table = declared.get("project") or {}
    groups = [
        project_table.get("dependencies") or [],
        *(project_table.get("optional-dependencies") or {}).values(),
        *(declared.get("dependency-groups") or {}).values(),
    ]
    return any(_requirement(entry) == package for group in groups for entry in group)


def _requirement(entry: object) -> str:
    """The distribution a requirement string names, normalised as PyPI does."""
    if not isinstance(entry, str):
        return ""
    found = _REQUIREMENT_NAME.match(entry.strip())
    return normalize(found.group(0)) if found else ""
