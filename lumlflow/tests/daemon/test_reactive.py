"""Reactivity end to end: an edit lands, and the cheap closure runs itself.

The planner's own tests say what `auto` *decides*. These say the daemon acts on
it — which is the half that was missing, and the reason the setting read as
broken from the workbench. Every edit here arrives through a door a user or an
agent actually uses: the edit verb, or the file plane the watcher reconciles.
"""

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from lumlflow.flow.daemon import queries, workspace
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.daemon.hub import FlowSession, Hub
from lumlflow.flow.daemon.reactive import AUTO_ACTOR
from lumlflow.flow.daemon.stream import StateName, Streams
from lumlflow.flow.errors import KernelError
from lumlflow.flow.store.models import CellNoted, RunRecorded

from tests.daemon.helpers import (
    REPORT_CELL,
    SCORE_CELL,
    daemon_api,
    make_workspace,
    ops_of,
    slugs,
    source_of,
    transactions,
    write_cell,
    write_file,
    write_lock,
)

EDITED_SCORE = """
class Score:
    \"\"\"The headline metric, moved.\"\"\"
    produces = {"summary": "asset"}

    def materialize(self, ctx):
        return {"summary": {"auc": 0.93}}
"""

EDITED_SCORE_AGAIN = """
class Score:
    \"\"\"The headline metric, moved again.\"\"\"
    produces = {"summary": "asset"}

    def materialize(self, ctx):
        return {"summary": {"auc": 0.95}}
"""

UNRESOLVABLE_CELL = """
class Alpha:
    \"\"\"Consumes a cell this lane does not have.\"\"\"
    consumes = {"summary": "nowhere.summary"}
    produces = {"result": "asset"}

    def materialize(self, ctx, summary):
        return {"result": summary}
"""

ZETA_CELL = """
class Zeta:
    \"\"\"An independent target.\"\"\"
    produces = {"result": "asset"}

    def materialize(self, ctx):
        return {"result": 1}
"""

EDITED_ZETA = ZETA_CELL.replace('return {"result": 1}', 'return {"result": 2}')


async def settle(api: Api, flow: str = "churn") -> None:
    """Wait out the sweep the last call armed, as the daemon's loop would."""
    await api.hub.session(flow).reactor.settled()


def cell_named(listed: dict[str, Any], slug: str) -> dict[str, Any]:
    return next(cell for cell in listed["cells"] if cell["slug"] == slug)


def auto_runs(api: Api, flow: str = "churn") -> list[str]:
    """Cells materialized by nobody's request, in the order they ran."""
    return [
        op.uid
        for entry in transactions(api.hub.session(flow))
        if entry.actor == AUTO_ACTOR
        for op in entry.ops
        if isinstance(op, RunRecorded)
    ]


def refresh_notes(session: FlowSession) -> list[CellNoted]:
    return [
        note for note in ops_of(session, CellNoted) if note.kind == "refresh_failed"
    ]


async def refuse_kernel_start(
    session: FlowSession, monkeypatch: Any
) -> Callable[[], Awaitable[dict[str, Any]]]:
    await session.kernel.stop()
    original = session.kernel.ensure_started

    async def cannot_start() -> dict[str, Any]:
        raise KernelError("the workspace interpreter cannot start")

    monkeypatch.setattr(session.kernel, "ensure_started", cannot_start)
    return original


async def prepare_failed_refresh(
    api: Api, monkeypatch: Any, *, source: str = EDITED_SCORE
) -> tuple[FlowSession, Callable[[], Awaitable[dict[str, Any]]]]:
    listed = await api.cells_list({"flow": "churn"})
    target = "report" if "report" in slugs(listed) else "score"
    await api.run({"flow": "churn", "target": target})
    await settle(api)
    await api.settings_set(
        {"flow": "churn", "reactivity": "auto", "eager_cost_threshold_s": 60}
    )
    await settle(api)
    session = api.hub.session("churn")
    original = await refuse_kernel_start(session, monkeypatch)
    await api.cells_edit({"flow": "churn", "slug": "score", "source": source})
    await settle(api)
    return session, original


async def timed(api: Api) -> None:
    """Run the flow once, which is what gives reactivity a cost to weigh."""
    await api.run({"flow": "churn", "target": "report"})
    await settle(api)


