import asyncio
import json
from pathlib import Path
from typing import Any, cast

import pytest
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.daemon.main import Daemon, Leases
from lumlflow.flow.dsl.tree import WorkspaceTree
from lumlflow.flow.errors import LaneMoved

from tests.helpers.daemon import daemon_api, make_workspace

NOTE = '''
class Note:
    """A note on the lane."""
'''

AGENT = "codex-1"


def _as_agent(**params: Any) -> dict[str, Any]:
    return {"flow": "churn", "actor": AGENT} | params


async def _lane_with_two_steps(api: Api) -> tuple[int, int]:
    await api.flow_open({"flow": "churn"})
    await api.cells_new({"flow": "churn", "slug": "first", "source": NOTE})
    await api.cells_new({"flow": "churn", "slug": "second", "source": NOTE})
    first = await api.cells_show({"flow": "churn", "slug": "first"})
    second = await api.cells_show({"flow": "churn", "slug": "second"})
    return int(first["created_step"]), int(second["created_step"])


async def _agent_reads_context(api: Api) -> None:
    await api.context(_as_agent())
    api.observed("context", _as_agent())


async def test_a_change_after_somebody_rewound_the_lane_is_refused_once(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        first, _ = await _lane_with_two_steps(api)
        await _agent_reads_context(api)
        await api.rewind({"flow": "churn", "to_step": first})

        with pytest.raises(LaneMoved) as refused:
            api.fence("cells.new", _as_agent(slug="third"))
        api.fence("cells.new", _as_agent(slug="third"))

    message = str(refused.value)
    assert refused.value.to_step == first
    assert refused.value.by == "user"
    assert f"moved to step {first} by user" in message
    assert "Nothing was changed" in message
    assert "`new-lane`" in message


@pytest.mark.parametrize("method", ["cells.new", "cells.edit"])
async def test_a_rewind_while_a_fenced_change_waits_for_its_scan_refuses_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        first, _ = await _lane_with_two_steps(api)
        await _agent_reads_context(api)
        params = _as_agent(slug="first" if method == "cells.edit" else "third")
        params["source"] = NOTE + "\n# changed\n"
        rewind_scanning = asyncio.Event()
        release_rewind = asyncio.Event()
        fenced = asyncio.Event()
        scan = api.hub._scan

        async def rewind_scan_held(workspace_dir: Path) -> WorkspaceTree:
            if not rewind_scanning.is_set():
                rewind_scanning.set()
                await release_rewind.wait()
            return await scan(workspace_dir)

        async def agent_change() -> dict[str, Any]:
            api.fence(method, params)
            fenced.set()
            return await api.methods[method](params)

        monkeypatch.setattr(api.hub, "_scan", rewind_scan_held)
        rewind = asyncio.create_task(api.rewind({"flow": "churn", "to_step": first}))
        await rewind_scanning.wait()
        change = asyncio.create_task(agent_change())
        await fenced.wait()
        release_rewind.set()
        await rewind

        with pytest.raises(LaneMoved) as refused:
            await change
        assert refused.value.to_step == first
        cells = await api.cells_list({"flow": "churn"})
        assert "third" not in {cell["slug"] for cell in cells["cells"]}


async def test_every_change_is_fenced_and_reading_or_moving_it_is_not(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        first, _ = await _lane_with_two_steps(api)
        await _agent_reads_context(api)
        await api.rewind({"flow": "churn", "to_step": first})

        for method in ("context", "cells.show", "asset.preview", "fork", "rewind"):
            api.fence(method, _as_agent())
        with pytest.raises(LaneMoved):
            api.fence("run", _as_agent(target="first"))


async def test_a_person_editing_at_the_newest_step_does_not_stop_the_agent(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        await _lane_with_two_steps(api)
        await _agent_reads_context(api)
        await api.cells_new({"flow": "churn", "slug": "by_hand", "source": NOTE})

        api.fence("cells.edit", _as_agent(slug="first"))


async def test_the_agents_own_rewind_and_a_return_to_where_it_was_are_not_moves(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        first, second = await _lane_with_two_steps(api)
        await _agent_reads_context(api)

        await api.rewind(_as_agent(to_step=first))
        api.observed("rewind", _as_agent(to_step=first))
        api.fence("cells.new", _as_agent(slug="third"))

        await api.rewind({"flow": "churn", "to_step": second})
        await api.rewind({"flow": "churn", "to_step": first})
        api.fence("cells.new", _as_agent(slug="third"))


async def test_an_agent_that_was_shown_nothing_is_held_to_nothing(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        first, _ = await _lane_with_two_steps(api)
        await api.rewind({"flow": "churn", "to_step": first})

        api.fence("cells.new", _as_agent(slug="third"))
        api.forget_agent(AGENT)
        api.fence("cells.new", _as_agent(slug="third"))


async def test_a_run_waiting_for_its_scan_is_fenced_on_its_own_lane_after_a_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        first, _ = await _lane_with_two_steps(api)
        await api.fork({"flow": "churn", "name": "sweep"})
        await _agent_reads_context(api)
        session = api.hub.session("churn")
        run_scanning = asyncio.Event()
        release_run = asyncio.Event()
        scan = api.hub._scan

        async def run_scan_held(workspace_dir: Path) -> WorkspaceTree:
            run_scanning.set()
            await release_run.wait()
            return await scan(workspace_dir)

        async def agent_run() -> dict[str, Any]:
            api.fence("run", _as_agent())
            return await api.run(_as_agent())

        monkeypatch.setattr(api.hub, "_scan", run_scan_held)
        running = asyncio.create_task(agent_run())
        await run_scanning.wait()
        session.store.branches.rewind("main", to_step=first, actor="user")
        session.worktree.checkout("sweep", actor="user")
        release_run.set()

        with pytest.raises(LaneMoved) as refused:
            await running
        assert refused.value.to_step == first


class _Socket:
    """The writer end of a client connection: keeps each reply sent to it."""

    def __init__(self) -> None:
        self.replies: list[dict[str, Any]] = []

    def write(self, data: bytes) -> None:
        self.replies.append(json.loads(data))

    def is_closing(self) -> bool:
        return False

    async def drain(self) -> None:
        return None


async def test_a_leased_run_that_waited_out_a_checkout_acknowledges_its_own_lane(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project")
    daemon = Daemon(root)
    api = daemon.api
    socket = _Socket()
    leased: Leases = set()

    async def call(method: str, params: dict[str, Any]) -> dict[str, Any]:
        line = json.dumps({"id": 1, "method": method, "params": params}).encode()
        await daemon._handle(line, cast(asyncio.StreamWriter, socket), leased)
        return socket.replies.pop()

    try:
        await _lane_with_two_steps(api)
        await api.fork({"flow": "churn", "name": "sweep"})
        for slug in ("on_sweep", "later_on_sweep"):
            await api.cells_new(
                {"flow": "churn", "branch": "sweep", "slug": slug, "source": NOTE}
            )
        shown = await api.cells_show(
            {"flow": "churn", "branch": "sweep", "slug": "on_sweep"}
        )
        await api.flow_checkout({"flow": "churn", "branch": "main"})
        await call("agent.begin", _as_agent(label="codex", lease=True))
        await call("context", _as_agent(branch="sweep"))
        await call("context", _as_agent())
        session = api.hub.session("churn")
        run_scanning = asyncio.Event()
        release_run = asyncio.Event()
        scan = api.hub._scan

        async def run_scan_held(workspace_dir: Path) -> WorkspaceTree:
            run_scanning.set()
            await release_run.wait()
            return await scan(workspace_dir)

        monkeypatch.setattr(api.hub, "_scan", run_scan_held)
        running = asyncio.create_task(call("run", _as_agent()))
        await run_scanning.wait()
        session.store.branches.rewind(
            "sweep", to_step=int(shown["created_step"]), actor="user"
        )
        session.worktree.checkout("sweep", actor="user")
        release_run.set()
        ran = await running
        edited = await call("cells.new", _as_agent(slug="third", source=NOTE))
    finally:
        await daemon.hub.close()

    assert ran["result"]["branch"] == "main"
    assert edited["error"]["data"]["kind"] == "LaneMoved"
