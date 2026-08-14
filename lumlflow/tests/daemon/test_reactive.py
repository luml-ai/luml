"""Reactivity end to end: an edit lands, and the cheap closure runs itself.

The planner's own tests say what `auto` *decides*. These say the daemon acts on
it — which is the half that was missing, and the reason the setting read as
broken from the workbench. Every edit here arrives through a door a user or an
agent actually uses: the edit verb, or the file plane the watcher reconciles.
"""

from pathlib import Path
from typing import Any

from lumlflow.flow.daemon import queries
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.daemon.reactive import AUTO_ACTOR
from lumlflow.flow.store.models import RunRecorded

from tests.daemon.helpers import (
    REPORT_CELL,
    SCORE_CELL,
    daemon_api,
    make_workspace,
    slugs,
    transactions,
    write_cell,
)

EDITED_SCORE = """
class Score:
    \"\"\"The headline metric, moved.\"\"\"
    produces = {"summary": "asset"}

    def materialize(self, ctx):
        return {"summary": {"auc": 0.93}}
"""


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
        await api.cells_edit(
            {"flow": "churn", "slug": "score", "source": EDITED_SCORE}
        )
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
        await api.cells_edit(
            {"flow": "churn", "slug": "score", "source": EDITED_SCORE}
        )
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
        await api.cells_edit(
            {"flow": "churn", "slug": "score", "source": EDITED_SCORE}
        )
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
        await api.cells_edit(
            {"flow": "churn", "slug": "score", "source": EDITED_SCORE}
        )
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
        await api.cells_edit(
            {"flow": "churn", "slug": "score", "source": EDITED_SCORE}
        )
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
        session = api.hub.session("churn")
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
