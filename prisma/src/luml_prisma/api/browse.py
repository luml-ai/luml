import asyncio
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from luml_prisma.infra.exceptions import InvalidOperationError
from luml_prisma.schemas import (
    BranchListOut,
    BrowseEntryOut,
    BrowseResultOut,
)

router = APIRouter(prefix="/api/browse", tags=["browse"])


@router.get("")
def browse(
    path: str | None = None,
) -> dict[str, Any]:
    target = (
        Path.home()
        if path is None
        else Path(os.path.expanduser(path)).resolve()
    )

    if not target.exists():
        raise InvalidOperationError(
            f"Path does not exist: {target}"
        )
    if not target.is_dir():
        raise InvalidOperationError(
            f"Not a directory: {target}"
        )

    try:
        entries = list(target.iterdir())
    except PermissionError as exc:
        raise InvalidOperationError(
            f"Permission denied: {target}"
        ) from exc

    dirs: list[BrowseEntryOut] = []
    for entry in sorted(
        entries, key=lambda e: e.name.lower(),
    ):
        if entry.name.startswith("."):
            continue
        try:
            if not entry.is_dir():
                continue
            is_git = (entry / ".git").exists()
        except PermissionError:
            continue
        dirs.append(
            BrowseEntryOut(
                name=entry.name,
                path=str(entry),
                is_git=is_git,
            )
        )

    parent = (
        str(target.parent)
        if target != target.parent
        else None
    )
    return BrowseResultOut(
        current=str(target),
        parent=parent,
        dirs=dirs,
        is_git=(target / ".git").exists(),
    ).model_dump()


@router.get("/branches")
async def list_branches(path: str) -> dict[str, Any]:
    target = Path(os.path.expanduser(path)).resolve()

    if not target.is_dir():
        raise InvalidOperationError(
            f"Not a directory: {target}"
        )
    if not (target / ".git").exists():
        raise InvalidOperationError(
            f"Not a git repository: {target}"
        )

    proc = await asyncio.create_subprocess_exec(
        "git",
        "for-each-ref",
        "refs/heads/",
        "--format=%(refname:short)",
        cwd=str(target),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise InvalidOperationError(
            f"Failed to list branches: {stderr.decode().strip()}"
        )

    branches = sorted(
        line
        for line in stdout.decode().strip().splitlines()
        if line
    )
    return BranchListOut(branches=branches).model_dump()
