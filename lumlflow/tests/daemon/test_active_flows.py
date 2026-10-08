import asyncio
import contextlib
import time
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from lumlflow.flow.daemon import web, workspace
from lumlflow.flow.daemon.api import Api, Leases
from lumlflow.flow.daemon.hub import FlowSession, Hub
from lumlflow.flow.daemon.stream import Streams
from lumlflow.flow.errors import FlowAmbiguous

from tests.daemon.helpers import SCORE_CELL, daemon_api, make_workspace, write_cell

HOUR_S = 3600.0


def _no_walk(root: Path) -> list[workspace.FlowRef]:
    raise AssertionError(f"`{root}` was walked")


def _age(session: FlowSession, api: Api) -> None:
    session.ran -= api.kernel_idle_s
    session.kernel.used -= api.kernel_idle_s
    session.touched -= api.session_idle_s


async def _ran(api: Api) -> FlowSession:
    await api.run({"flow": "churn", "target": "score"})
    session = api.hub.session("churn")
    assert session.kernel.state == "running"
    return session


@contextlib.asynccontextmanager
async def _streamed_api(
    root: Path, leases: Leases | None = None
) -> AsyncIterator[tuple[Api, Streams]]:
    streams = Streams()
    hub = Hub(streams=streams)
    held = leases if leases is not None else set()
    try:
        yield Api(hub, directory=root, leases=lambda: held), streams
    finally:
        await hub.close()


async def test_a_name_resolves_against_an_open_flow_without_a_walk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    home = make_workspace(tmp_path / "home", flows=())
    project = make_workspace(home / "work" / "ml", flows=("churn",))

    async with daemon_api(project) as api:
        await api.flow_open({"flow": "churn", "worktree": False})
        monkeypatch.setattr(workspace, "find_flows", _no_walk)
        from_home = api.resolve("churn", directory=home)
        from_project = api.resolve("churn.flow", directory=project)

    assert from_home.path == project / "churn.flow"
    assert from_home.relpath == "work/ml/churn.flow"
    assert from_project.relpath == "churn.flow"


async def test_a_name_prefers_the_open_flow_under_the_directory(tmp_path: Path):
    first = make_workspace(tmp_path / "first", flows=("churn",))
    second = make_workspace(tmp_path / "second", flows=("churn",))

    async with daemon_api(first) as api:
        await api.flow_open({"flow": "churn", "worktree": False})
        await api.flow_open(
            {"flow": "churn", "directory": str(second), "worktree": False}
        )
        here = api.resolve("churn", directory=second)

        with pytest.raises(FlowAmbiguous) as ambiguous:
            api.resolve("churn", directory=tmp_path)

    assert here.path == second / "churn.flow"
    assert str(first / "churn.flow") in str(ambiguous.value)
    assert str(second / "churn.flow") in str(ambiguous.value)


async def test_the_walk_is_kept_until_a_flow_is_made_renamed_or_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = make_workspace(tmp_path / "project", flows=("churn",))
    walked: list[Path] = []
    walk = workspace.find_flows

    def counted(directory: Path) -> list[workspace.FlowRef]:
        walked.append(directory)
        return walk(directory)

    monkeypatch.setattr(workspace, "find_flows", counted)

    async def names(api: Api) -> list[str]:
        listed = await api.workspace_list({})
        return [flow["name"] for flow in listed["flows"]]

    async with daemon_api(root) as api:
        assert await names(api) == ["churn"]
        assert await names(api) == ["churn"]
        assert len(walked) == 1

        await api.flow_init({"name": "sales"})
        assert await names(api) == ["churn", "sales"]
        await api.flow_rename({"flow": "sales", "name": "leads"})
        assert await names(api) == ["churn", "leads"]
        await api.flow_delete({"flow": "leads"})
        assert await names(api) == ["churn"]

    assert len(walked) == 4


async def test_a_listed_flow_is_found_by_name_without_walking_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = make_workspace(tmp_path / "project", flows=("churn",))

    async with daemon_api(root) as api:
        await api.workspace_list({})
        monkeypatch.setattr(workspace, "find_flows", _no_walk)
        ref = api.resolve("churn")

    assert ref.path == root / "churn.flow"


