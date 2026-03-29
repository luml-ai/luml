import asyncio
import logging
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class WorktreeStatus:
    branch: str
    commits_ahead: int
    changed_files: int


def slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def generate_short_id(length: int = 6) -> str:
    return uuid.uuid4().hex[:length]


async def _run_git(args: list[str], cwd: str | Path) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    assert proc.returncode is not None
    return proc.returncode, stdout.decode().strip(), stderr.decode().strip()


def preserve_env_files(
    source: Path,
    dest: Path,
    patterns: list[str] | None = None,
) -> list[str]:
    if patterns is None:
        patterns = [".env", ".env.local", ".env.development", ".env.production"]
    copied = []
    for pattern in patterns:
        src_file = source / pattern
        if src_file.is_file():
            shutil.copy2(str(src_file), str(dest / pattern))
            copied.append(pattern)
    return copied


async def create_worktree(
    repo_path: str | Path,
    task_name: str,
    base_branch: str,
    branch_prefix: str = "luml-agent",
    preserve_patterns: list[str] | None = None,
    shared_paths: list[str] | None = None,
) -> tuple[str, str]:
    repo = Path(repo_path).resolve()
    slug = slugify(task_name)
    short_id = generate_short_id()
    branch_name = f"{branch_prefix}/{slug}-{short_id}"
    worktree_dir_name = f"{slug}-{short_id}"

    worktrees_root = repo.parent / "worktrees"
    worktrees_root.mkdir(parents=True, exist_ok=True)
    worktree_path = worktrees_root / worktree_dir_name

    rc, _, stderr = await _run_git(
        ["worktree", "add", "-b", branch_name, str(worktree_path), base_branch],
        cwd=repo,
    )
    if rc != 0:
        raise RuntimeError(f"Failed to create worktree: {stderr}")

    try:
        preserve_env_files(repo, worktree_path, preserve_patterns)
    except Exception:
        logger.warning(
            "Failed to preserve env files in worktree %s", worktree_path,
            exc_info=True,
        )

    linked = setup_shared_paths(repo, worktree_path, shared_paths or [])
    _setup_gitignore(worktree_path, extra_entries=linked)

    return str(worktree_path), branch_name


async def remove_worktree(
    repo_path: str | Path,
    worktree_path: str | Path,
    branch_name: str,
) -> None:
    repo = Path(repo_path).resolve()
    wt = Path(worktree_path).resolve()

    if wt == repo:
        raise ValueError("Cannot remove the main repository worktree")

    if wt.exists():
        rc, _, stderr = await _run_git(
            ["worktree", "remove", "--force", str(wt)],
            cwd=repo,
        )
        if rc != 0:
            raise RuntimeError(f"Failed to remove worktree: {stderr}")

    await _run_git(["worktree", "prune"], cwd=repo)

    rc, _, _ = await _run_git(["branch", "-D", branch_name], cwd=repo)


async def get_worktree_status(
    repo_path: str | Path,
    branch_name: str,
    base_branch: str,
) -> WorktreeStatus:
    repo = Path(repo_path).resolve()

    rc, out, _ = await _run_git(
        ["rev-list", "--count", f"{base_branch}..{branch_name}"],
        cwd=repo,
    )
    commits_ahead = int(out) if rc == 0 and out.isdigit() else 0

    rc, out, _ = await _run_git(
        ["diff", "--name-only", f"{base_branch}...{branch_name}"],
        cwd=repo,
    )
    changed_files = len(out.splitlines()) if rc == 0 and out else 0

    return WorktreeStatus(
        branch=branch_name,
        commits_ahead=commits_ahead,
        changed_files=changed_files,
    )


_OBSOLETE_ENTRIES = {".luml-fork.json", ".proposals/", "result.json"}


def _setup_gitignore(
    worktree_path: Path,
    extra_entries: list[str] | None = None,
) -> None:
    gitignore = worktree_path / ".gitignore"
    required = {".luml-agent/"}
    if extra_entries:
        for e in extra_entries:
            entry = e.rstrip("/") + "/"
            required.add(entry)

    if gitignore.exists():
        lines = gitignore.read_text().splitlines()
        filtered = [ln for ln in lines if ln.strip() not in _OBSOLETE_ENTRIES]
        existing = {ln.strip() for ln in filtered}
        for entry in required:
            if entry not in existing:
                filtered.append(entry)
        gitignore.write_text("\n".join(filtered) + "\n")
    else:
        gitignore.write_text("\n".join(required) + "\n")


def setup_shared_paths(
    repo_path: Path,
    worktree_path: Path,
    shared_paths: list[str],
) -> list[str]:
    linked: list[str] = []
    for rel_path in shared_paths:
        source = repo_path / rel_path
        target = worktree_path / rel_path
        if not source.exists():
            continue
        if target.exists() or target.is_symlink():
            if target.is_symlink():
                target.unlink()
            elif target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        target.symlink_to(source.resolve())
        linked.append(rel_path)
    return linked


async def auto_commit_changes(worktree_path: str | Path) -> bool:
    wt = Path(worktree_path)
    rc, out, _ = await _run_git(["status", "--porcelain"], cwd=wt)
    if rc != 0 or not out.strip():
        return False
    rc, _, stderr = await _run_git(["add", "-A"], cwd=wt)
    if rc != 0:
        logger.warning("auto-commit: git add failed in %s: %s", wt, stderr)
        return False
    rc, _, stderr = await _run_git(
        ["commit", "-m", "luml-agent: auto-commit uncommitted changes"],
        cwd=wt,
    )
    if rc != 0:
        logger.warning("auto-commit: git commit failed in %s: %s", wt, stderr)
        return False
    return True
