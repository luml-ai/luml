"""Reconciliation over a real workspace: the quiesce race, cold starts, and
the file-plane changes that are not edits — deletions, renames, shared code.

Nothing here is stubbed. The files are files and the store is a store, because
what is under test is precisely whether the two agree.
"""

import asyncio
from pathlib import Path
from typing import Any

from lumlflow.flow import render
from lumlflow.flow.daemon import workspace
from lumlflow.flow.daemon.reconcile import MIXED_EDITING
from lumlflow.flow.daemon.watcher import Watcher
from lumlflow.flow.dsl import tree as workspace_tree
from lumlflow.flow.dsl.accept import Acceptance
from lumlflow.flow.store.models import (
    CellAccepted,
    CellNoted,
    CellRemoved,
    FlagSet,
    Renamed,
    WorkspaceCodeChanged,
)

from tests.daemon.helpers import (
    REPORT_CELL,
    SCORE_CELL,
    cell_files,
    daemon_api,
    make_workspace,
    ops_of,
    slice_of,
    slugs,
    source_of,
    transactions,
    values_in,
    write_cell,
    write_file,
)

HELPER_CELL = """
class Score:
    \"\"\"Leans on the workspace's shared code.\"\"\"
    produces = {"summary": "asset"}

    def materialize(self, ctx):
        import helpers

        return {"summary": {"auc": helpers.AUC}}
"""