async def test_an_edit_refreshes_the_cheap_closure_without_being_asked(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_cell(root / "churn.flow", "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await timed(api)
        await api.settings_set(
            {"flow": "churn", "reactivity": "auto", "eager_cost_threshold_s": 60}
        )
        await api.cells_edit({"flow": "churn", "slug": "score", "source": EDITED_SCORE})
        await settle(api)
        listed = await api.cells_list({"flow": "churn"})

        assert slugs(listed, "synced") == ["report", "score"]
        # Attributed to nobody: a run the user never asked for is not the
        # user's, and the timeline says so.
        assert len(auto_runs(api)) == 2
        assert cell_named(listed, "report")["auto_declined"] is None


async def test_an_edit_on_disk_refreshes_it_too(tmp_path: Path):
    """The watcher's door, driven through the reconciliation it calls."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_cell(root / "churn.flow", "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await timed(api)
        write_cell(root / "churn.flow", "score", EDITED_SCORE)
        # What `Watcher.flush` does with a path in hand, and the only part of
        # it that is not the observer thread.
        await api.hub.quiesce(api.hub.session("churn"), tier="live")
        await settle(api)
        listed = await api.cells_list({"flow": "churn"})

    assert slugs(listed, "synced") == ["report", "score"]


async def test_a_closure_over_the_threshold_waits_and_says_why(tmp_path: Path):
    """The silence that made this feel broken: the card now carries a reason."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_cell(root / "churn.flow", "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await timed(api)
        await api.settings_set(
            {"flow": "churn", "reactivity": "auto", "eager_cost_threshold_s": 0.0}
        )
        await api.cells_edit({"flow": "churn", "slug": "score", "source": EDITED_SCORE})
        await settle(api)
        listed = await api.cells_list({"flow": "churn"})

    assert slugs(listed, "unsynced") == ["score"]
    assert auto_runs(api) == []
    declined = cell_named(listed, "score")["auto_declined"]
    assert declined["reason"] == "too-expensive"
    assert declined["estimate_seconds"] > 0


async def test_opening_a_flow_nobody_has_run_starts_nothing(tmp_path: Path):
    """Auto keeps results fresh; it does not decide to compute them the first
    time. A closure with no measured cost is not a cheap one."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_cell(root / "churn.flow", "report", REPORT_CELL)

    async with daemon_api(root) as api:
        listed = await api.cells_list({"flow": "churn"})
        await settle(api)
        after = await api.cells_list({"flow": "churn"})

    assert slugs(listed, "unmaterialized") == ["report", "score"]
    assert slugs(after, "unmaterialized") == ["report", "score"]
    assert auto_runs(api) == []
    assert cell_named(after, "score")["auto_declined"]["reason"] == "never-timed"


async def test_opening_a_flow_catches_up_on_what_it_left_unsynced(tmp_path: Path):
    """A daemon that was not running is the case reactivity exists for: the
    edits landed as one offline transaction, and nothing has run since."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_cell(root / "churn.flow", "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await timed(api)

    write_cell(root / "churn.flow", "score", EDITED_SCORE)

    async with daemon_api(root) as api:
        await api.cells_list({"flow": "churn"})
        await settle(api)
        listed = await api.cells_list({"flow": "churn"})

    assert slugs(listed, "synced") == ["report", "score"]
    assert len(auto_runs(api)) == 2


async def test_lazy_refreshes_nothing_and_claims_nothing(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_cell(root / "churn.flow", "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await timed(api)
        await api.settings_set({"flow": "churn", "reactivity": "lazy"})
        await api.cells_edit({"flow": "churn", "slug": "score", "source": EDITED_SCORE})
        await settle(api)
        listed = await api.cells_list({"flow": "churn"})

    assert slugs(listed, "unsynced") == ["score"]
    assert auto_runs(api) == []
    # Off is not "declined": there is no verdict to render either way.
    assert cell_named(listed, "score")["auto_declined"] is None


async def test_turning_reactivity_on_takes_up_what_lazy_left_behind(tmp_path: Path):
    """Flipping the switch is a decision about the cells that are stale now."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_cell(root / "churn.flow", "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await timed(api)
        await api.settings_set({"flow": "churn", "reactivity": "lazy"})
        await api.cells_edit({"flow": "churn", "slug": "score", "source": EDITED_SCORE})
        await settle(api)
        stale = await api.cells_list({"flow": "churn"})

        await api.settings_set({"flow": "churn", "reactivity": "auto"})
        await settle(api)
        listed = await api.cells_list({"flow": "churn"})

    assert slugs(stale, "unsynced") == ["score"]
    assert slugs(listed, "synced") == ["report", "score"]


async def test_the_eager_opt_in_takes_a_cell_the_threshold_refused(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_cell(root / "churn.flow", "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await timed(api)
        await api.settings_set(
            {"flow": "churn", "reactivity": "auto", "eager_cost_threshold_s": 0.0}
        )
        await api.cells_edit({"flow": "churn", "slug": "score", "source": EDITED_SCORE})
        await settle(api)
        refused = await api.cells_list({"flow": "churn"})

        await api.cells_eager({"flow": "churn", "slug": "score", "eager": True})
        await settle(api)
        listed = await api.cells_list({"flow": "churn"})

    assert slugs(refused, "unsynced") == ["score"]
    assert slugs(listed, "synced") == ["score"]
    assert cell_named(listed, "score")["auto_declined"] is None


async def test_reading_a_slice_does_not_ask_reactivity_anything(tmp_path: Path):
    """Answering costs a plan and a preflight per stale cell.

    Every verb that names a cell reads a slice first, and most of them — paging
    a value, previewing, diffing — never render a verdict. Asking eagerly put
    a third of a second on a forty-cell flow's every call.
    """
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_cell(root / "churn.flow", "report", REPORT_CELL)

    async with daemon_api(root) as api:
        session = api.hub.open(workspace.select_flow(root, name="churn"))
        asked = 0
        verdicts = session.planner.auto_verdicts

        def counted(branch: str) -> Any:
            nonlocal asked
            asked += 1
            return verdicts(branch)

        session.planner.auto_verdicts = counted  # type: ignore[method-assign]

        here = queries.read(session, "main")
        assert asked == 0

        # One card's worth of facts is one ask, cached on the slice however
        # many cells are read off it.
        queries.cell(here, here.uid_of("score"))
        queries.cell(here, here.uid_of("report"))
        assert asked == 1


async def test_a_cell_that_failed_is_not_retried_until_it_is_edited(
    tmp_path: Path,
):
    """Otherwise reactivity is a loop that reruns a broken cell forever."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await timed_score(api)
        write_cell(root / "churn.flow", "score", BREAKING_SCORE)
        await api.hub.quiesce(api.hub.session("churn"), tier="live")
        await settle(api)
        failed = await api.cells_list({"flow": "churn"})
        runs_after_failure = len(auto_runs(api))

        # Nothing has changed since it failed. A second sweep must not try again.
        await api.hub.quiesce(api.hub.session("churn"), tier="live")
        api.hub.session("churn").reactor.arm()
        await settle(api)
        again = await api.cells_list({"flow": "churn"})

    assert slugs(failed, "failed") == ["score"]
    assert slugs(again, "failed") == ["score"]
    assert len(auto_runs(api)) == runs_after_failure


BREAKING_SCORE = """
class Score:
    \"\"\"The headline metric, broken.\"\"\"
    produces = {"summary": "asset"}

    def materialize(self, ctx):
        raise ValueError("the model did not converge")
"""


async def timed_score(api: Api) -> None:
    await api.run({"flow": "churn", "target": "score"})
    await settle(api)


async def test_a_forked_lane_refreshes_without_touching_the_worktree(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow_dir = root / "churn.flow"
    write_cell(flow_dir, "score", SCORE_CELL)
    write_cell(flow_dir, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await timed(api)
        await api.settings_set(
            {"flow": "churn", "reactivity": "auto", "eager_cost_threshold_s": 60}
        )
        await settle(api)
        await api.fork({"flow": "churn", "name": "sweep"})
        before = source_of(flow_dir, "score")

        await api.cells_edit(
            {
                "flow": "churn",
                "branch": "sweep",
                "slug": "score",
                "source": EDITED_SCORE,
            }
        )
        await settle(api)
        sweep = await api.cells_list({"flow": "churn", "branch": "sweep"})
        main = await api.cells_list({"flow": "churn", "branch": "main"})
        session = api.hub.session("churn")
        sweep_id = session.store.branches.get("sweep").branch_id
        swept = [
            op
            for entry in transactions(session)
            if entry.actor == AUTO_ACTOR and entry.branch == sweep_id
            for op in entry.ops
            if isinstance(op, RunRecorded)
        ]

    assert slugs(sweep, "synced") == ["report", "score"]
    assert slugs(main, "synced") == ["report", "score"]
    assert len(swept) == 2
    assert {run.branch_id for run in swept} == {sweep_id}
    assert source_of(flow_dir, "score") == before


async def test_an_unresolvable_target_is_declined_while_another_runs(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow_dir = root / "churn.flow"
    write_cell(flow_dir, "alpha", UNRESOLVABLE_CELL)
    write_cell(flow_dir, "zeta", ZETA_CELL)

    async with daemon_api(root) as api:
        await api.run({"flow": "churn", "target": "zeta"})
        await api.cells_eager({"flow": "churn", "slug": "alpha", "eager": True})
        await api.settings_set(
            {"flow": "churn", "reactivity": "auto", "eager_cost_threshold_s": 60}
        )
        await api.cells_edit({"flow": "churn", "slug": "zeta", "source": EDITED_ZETA})
        session = api.hub.session("churn")
        zeta_uid = session.store.branches.resolve("main", "zeta")
        before = len(transactions(session))
        verdicts = {
            verdict.slug: verdict
            for verdict in session.planner.auto_verdicts("main").values()
        }

        assert verdicts["alpha"].reason == "unresolvable-reference"
        assert "nowhere.summary" in str(verdicts["alpha"].detail)
        assert verdicts["zeta"].taken

        await settle(api)
        listed = await api.cells_list({"flow": "churn"})
        after = len(transactions(session))
        session.reactor.arm()
        await settle(api)

    declined = cell_named(listed, "alpha")["auto_declined"]
    assert declined["reason"] == "unresolvable-reference"
    assert "nowhere.summary" in declined["detail"]
    assert cell_named(listed, "zeta")["state"] == "synced"
    assert auto_runs(api) == [zeta_uid]
    assert after > before
    assert len(transactions(session)) == after
    assert refresh_notes(session) == []


async def test_kernel_start_failures_are_recorded_once_and_retried_after_restart(
    tmp_path: Path, monkeypatch: Any
) -> None:
    root = make_workspace(tmp_path / "project")
    flow_dir = root / "churn.flow"
    write_cell(flow_dir, "score", SCORE_CELL)
    write_cell(flow_dir, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        session, _ = await prepare_failed_refresh(api, monkeypatch)
        first_notes = refresh_notes(session)
        failed_entries = [
            entry
            for entry in transactions(session)
            if any(
                isinstance(op, CellNoted) and op.kind == "refresh_failed"
                for op in entry.ops
            )
        ]
        listed = await api.cells_list({"flow": "churn"})
        session.reactor.arm()
        await settle(api)

        assert len(first_notes) == 2
        assert len(failed_entries) == 2
        assert all(entry.actor == "system" for entry in failed_entries)
        assert all(
            note.sentence.startswith("could not refresh: ") for note in first_notes
        )
        assert {
            cell_named(listed, slug)["auto_declined"]["reason"]
            for slug in ("score", "report")
        } == {"refresh-failed"}
        assert refresh_notes(session) == first_notes
        first_steps = [entry.step for entry in failed_entries]

    async with daemon_api(root) as api:
        session = api.hub.open(workspace.select_flow(root, name="churn"))
        await refuse_kernel_start(session, monkeypatch)
        reopened = session.planner.auto_verdicts("main")

        assert reopened
        assert all(verdict.taken for verdict in reopened.values())

        await settle(api)
        all_failed_entries = [
            entry
            for entry in transactions(session)
            if any(
                isinstance(op, CellNoted) and op.kind == "refresh_failed"
                for op in entry.ops
            )
        ]

    assert [entry.step for entry in all_failed_entries[:2]] == first_steps
    assert len(all_failed_entries) == 4
    assert len(refresh_notes(session)) == 4


async def test_a_kernel_restart_lifts_a_refresh_failure(
    tmp_path: Path, monkeypatch: Any
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        session, original = await prepare_failed_refresh(api, monkeypatch)
        monkeypatch.setattr(session.kernel, "ensure_started", original)

        await api.kernel_restart({"flow": "churn"})
        await settle(api)
        listed = await api.cells_list({"flow": "churn"})

    assert cell_named(listed, "score")["state"] == "synced"
    assert cell_named(listed, "score")["auto_declined"] is None
    assert len(refresh_notes(session)) == 1


async def test_an_environment_change_lifts_a_refresh_failure(
    tmp_path: Path, monkeypatch: Any
) -> None:
    root = make_workspace(tmp_path / "project")
    write_lock(root, {"pandas": "1.0.0"})
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        session, original = await prepare_failed_refresh(api, monkeypatch)
        monkeypatch.setattr(session.kernel, "ensure_started", original)
        note_step = next(
            note.step
            for note in session.store.index.cell_notes(
                session.store.branches.get("main").branch_id,
                session.store.branches.resolve("main", "score"),
            )
            if note.kind == "refresh_failed"
        )
        write_lock(root, {"pandas": "2.0.0"})

        await api.status({})
        assert session.store.index.env_changed_step() > note_step
        await settle(api)
        listed = await api.cells_list({"flow": "churn"})

    assert cell_named(listed, "score")["state"] == "synced"
    assert cell_named(listed, "score")["auto_declined"] is None


async def test_a_workspace_code_change_lifts_a_refresh_failure(
    tmp_path: Path, monkeypatch: Any
) -> None:
    root = make_workspace(tmp_path / "project", files={"helpers.py": "VALUE = 1\n"})
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        session, original = await prepare_failed_refresh(api, monkeypatch)
        monkeypatch.setattr(session.kernel, "ensure_started", original)
        write_file(root / "helpers.py", "VALUE = 2\n")

        await api.status({})
        await settle(api)
        listed = await api.cells_list({"flow": "churn"})

    assert cell_named(listed, "score")["state"] == "synced"
    assert cell_named(listed, "score")["auto_declined"] is None


async def test_an_explicit_run_lifts_downstream_refresh_failures(
    tmp_path: Path, monkeypatch: Any
) -> None:
    root = make_workspace(tmp_path / "project")
    flow_dir = root / "churn.flow"
    write_cell(flow_dir, "score", SCORE_CELL)
    write_cell(flow_dir, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        session, original = await prepare_failed_refresh(api, monkeypatch)
        assert len(refresh_notes(session)) == 2
        monkeypatch.setattr(session.kernel, "ensure_started", original)
        report_uid = session.store.branches.resolve("main", "report")

        outcome = await api.run({"flow": "churn", "target": "score"})
        await settle(api)
        listed = await api.cells_list({"flow": "churn"})

    assert outcome["executed"] == ["score"]
    assert slugs(listed, "synced") == ["report", "score"]
    assert all(cell["auto_declined"] is None for cell in listed["cells"])
    assert auto_runs(api) == [report_uid]
    assert len(refresh_notes(session)) == 2


async def test_cell_and_input_edits_lift_refresh_failures(
    tmp_path: Path, monkeypatch: Any
) -> None:
    root = make_workspace(tmp_path / "project")
    flow_dir = root / "churn.flow"
    write_cell(flow_dir, "score", SCORE_CELL)
    write_cell(flow_dir, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        session, original = await prepare_failed_refresh(api, monkeypatch)
        assert len(refresh_notes(session)) == 2
        monkeypatch.setattr(session.kernel, "ensure_started", original)

        await api.cells_edit(
            {"flow": "churn", "slug": "score", "source": EDITED_SCORE_AGAIN}
        )
        await settle(api)
        listed = await api.cells_list({"flow": "churn"})

    assert slugs(listed, "synced") == ["report", "score"]
    assert all(cell["auto_declined"] is None for cell in listed["cells"])


async def test_archived_lanes_are_not_swept(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")
    flow_dir = root / "churn.flow"
    write_cell(flow_dir, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await timed_score(api)
        await api.settings_set(
            {"flow": "churn", "reactivity": "auto", "eager_cost_threshold_s": 60}
        )
        await settle(api)
        await api.fork({"flow": "churn", "name": "old"})
        await api.archive({"flow": "churn", "branch": "old"})
        session = api.hub.session("churn")
        old_id = session.store.branches.get("old").branch_id

        await api.cells_edit(
            {
                "flow": "churn",
                "branch": "old",
                "slug": "score",
                "source": EDITED_SCORE,
            }
        )
        await settle(api)
        listed = await api.cells_list({"flow": "churn", "branch": "old"})
        runs = [
            op
            for entry in transactions(session)
            if entry.actor == AUTO_ACTOR and entry.branch == old_id
            for op in entry.ops
            if isinstance(op, RunRecorded)
        ]

    assert cell_named(listed, "score")["state"] == "unsynced"
    assert runs == []


async def test_taking_a_target_pushes_refreshing_for_its_lane(
    tmp_path: Path, monkeypatch: Any
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    streams = Streams()
    hub = Hub(streams=streams)
    api = Api(hub, directory=root)
    states: list[dict[str, Any]] = []

    def record_state(
        flow: str,
        state: StateName,
        *,
        step: int,
        lane: str | None = None,
        cell: str | None = None,
    ) -> None:
        states.append(
            {"flow": flow, "state": state, "step": step, "lane": lane, "cell": cell}
        )

    monkeypatch.setattr(streams, "state", record_state)
    try:
        await timed_score(api)
        await api.settings_set(
            {"flow": "churn", "reactivity": "auto", "eager_cost_threshold_s": 60}
        )
        await settle(api)
        states.clear()

        await api.cells_edit({"flow": "churn", "slug": "score", "source": EDITED_SCORE})
        await settle(api)
    finally:
        await hub.close()

    assert [state["state"] for state in states] == ["refreshing"]
    assert states[0]["lane"] == "main"
    assert states[0]["cell"] == "score"
