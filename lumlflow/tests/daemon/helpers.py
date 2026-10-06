import asyncio
import contextlib
import json
import os
import re
import stat
import sys
import textwrap
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any

from lumlflow.flow.daemon import envs
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.daemon.hub import FlowSession, Hub
from lumlflow.flow.daemon.kernel_proc import KernelProcess, OnEvent
from lumlflow.flow.scheduler.planner import Bound
from lumlflow.flow.scheduler.queue import RunRequest
from lumlflow.flow.store.flowstore import (
    CELLS_DIRNAME,
    FLOW_SUFFIX,
    FlowStore,
    store_dir,
)
from lumlflow.flow.store.index import VersionRow
from lumlflow.flow.store.models import OutputSpec, Transaction
from lumlflow.tracker import TrackerProvider

SCORE_CELL = """
class Score:
    \"\"\"The headline metric.\"\"\"
    produces = {"summary": "asset"}

    def materialize(self, ctx):
        return {"summary": {"auc": 0.91}}
"""

REPORT_CELL = """
class Report:
    \"\"\"Reads the score.\"\"\"
    consumes = {"summary": "score.summary"}
    produces = {"report": "asset"}

    def materialize(self, ctx, summary):
        return {"report": {"auc_pct": summary["auc"] * 100}}
"""

BROKEN_CELL = """
class Broken:
    \"\"\"Fails on purpose.\"\"\"
    produces = {"summary": "asset"}

    def materialize(self, ctx):
        raise ValueError("the model did not converge")
"""

TRAIN_CELL = """
class Train:
    \"\"\"Produces something that leaves the flow.\"\"\"
    produces = {"model": "model", "run": "experiment"}

    def materialize(self, ctx):
        ctx.tracker.log_param("lr", 3e-4)
        ctx.tracker.log_metric("auc", 0.91)
        return {"model": "WEIGHTS", "run": ctx.tracker.record}
"""

EXTERNAL_CELL = """
class Load:
    \"\"\"Reads a workspace file, which the store does not version.\"\"\"
    produces = {"rows": "asset"}

    def materialize(self, ctx):
        import pandas

        return {"rows": pandas.read_csv(ctx.workspace_dir / "raw.csv")}
"""

FRAME_CELL = """
class Rows:
    \"\"\"A frame worth paging.\"\"\"
    produces = {"rows": {"type": "asset", "kind": "frame"}}

    def materialize(self, ctx):
        import pandas

        return {"rows": pandas.DataFrame({"n": list(range(50))})}
"""


def make_workspace(
    root: Path,
    *,
    flows: Sequence[str] = ("churn",),
    files: dict[str, str] | None = None,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for name in flows:
        (root / f"{name}{FLOW_SUFFIX}" / CELLS_DIRNAME).mkdir(
            parents=True, exist_ok=True
        )
    for relative, body in (files or {}).items():
        write_file(root / relative, body)
    return root


def write_cell(flow_dir: Path, slug: str, source: str) -> Path:
    return write_file(flow_dir / CELLS_DIRNAME / f"{slug}.py", source)


def write_file(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).strip() + "\n", encoding="utf-8")
    return path


def stub_uv(directory: Path, script: str, monkeypatch: Any) -> Path:
    tool = write_file(directory / "uv", script)
    tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")
    return tool


def write_lock(root: Path, pins: dict[str, str]) -> Path:
    return write_file(root / envs.LOCK_FILE, _lock_body(pins))


def _lock_body(pins: dict[str, str]) -> str:
    return "version = 1\n" + "".join(
        f'\n[[package]]\nname = "{name}"\nversion = "{version}"\n'
        for name, version in pins.items()
    )


def fake_venv(root: Path) -> Path:
    python = root / ".venv" / ("Scripts" if sys.platform == "win32" else "bin")
    python.mkdir(parents=True, exist_ok=True)
    link = python / ("python.exe" if sys.platform == "win32" else "python")
    os.symlink(sys.executable, link)
    return link