async def test_a_write_then_run_never_waits_for_the_watcher(tmp_path: Path):
    """The quiesce contract: an agent that writes a cell and runs it
    milliseconds later runs what it just wrote, whether or not any event
    arrived. The watcher here is armed with a debounce longer than the test —
    if it were load-bearing, the second run would execute the old version."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        watcher = Watcher(api.hub, debounce_s=600)
        watcher.start()
        try:
            await api.run({"flow": "churn", "target": "score"})
            write_cell(root / "churn.flow", "score", SCORE_CELL.replace("0.91", "0.93"))
            outcome = await api.run({"flow": "churn", "target": "score"})
        finally:
            await watcher.stop()

    assert outcome["executed"] == ["score"]
    assert values_in(root / "churn.flow") == [{"auc": 0.91}, {"auc": 0.93}]


async def test_cold_start_lands_offline_edits_as_one_coarse_transaction(
    tmp_path: Path,
):
    """The fine-grained sequence genuinely was not recorded, so one transaction
    says so — actor `user`, flagged offline, and an intent that counts rather
    than narrates. Identity is minted and validated exactly as it is live."""
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    for slug in ("score", "report", "summary"):
        write_cell(flow, slug, SCORE_CELL.replace("Score", slug.title()))

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        before = {
            slug: version.uid
            for slug, version in slice_of(api.hub.session("churn"), "main").items()
        }
        steps = len(transactions(api.hub.session("churn")))

    for slug in ("score", "report", "summary"):
        write_cell(flow, slug, source_of(flow, slug).replace("0.91", "0.93"))
    write_cell(flow, "extra", SCORE_CELL.replace("Score", "Extra"))

    async with daemon_api(root) as api:
        session = api.hub.open(workspace.select_flow(root, name="churn"))
        landed = transactions(session)[steps:]
        after = {
            slug: version.uid for slug, version in slice_of(session, "main").items()
        }

    assert len(landed) == 1
    offline = landed[0]
    assert (offline.actor, offline.offline) == ("user", True)
    assert offline.intent == "offline edits: 4 cells changed"
    # The three that existed kept their identity; the new one was minted and
    # written back into its file, exactly as a live acceptance would.
    assert {slug: after[slug] for slug in before} == before
    assert after["extra"] in source_of(flow, "extra")


async def test_the_offline_burst_reads_back_as_the_one_coarse_entry_it_is(
    tmp_path: Path,
):
    """One transaction in the journal has to read as one entry in the brief,
    labelled for what it is — an ordinary-looking burst would claim a sequence
    nobody recorded."""
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})

    write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.93"))
    write_cell(flow, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        brief = await api.context({"flow": "churn"})

    latest = brief["recent"][0]
    coarse = f"step {latest['step']} · user · offline edits: 2 cells changed · offline"
    assert (latest["actor"], latest["offline"]) == ("user", True)
    assert latest["intent"] == "offline edits: 2 cells changed"
    assert [line.strip() for line in render.context(brief)].count(coarse) == 1


async def test_re_applying_an_edit_a_rewind_took_back_keeps_it(tmp_path: Path):
    """Bytes the store has seen before are a projection it still owes only when
    they predate the head. After a rewind the same edit is an edit again —
    reading it as a projection would overwrite the author's file with the head
    and accept nothing in its place."""
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        at = session.store.next_step - 1

        write_cell(flow, "score", source_of(flow, "score").replace("0.91", "0.93"))
        await api.status({"flow": "churn"})
        await api.rewind({"flow": "churn", "to_step": at})
        rewound = source_of(flow, "score")

        # The author makes the same edit again, in place, by hand.
        write_cell(flow, "score", source_of(flow, "score").replace("0.91", "0.93"))
        await api.status({"flow": "churn"})
        head = slice_of(session, "main")["score"]
        stored = session.store.objects.get(head.raw_source_ref).decode("utf-8")
        on_disk = source_of(flow, "score")

    assert "0.91" in rewound
    assert "0.93" in on_disk
    assert "0.93" in stored


async def test_an_older_version_from_another_lane_lands_as_an_offline_edit(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        await api.fork({"flow": "churn", "name": "exp"})
        await api.switch({"flow": "churn", "branch": "exp"})
        await api.cells_edit(
            {
                "flow": "churn",
                "slug": "score",
                "source": SCORE_CELL.replace("0.91", "0.92"),
            }
        )
        exp_version = slice_of(session, "exp")["score"]
        exp_source = session.store.objects.get(exp_version.raw_source_ref)

        await api.switch({"flow": "churn", "branch": "main"})
        await api.cells_edit(
            {
                "flow": "churn",
                "slug": "score",
                "source": SCORE_CELL.replace("0.91", "0.93"),
            }
        )
        main_before = slice_of(session, "main")["score"]
        landed_at = len(transactions(session))

        (flow / "cells" / "score.py").write_bytes(exp_source)
        await api.status({"flow": "churn"})

        main_after = slice_of(session, "main")["score"]
        landed = transactions(session)[landed_at:]

    assert len(landed) == 1
    assert landed[0].actor == "user"
    assert not any(isinstance(op, CellNoted) for op in landed[0].ops)
    assert main_after.version_id != main_before.version_id
    assert main_after.parent_version_id == main_before.version_id
    assert main_after.raw_source_ref == exp_version.raw_source_ref
    assert source_of(flow, "score").encode() == exp_source


async def test_a_same_lane_hand_revert_is_completed_noted_and_rewindable(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        older = slice_of(session, "main")["score"]
        older_source = session.store.objects.get(older.raw_source_ref)
        await api.cells_edit(
            {
                "flow": "churn",
                "slug": "score",
                "source": SCORE_CELL.replace("0.91", "0.93"),
            }
        )
        selected = slice_of(session, "main")["score"]
        selected_source = session.store.objects.get(selected.raw_source_ref)
        main_branch_id = session.store.branches.get("main").branch_id
        landed_at = len(transactions(session))

        (flow / "cells" / "score.py").write_bytes(older_source)
        await api.status({"flow": "churn"})

        landed = transactions(session)[landed_at:]
        head = slice_of(session, "main")["score"]
        completed_source = (flow / "cells" / "score.py").read_bytes()
        brief = await api.context({"flow": "churn"})

        await api.rewind({"flow": "churn", "to_step": older.created_step})
        rewound = slice_of(session, "main")["score"]
        rewound_source = (flow / "cells" / "score.py").read_bytes()

    assert len(landed) == 1
    (noted,) = landed
    assert (noted.actor, noted.branch) == ("system", main_branch_id)
    assert len(noted.ops) == 1
    note = noted.ops[0]
    assert isinstance(note, CellNoted)
    assert (note.uid, note.kind, note.version_id) == (
        selected.uid,
        "projection_completed",
        selected.version_id,
    )
    assert "score" in note.sentence
    assert selected.version_id in note.sentence
    assert "rewind" in note.sentence
    assert noted.intent == note.sentence
    assert head.version_id == selected.version_id
    assert completed_source == selected_source
    assert brief["recent"][0]["step"] == noted.step
    assert brief["recent"][0]["intent"] == note.sentence
    assert rewound.version_id == older.version_id
    assert rewound_source == older_source


async def test_a_file_moved_onto_another_cells_name_settles_once(tmp_path: Path):
    """Which cell left is decided by identity, not by filename: the one whose
    file was overwritten is gone, and the one that arrived keeps the name it
    landed on. Asking the filesystem for a file named after each slug instead
    would report the arriving cell deleted — it answers to a name its file does
    not carry — and re-add it on every quiesce for as long as the flow exists."""
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "score_v2", SCORE_CELL.replace("0.91", "0.77"))

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        (flow / "cells" / "score_v2.py").replace(flow / "cells" / "score.py")

        await api.status({"flow": "churn"})
        settled = len(transactions(session))
        for _ in range(3):
            await api.status({"flow": "churn"})
        here = slice_of(session, "main")
        stored = session.store.objects.get(here["score"].raw_source_ref).decode("utf-8")
        idle = len(transactions(session))

    assert sorted(here) == ["score"]
    assert "0.77" in stored
    # Reconciliation is idempotent: a settled file plane writes nothing.
    assert idle == settled


async def test_a_deleted_file_leaves_this_branch_and_dangles_its_consumers(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        session.store.branches.fork("sweep", from_branch="main")
        (flow / "cells" / "score.py").unlink()
        await api.flow_open({"flow": "churn"})
        opened = await api.flow_open({"flow": "churn"})
        removals = ops_of(session, CellRemoved)
        elsewhere = sorted(slice_of(session, "sweep"))

    assert len(removals) == 1
    assert slugs(opened) == ["report"]
    report = next(cell for cell in opened["cells"] if cell["slug"] == "report")
    assert [flag["code"] for flag in report["flags"]] == ["dangling_ref"]
    assert str(report["flags"][0]["detail"]) == (
        "unknown reference `score.summary`. no cell on this lane produces it"
    )
    # Delete is per-branch: the fork still holds both cells.
    assert elsewhere == ["report", "score"]


async def test_an_mv_is_a_rename_that_rewires_consumers_for_free(tmp_path: Path):
    """References hash as uids, so renaming costs a spelling change in the
    consumers' files and nothing else — no new behaviour, no staleness, no
    cache thrown away."""
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await api.run({"flow": "churn", "target": "report"})
        session = api.hub.session("churn")
        before = slice_of(session, "main")["report"]

        (flow / "cells" / "score.py").rename(flow / "cells" / "auc.py")
        opened = await api.flow_open({"flow": "churn"})
        after = slice_of(session, "main")["report"]
        renames = ops_of(session, Renamed)

    assert [(op.old_slug, op.new_slug) for op in renames] == [("score", "auc")]
    assert "auc.summary" in source_of(flow, "report")
    # Same cell, same behaviour: the consumer neither moved nor went stale.
    assert (after.uid, after.definition_hash) == (before.uid, before.definition_hash)
    assert slugs(opened, "synced") == ["auc", "report"]


async def test_an_mv_during_a_syntax_error_keeps_the_cell_uid(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        before = slice_of(session, "main")["score"]
        score = flow / "cells" / "score.py"
        score.write_text(
            score.read_text("utf-8") + "\n    consumes = {\n", encoding="utf-8"
        )
        score.rename(flow / "cells" / "points.py")

        broken = await api.cells_list({"flow": "churn"})
        during = slice_of(session, "main")["points"]
        renames = ops_of(session, Renamed)

        write_cell(flow, "points", SCORE_CELL)
        fixed = await api.cells_list({"flow": "churn"})
        after = slice_of(session, "main")

    report = next(cell for cell in fixed["cells"] if cell["slug"] == "report")
    assert slugs(broken) == ["points", "report"]
    assert (during.uid, after["points"].uid) == (before.uid, before.uid)
    assert [(op.old_slug, op.new_slug) for op in renames] == [("score", "points")]
    assert [flag["code"] for flag in report["flags"]] == []
    assert after["report"].manifest.consumes["summary"].uid == before.uid
    assert "points.summary" in source_of(flow, "report")


async def test_renaming_a_producer_and_its_consumer_together_still_rewires(
    tmp_path: Path,
):
    """Both files move in one burst, so the consumer is between names when its
    producer is accepted — reachable only by identity, and only once its own
    file has been read. Missing it would leave the reference spelled at a cell
    nothing on the branch answers to, which is the one thing a rename is
    supposed to cost nothing to avoid."""
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await api.run({"flow": "churn", "target": "report"})
        session = api.hub.session("churn")
        before = slice_of(session, "main")["report"]

        (flow / "cells" / "score.py").rename(flow / "cells" / "auc.py")
        (flow / "cells" / "report.py").rename(flow / "cells" / "auc_report.py")
        opened = await api.flow_open({"flow": "churn"})
        after = slice_of(session, "main")["auc_report"]

    assert "auc.summary" in source_of(flow, "auc_report")
    assert [flag.code for flag in after.flags] == []
    assert (after.uid, after.definition_hash) == (before.uid, before.definition_hash)
    assert slugs(opened, "synced") == ["auc", "auc_report"]


async def test_shared_code_marks_every_cell_and_evicts_before_the_next_run(
    tmp_path: Path,
):
    """Workspace code is not versioned by the store, so a change to it is a
    fact about behaviour: every cell marks with the file named in words, and
    the kernel forgets the module before anything else runs against it."""
    root = make_workspace(tmp_path / "project", files={"helpers.py": "AUC = 0.91"})
    write_cell(root / "churn.flow", "score", HELPER_CELL)
    evictions: list[bool] = []

    async with daemon_api(root) as api:
        await api.run({"flow": "churn", "target": "score"})
        session = api.hub.session("churn")
        evict_for_real = session.kernel.evict_workspace_modules

        def evict() -> None:
            evictions.append(True)
            evict_for_real()

        session.kernel.evict_workspace_modules = evict  # type: ignore[method-assign]
        write_file(root / "helpers.py", "AUC = 0.99")
        opened = await api.flow_open({"flow": "churn"})
        again = await api.run({"flow": "churn", "target": "score"})
        changes = [
            op for op in ops_of(session, WorkspaceCodeChanged) if op.changed_paths
        ]

    assert [op.changed_paths for op in changes] == [["helpers.py"]]
    assert slugs(opened, "unsynced") == ["score"]
    score = next(cell for cell in opened["cells"] if cell["slug"] == "score")
    assert score["causes"] == ["`helpers.py` changed"]
    assert evictions == [True]
    assert again["executed"] == ["score"]
    assert values_in(root / "churn.flow") == [{"auc": 0.91}, {"auc": 0.99}]


async def test_a_helper_edit_does_not_wait_for_a_running_cell(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project", files={"helpers.py": "AUC = 0.91"})
    flow = root / "churn.flow"
    started = tmp_path / "started"
    release = tmp_path / "release"
    write_cell(
        flow,
        "score",
        f"""
        class Score:
            produces = {{"summary": "asset"}}

            def materialize(self, ctx):
                import time
                from pathlib import Path
                import helpers

                Path({str(started)!r}).touch()
                deadline = time.monotonic() + 60
                while not Path({str(release)!r}).exists():
                    if time.monotonic() >= deadline:
                        raise TimeoutError("the test did not release the cell")
                    time.sleep(0.01)
                return {{"summary": {{"auc": helpers.AUC}}}}
        """,
    )

    async with daemon_api(root) as api:
        running = asyncio.create_task(api.run({"flow": "churn", "target": "score"}))
        try:
            deadline = asyncio.get_running_loop().time() + 30
            while not started.exists() and asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(0.01)
            assert started.exists()

            write_file(root / "helpers.py", "AUC = 0.99")
            listed = await asyncio.wait_for(
                api.cells_list({"flow": "churn"}), timeout=2
            )
            assert not running.done()
        finally:
            release.touch()
            first = await asyncio.wait_for(running, timeout=30)

        second = await api.run({"flow": "churn", "target": "score"})

    assert slugs(listed) == ["score"]
    assert first["executed"] == ["score"]
    assert second["executed"] == ["score"]
    assert values_in(flow) == [{"auc": 0.91}, {"auc": 0.99}]


async def test_a_user_verb_attributes_a_file_edit_to_the_one_registered_agent(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.agent_begin({"flow": "churn", "label": "claude-1"})
        path = root / "churn.flow" / "cells" / "score.py"
        watcher = Watcher(api.hub, debounce_s=600)
        watcher.start()
        try:
            write_cell(root / "churn.flow", "score", SCORE_CELL.replace("0.91", "0.93"))
            watcher.notice(path)
            session = api.hub.session("churn")
            await api.cells_list({"flow": "churn", "actor": "user"})
            landed = transactions(session)[-1]
            version = slice_of(session, "main")["score"]
        finally:
            await watcher.stop()

    assert (landed.actor, version.author) == ("claude-1", "claude-1")
    assert [op.flag for op in landed.ops if isinstance(op, FlagSet)] == [MIXED_EDITING]


async def test_a_user_verb_attributes_a_file_edit_to_user_with_two_agents(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.agent_begin({"flow": "churn", "label": "claude-1"})
        await api.agent_begin({"flow": "churn", "label": "codex-2"})
        write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.93"))

        await api.cells_list({"flow": "churn", "actor": "user"})
        session = api.hub.session("churn")
        landed = transactions(session)[-1]
        version = slice_of(session, "main")["score"]

    assert (landed.actor, version.author) == ("user", "user")


async def test_an_explicit_agent_caller_owns_the_reconcile_it_triggers(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.agent_begin({"flow": "churn", "label": "claude-1"})
        await api.agent_begin({"flow": "churn", "label": "codex-2"})
        write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.93"))

        await api.cells_list({"flow": "churn", "actor": "shell-agent"})
        session = api.hub.session("churn")
        landed = transactions(session)[-1]
        version = slice_of(session, "main")["score"]

    assert (landed.actor, version.author) == ("shell-agent", "shell-agent")


async def test_the_agent_bracket_bounds_which_edits_carry_its_name(tmp_path: Path):
    """`agent begin` and `agent end` are boundaries, and each settles the file
    plane before it lands: an edit made before the session opened belongs to
    whoever was there before it, and one made after it closed is the user's
    again — neither is swept into the agent's name by the debounce that would
    otherwise have grouped them together."""
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")

        write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.92"))
        await api.agent_begin({"flow": "churn", "label": "claude-1"})
        write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.93"))
        await api.agent_end({"flow": "churn", "actor": "claude-1"})
        write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.94"))
        session.reconcile(tier="live")

        authors = [op.author for op in ops_of(session, CellAccepted)]

    assert authors == ["user", "user", "claude-1", "user"]


async def test_reconciliation_leaves_files_it_was_never_asked_to_watch(
    tmp_path: Path,
):
    root = make_workspace(
        tmp_path / "project", files={"data/raw.csv": "a,b", "helpers.py": "VALUE = 1"}
    )
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_file(flow / "util.py", "def clean(frame):\n    return frame\n")

    async with daemon_api(root) as api:
        opened = await api.flow_open({"flow": "churn"})

    # A stray module inside the flow is shared code, never a cell — and the
    # projection that follows the checkout leaves it exactly where it was.
    assert slugs(opened) == ["score"]
    assert cell_files(flow) == ["score"]
    assert (flow / "util.py").exists()
    assert (root / "data" / "raw.csv").read_text().strip() == "a,b"


async def test_editor_links_and_an_undecodable_cell_do_not_break_reconciliation(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    cells = root / "churn.flow" / "cells"
    (cells / ".#score.py").symlink_to("missing.py")
    (cells / "._score.py").symlink_to("also-missing.py")
    (cells / "dangling.py").symlink_to("../../not-there.py")
    latin1_path = cells / "latin1.py"
    latin1_source = b'class Latin1:\n    """caf\xe9"""\n'
    latin1_path.write_bytes(latin1_source)

    async with daemon_api(root) as api:
        opened = await api.flow_open({"flow": "churn"})
        listed = await api.cells_list({"flow": "churn"})

    assert slugs(opened) == ["latin1"]
    assert slugs(listed) == ["latin1"]
    (latin1,) = listed["cells"]
    assert [flag["code"] for flag in latin1["flags"]] == ["invalid"]
    assert "UTF-8 encoding" in latin1["flags"][0]["detail"]
    assert (cells / ".#score.py").is_symlink()
    assert (cells / "._score.py").is_symlink()
    assert (cells / "dangling.py").is_symlink()
    assert latin1_path.read_bytes() == latin1_source


async def test_an_unreadable_cell_is_skipped_without_being_deleted(
    tmp_path: Path, monkeypatch: Any
) -> None:
    root = make_workspace(tmp_path / "project")
    score = write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        original_read_bytes = Path.read_bytes

        def read_bytes(path: Path) -> bytes:
            if path == score:
                raise PermissionError("cell is unreadable")
            return original_read_bytes(path)

        monkeypatch.setattr(Path, "read_bytes", read_bytes)
        listed = await api.cells_list({"flow": "churn"})

    assert slugs(listed) == ["score"]


async def test_inline_class_and_utf8_bom_are_accepted_once(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    cells = flow / "cells"
    (cells / "todo.py").write_text(
        'class Todo: """Write the report."""', encoding="utf-8"
    )
    (cells / "meta.py").write_bytes(
        b'\xef\xbb\xbfclass Meta:\n    """Track metadata."""\n'
    )

    async with daemon_api(root) as api:
        first = await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        settled_at = len(transactions(session))
        second = await api.cells_list({"flow": "churn"})
        settled = len(transactions(session))

    assert slugs(first) == ["meta", "todo"]
    assert all(cell["flags"] == [] for cell in second["cells"])
    compile((cells / "todo.py").read_text("utf-8"), "todo.py", "exec")
    assert "uid =" in (cells / "todo.py").read_text("utf-8")
    assert settled == settled_at


async def test_an_unreadable_workspace_file_is_skipped_and_later_edits_land(
    tmp_path: Path, monkeypatch: Any
) -> None:
    root = make_workspace(
        tmp_path / "project",
        files={
            "helpers.py": "AUC = 0.91",
            "private/notes.py": "SECRET = 1",
            ".#draft.py": "IGNORED = 1",
            "._draft.py": "IGNORED = 2",
        },
    )
    write_cell(root / "churn.flow", "score", HELPER_CELL)
    private = root / "private" / "notes.py"
    original_hash_file = workspace_tree.hash_file

    def hash_file(path: Path) -> str:
        if path == private:
            raise PermissionError("workspace file is unreadable")
        return original_hash_file(path)

    monkeypatch.setattr(workspace_tree, "hash_file", hash_file)

    async with daemon_api(root) as api:
        await api.run({"flow": "churn", "target": "score"})
        session = api.hub.session("churn")
        write_file(root / "helpers.py", "AUC = 0.99")
        listed = await api.cells_list({"flow": "churn"})
        changes = ops_of(session, WorkspaceCodeChanged)

    ignored = {"private/notes.py", ".#draft.py", "._draft.py"}
    assert all(ignored.isdisjoint(change.files) for change in changes)
    assert changes[-1].changed_paths == ["helpers.py"]
    score = next(cell for cell in listed["cells"] if cell["slug"] == "score")
    assert score["causes"] == ["`helpers.py` changed"]


async def test_a_settled_file_plane_is_read_but_not_reparsed_on_every_verb(
    tmp_path: Path, monkeypatch: Any
):
    """Every verb reconciles first, and a workbench opening asks twenty of them.

    Parsing is the expensive half of acceptance — an AST per cell, deep-copied
    and unparsed to build the bound source — so a directory nobody touched
    between two verbs is read from disk and left alone. What must not change is
    the guarantee: the files are still stat'd every time, and an edit made
    between two verbs is picked up by the second whether or not any watcher
    event arrived.
    """
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)

    parsed: list[str] = []
    original = Acceptance.accept_path

    def counted(self: Acceptance, path: Path, **kwargs: Any) -> Any:
        parsed.append(path.stem)
        return original(self, path, **kwargs)

    monkeypatch.setattr(Acceptance, "accept_path", counted)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        parsed.clear()

        for _ in range(5):
            await api.cells_show({"flow": "churn", "slug": "score"})
        idle = list(parsed)

        # The same window, with an edit landing in it and no watcher running.
        # Same length as what it replaces, deliberately: a stamp over the
        # clock and the size would be a bet on the filesystem's timestamp
        # resolution, which is a platform's to decide and not this file's.
        parsed.clear()
        write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.93"))
        shown = await api.cells_show({"flow": "churn", "slug": "score"})

    assert idle == [], f"a settled directory was re-parsed: {idle}"
    assert "score" in parsed
    assert "0.93" in shown["source"]
