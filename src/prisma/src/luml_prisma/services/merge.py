import asyncio
from dataclasses import dataclass
from pathlib import Path

from luml_prisma.infra.exceptions import MergeConflictError


@dataclass
class BranchDiffStats:
    commits_ahead: int
    files_changed: int
    insertions: int
    deletions: int


@dataclass
class MergePreview:
    branch: str
    base_branch: str
    stats: BranchDiffStats
    commit_messages: list[str]
    changed_files: list[str]
    can_fast_forward: bool


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


async def get_branch_diff_stats(
    repo_path: str | Path,
    branch: str,
    base_branch: str,
) -> BranchDiffStats:
    repo = Path(repo_path).resolve()

    rc, out, _ = await _run_git(
        ["rev-list", "--count", f"{base_branch}..{branch}"],
        cwd=repo,
    )
    commits_ahead = int(out) if rc == 0 and out.isdigit() else 0

    rc, out, _ = await _run_git(
        ["diff", "--shortstat", f"{base_branch}...{branch}"],
        cwd=repo,
    )
    files_changed = 0
    insertions = 0
    deletions = 0
    if rc == 0 and out:
        parts = out.split(",")
        for part in parts:
            part = part.strip()
            if "file" in part:
                files_changed = int(part.split()[0])
            elif "insertion" in part:
                insertions = int(part.split()[0])
            elif "deletion" in part:
                deletions = int(part.split()[0])

    return BranchDiffStats(
        commits_ahead=commits_ahead,
        files_changed=files_changed,
        insertions=insertions,
        deletions=deletions,
    )


async def can_fast_forward(
    repo_path: str | Path,
    branch: str,
    base_branch: str,
) -> bool:
    repo = Path(repo_path).resolve()
    rc, merge_base, _ = await _run_git(
        ["merge-base", base_branch, branch],
        cwd=repo,
    )
    if rc != 0:
        return False
    rc, base_head, _ = await _run_git(["rev-parse", base_branch], cwd=repo)
    return rc == 0 and merge_base == base_head


async def get_merge_preview(
    repo_path: str | Path,
    branch: str,
    base_branch: str,
) -> MergePreview:
    repo = Path(repo_path).resolve()

    stats = await get_branch_diff_stats(repo, branch, base_branch)
    ff = await can_fast_forward(repo, branch, base_branch)

    rc, out, _ = await _run_git(
        ["log", "--oneline", f"{base_branch}..{branch}"],
        cwd=repo,
    )
    commit_messages = out.splitlines() if rc == 0 and out else []

    rc, out, _ = await _run_git(
        ["diff", "--name-only", f"{base_branch}...{branch}"],
        cwd=repo,
    )
    changed_files = out.splitlines() if rc == 0 and out else []

    return MergePreview(
        branch=branch,
        base_branch=base_branch,
        stats=stats,
        commit_messages=commit_messages,
        changed_files=changed_files,
        can_fast_forward=ff,
    )


async def merge_branch(
    repo_path: str | Path,
    branch: str,
    base_branch: str,
) -> str:
    repo = Path(repo_path).resolve()

    rc, original_branch, _ = await _run_git(
        ["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo
    )

    rc, _, stderr = await _run_git(["checkout", base_branch], cwd=repo)
    if rc != 0:
        raise RuntimeError(f"Failed to checkout {base_branch}: {stderr}")

    rc, out, stderr = await _run_git(["merge", "--no-ff", branch], cwd=repo)
    if rc != 0:
        _, conflict_out, _ = await _run_git(
            ["diff", "--name-only", "--diff-filter=U"], cwd=repo,
        )
        await _run_git(["merge", "--abort"], cwd=repo)
        if original_branch and original_branch != base_branch:
            await _run_git(["checkout", original_branch], cwd=repo)
        if conflict_out.strip():
            conflicting_files = conflict_out.strip().splitlines()
            raise MergeConflictError(conflicting_files)
        raise RuntimeError(f"Merge failed: {stderr}")

    if original_branch and original_branch != base_branch and original_branch != branch:
        await _run_git(["checkout", original_branch], cwd=repo)

    return out