@contextlib.asynccontextmanager
async def flow_kernel(
    root: Path, *, flow: str = "churn", on_event: OnEvent | None = None
) -> AsyncIterator[KernelProcess]:
    flow_dir = root / f"{flow}{FLOW_SUFFIX}"
    if not store_dir(flow_dir).is_dir():
        FlowStore.init(flow_dir).close()
    kernel = KernelProcess(flow_dir=flow_dir, workspace_dir=root, on_event=on_event)
    try:
        yield kernel
    finally:
        await kernel.stop()


def run_request(
    slug: str,
    source: str,
    *,
    run_id: str = "run1",
    produces: dict[str, str] | None = None,
    inputs: dict[str, Bound] | None = None,
    params: dict[str, object] | None = None,
) -> RunRequest:
    return RunRequest(
        run_id=run_id,
        flow="churn",
        flow_id="01J000000000000000000000FL",
        flow_path="",
        branch="main",
        step=1,
        uid="01J000000000000000000000UI",
        slug=slug,
        version_id="01J000000000000000000000VE",
        source=textwrap.dedent(source).strip() + "\n",
        produces={
            name: OutputSpec(type=spec)  # type: ignore[arg-type]
            for name, spec in (produces or {"summary": "asset"}).items()
        },
        params=dict(params or {}),
        inputs=dict(inputs or {}),
    )


class LocalDaemon:
    def __init__(self, api: Api, loop: asyncio.AbstractEventLoop) -> None:
        self._api = api
        self._loop = loop

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        return self._loop.run_until_complete(self._api.methods[method](params or {}))

    def close(self) -> None:
        pass

    def __enter__(self) -> "LocalDaemon":
        return self

    def __exit__(self, *_: object) -> None:
        pass


@contextlib.asynccontextmanager
async def daemon_api(
    root: Path, *, tracker: TrackerProvider | None = None
) -> AsyncIterator[Api]:
    hub = Hub(tracker=tracker)
    try:
        yield Api(hub, directory=root)
    finally:
        await hub.close()


def transactions(session: FlowSession) -> list[Transaction]:
    return list(session.store.journal.replay())


def ops_of(session: FlowSession, kind: type) -> list[Any]:
    return [
        op
        for entry in transactions(session)
        for op in entry.ops
        if isinstance(op, kind)
    ]


def source_of(flow_dir: Path, slug: str) -> str:
    return (flow_dir / CELLS_DIRNAME / f"{slug}.py").read_text("utf-8")


def cell_files(flow_dir: Path) -> list[str]:
    return sorted(path.stem for path in (flow_dir / CELLS_DIRNAME).glob("*.py"))


def flags_on(status: dict[str, Any], slug: str) -> list[str]:
    cell = next(found for found in status["cells"] if found["slug"] == slug)
    return [str(flag["code"]) for flag in cell["flags"]]


def slugs(status: dict[str, Any], state: str | None = None) -> list[str]:
    return [
        str(cell["slug"])
        for cell in status["cells"]
        if state is None or cell["state"] == state
    ]


def flow_named(status: dict[str, Any], name: str) -> dict[str, Any]:
    return next(flow for flow in status["flows"] if flow["flow"] == name)


def slice_of(session: FlowSession, branch: str) -> dict[str, VersionRow]:
    branch_id = session.store.branches.get(branch).branch_id
    return {
        version.slug: version
        for version in session.store.index.slice_versions(branch_id).values()
    }


def values_in(flow_dir: Path) -> list[Any]:
    values = store_dir(flow_dir) / "values"
    blobs = [
        path
        for path in sorted(values.rglob("*"))
        if path.is_file() and path.parent.name != "tmp"
    ]
    return sorted((json.loads(path.read_bytes()) for path in blobs), key=json.dumps)


GIT_WORDS = re.compile(
    r"\b(branch|branches|branching|fork|forks|forked|forking|checkout|"
    r"checkouts|commit|commits|merge|merges|merged|clone|clones|rebase|"
    r"cherry-pick|worktree|worktrees|trunk|unsynced|variant|variants)\b",
    re.IGNORECASE,
)


_PATHISH = re.compile(r"\S*/\S*")


def no_git_words(text: str, where: str) -> None:
    found = sorted(set(GIT_WORDS.findall(_PATHISH.sub(" ", text))))
    assert not found, f"{where} says {found}:\n{text}"