async def test_status_of_a_directory_opens_none_of_its_closed_flows(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn", "sales"))
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn", "worktree": False})
        status = await api.status({})
        opened = [session.ref.name for session in api.hub.opened()]

    churn, sales = status["flows"]
    assert opened == ["churn"]
    assert churn["open"] is True
    assert [cell["slug"] for cell in churn["cells"]] == ["score"]
    assert sales == {
        "flow": "sales",
        "path": str(root / "sales.flow"),
        "relative_path": "sales.flow",
        "open": False,
        "kernel": {"state": "stopped"},
    }
    assert status["active"] == {
        "open_flows": 1,
        "running_kernels": 0,
        "active_runs": 0,
        "leased_sessions": 0,
    }


async def test_open_flows_reports_what_keeps_each_one_active(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn",))
    other = make_workspace(tmp_path / "elsewhere", flows=("sales",))
    leases: Leases = {
        (str(root / "churn.flow"), "claude-1", "Claude"),
        (None, "x", "X"),
    }

    async with _streamed_api(root, leases) as (api, streams):
        await api.flow_open({"flow": "churn", "worktree": False})
        await api.flow_open(
            {"flow": "sales", "directory": str(other), "worktree": False}
        )
        subscription = streams.subscribe()
        subscription.journals.add(str(root / "churn.flow"))
        opened = await api.flows_open({})

    sales, churn = opened["flows"]
    assert opened["directory"] == str(root)
    assert set(churn) == {
        "flow",
        "path",
        "relative_path",
        "inside",
        "kernel",
        "active_runs",
        "leased_sessions",
        "stream_subscribers",
        "checked_out",
        "last_activity",
    }
    assert (churn["flow"], churn["relative_path"], churn["inside"]) == (
        "churn",
        "churn.flow",
        True,
    )
    assert (sales["path"], sales["relative_path"], sales["inside"]) == (
        str(other / "sales.flow"),
        None,
        False,
    )
    assert (churn["leased_sessions"], churn["stream_subscribers"]) == (1, 1)
    assert (sales["leased_sessions"], sales["stream_subscribers"]) == (0, 0)
    assert churn["kernel"] == "stopped" and churn["active_runs"] == 0
    assert churn["checked_out"] is False
    assert churn["last_activity"].endswith("Z")
    assert opened["totals"] == {
        "open_flows": 2,
        "running_kernels": 0,
        "active_runs": 0,
        "leased_sessions": 1,
    }


async def test_an_idle_flow_loses_its_kernel_then_its_session_but_not_its_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = make_workspace(tmp_path / "project", flows=("churn",))
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with _streamed_api(root) as (api, streams):
        await api.run({"flow": "churn", "target": "score"})
        session = api.hub.session("churn")
        subscription = streams.subscribe()
        subscription.journals.add(session.ref.address)
        assert session.kernel.state == "running"

        await api.sweep_idle()
        assert session.kernel.state == "running"

        _age(session, api)
        await api.sweep_idle()
        stopped = await subscription.next()
        assert session.kernel.state == "stopped"
        assert api.hub.attached(session.ref.path) is session

        await api.sweep_idle()
        assert api.hub.attached(session.ref.path) is session
        subscription.close()
        await api.sweep_idle()
        assert api.hub.attached(session.ref.path) is None
        assert api.hub.watches.roots() == []

        monkeypatch.setattr(workspace, "find_flows", _no_walk)
        ref = api.resolve("churn")
        reopened = await api.cells_list({"flow": "churn"})

    assert stopped["event"] == "kernel_state" and stopped["kernel"] == "stopped"
    assert ref.path == root / "churn.flow"
    assert [cell["slug"] for cell in reopened["cells"]] == ["score"]


async def test_a_leased_flow_is_never_closed_for_being_quiet(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn",))
    leases: Leases = {(str(root / "churn.flow"), "claude-1", "Claude")}

    async with _streamed_api(root, leases) as (api, _):
        await api.flow_open({"flow": "churn", "worktree": False})
        session = api.hub.session("churn")
        session.touched -= 10 * HOUR_S
        await api.sweep_idle()

        assert api.hub.attached(session.ref.path) is session


async def test_the_idle_limits_come_from_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = make_workspace(tmp_path / "project", flows=("churn",))
    monkeypatch.setenv("LUMLFLOW_KERNEL_IDLE_S", "5")
    monkeypatch.setenv("LUMLFLOW_SESSION_IDLE_S", "0")

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn", "worktree": False})
        session = api.hub.session("churn")
        session.touched -= 10 * HOUR_S
        await api.sweep_idle()

        assert (api.kernel_idle_s, api.session_idle_s) == (5.0, 0.0)
        assert api.hub.attached(session.ref.path) is session


async def test_an_open_flow_elsewhere_does_not_shadow_an_unseen_one_beneath(
    tmp_path: Path,
):
    elsewhere = make_workspace(tmp_path / "a", flows=("churn",))
    asked = make_workspace(tmp_path / "b", flows=())
    beneath = make_workspace(asked / "proj", flows=("churn",)) / "churn.flow"
    unrelated = make_workspace(tmp_path / "c", flows=())

    async with daemon_api(elsewhere) as api:
        await api.flow_open({"flow": "churn", "worktree": False})
        nested = api.resolve("churn", directory=asked)
        direct = api.resolve("churn", directory=asked / "proj")
        fallback = api.resolve("churn", directory=unrelated)

    assert nested.path == beneath
    assert direct.path == beneath
    assert fallback.path == elsewhere / "churn.flow"


async def test_two_open_flows_elsewhere_are_ambiguous(tmp_path: Path):
    first = make_workspace(tmp_path / "first", flows=("churn",))
    second = make_workspace(tmp_path / "second", flows=("churn",))
    unrelated = make_workspace(tmp_path / "unrelated", flows=())

    async with daemon_api(first) as api:
        await api.flow_open({"flow": "churn", "worktree": False})
        await api.flow_open(
            {"flow": "churn", "directory": str(second), "worktree": False}
        )

        with pytest.raises(FlowAmbiguous):
            api.resolve("churn", directory=unrelated)


async def test_a_flow_renamed_or_made_by_hand_is_found_despite_the_walk_cache(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project", flows=("churn",))
    empty = make_workspace(tmp_path / "empty", flows=())

    async with daemon_api(root) as api:
        await api.workspace_list({})
        await api.workspace_list({"directory": str(empty)})
        (root / "churn.flow").rename(root / "leads.flow")
        make_workspace(empty, flows=("sales",))

        renamed = api.resolve("leads")
        made = api.resolve(None, directory=empty)

    assert renamed.path == root / "leads.flow"
    assert made.path == empty / "sales.flow"


async def test_a_request_during_a_close_keeps_the_one_session(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn",))
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with _streamed_api(root) as (api, _):
        session = await _ran(api)
        _age(session, api)
        closing = asyncio.create_task(
            api.hub.close_session(
                session,
                still=lambda held: api._session_idle(held, time.monotonic()),
            )
        )
        await asyncio.sleep(0)
        during = api.hub.open(session.ref)
        closed = await closing
        listed = await api.cells_list({"flow": "churn"})

        assert during is session
        assert closed is False
        assert api.hub.opened() == [session]
        assert [cell["slug"] for cell in listed["cells"]] == ["score"]


async def test_a_kernel_call_or_a_run_in_flight_keeps_the_kernel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = make_workspace(tmp_path / "project", flows=("churn",))
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with _streamed_api(root) as (api, _):
        session = await _ran(api)
        _age(session, api)
        pending = asyncio.get_running_loop().create_future()
        session.kernel._pending[0] = pending
        await api.sweep_idle()
        assert session.kernel.state == "running"
        del session.kernel._pending[0]
        pending.cancel()

        with monkeypatch.context() as patched:
            patched.setattr(type(session.queue), "in_flight", property(lambda _: 1))
            await api.sweep_idle()
            assert session.kernel.state == "running"

        await api.sweep_idle()
        assert session.kernel.state == "stopped"


async def test_a_browser_subscribed_to_a_flow_keeps_it_open(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn",))

    async with _streamed_api(root) as (api, streams):
        subscription = streams.subscribe()
        web._subscribed(
            api.hub,
            api,
            streams,
            subscription,
            {"subscribe": "journal", "flow": "churn"},
        )
        session = api.hub.session("churn")
        _age(session, api)
        await api.sweep_idle()
        assert api.hub.attached(session.ref.path) is session

        subscription.close()
        await api.sweep_idle()
        assert api.hub.attached(session.ref.path) is None


async def test_listing_flows_is_not_using_them(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn",))
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with _streamed_api(root) as (api, _):
        session = await _ran(api)
        _age(session, api)
        before = (session.touched, session.ran, session.kernel.used)
        await api.status({})
        await api.flows_open({})
        await api.gc_sweep({})

        assert (session.touched, session.ran, session.kernel.used) == before


async def test_a_run_started_while_a_close_stops_the_reactor_is_not_killed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = make_workspace(tmp_path / "project", flows=("churn",))
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with _streamed_api(root) as (api, _):
        await api.flow_open({"flow": "churn", "worktree": False})
        session = api.hub.session("churn")
        _age(session, api)
        released = asyncio.Event()
        stop = session.reactor.stop

        async def held() -> None:
            await released.wait()
            await stop()

        monkeypatch.setattr(session.reactor, "stop", held)
        closing = asyncio.create_task(
            api.hub.close_session(
                session,
                still=lambda held: api._session_idle(held, time.monotonic()),
            )
        )
        await asyncio.sleep(0)
        running = asyncio.create_task(api.run({"flow": "churn", "target": "score"}))
        for _ in range(1000):
            if session.kernel.state == "running" or running.done():
                break
            await asyncio.sleep(0.01)
        released.set()
        closed = await closing
        ran = await running

        assert closed is False
        assert ran["executed"] == ["score"] and not ran["failed"]
        assert api.hub.attached(session.ref.path) is session
