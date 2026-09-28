"""Checkout, file projection, and edits the daemon was handed rather than read."""

from pathlib import Path

import pytest
from lumlflow.flow.errors import EditConflict, FlowError
from lumlflow.flow.store.models import CellAccepted, CellRemoved, Renamed, WorktreeBound

from tests.daemon.helpers import (
    BROKEN_CELL,
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
    write_cell,
)

SWEEP_CELL = SCORE_CELL.replace("0.91", "0.77")


async def test_opening_a_flow_checks_it_out_rather_than_binding_it_bare(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        opened = await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        bound = session.worktree.bound()
        binds = ops_of(session, WorktreeBound)
        flow_id = session.store.manifest.flow_id

    assert opened["branch"] == "main"
    assert opened["checked_out"] is True
    assert "unwritten" not in opened
    assert bound is not None and bound.name == "main"
    assert [op.flow_id for op in binds] == [flow_id]
    # The cells were already the branch's slice, so the projection wrote nothing.
    assert slugs(opened) == ["score"]


async def test_switching_projects_the_target_branch_into_the_files(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        api.hub.session("churn").store.branches.fork("sweep", from_branch="main")
        await api.cells_edit(
            {"flow": "churn", "branch": "sweep", "slug": "score", "source": SWEEP_CELL}
        )
        await api.cells_new(
            {
                "flow": "churn",
                "branch": "sweep",
                "slug": "report",
                "source": REPORT_CELL,
            }
        )
        # Editing a branch nobody checked out never touches the files.
        untouched = source_of(flow, "score")

        onto_sweep = await api.switch({"flow": "churn", "branch": "sweep"})
        on_sweep = (source_of(flow, "score"), cell_files(flow))
        back = await api.switch({"flow": "churn", "branch": "main"})

    assert "0.91" in untouched
    assert onto_sweep["branch"] == "sweep"
    assert "0.77" in on_sweep[0] and on_sweep[1] == ["report", "score"]
    # Switching back removes what only the fork had, and restores what it edited.
    assert back["projected"]["removed"] == ["report"]
    assert cell_files(flow) == ["score"] and "0.91" in source_of(flow, "score")


async def test_reopening_lands_on_the_branch_the_worktree_is_bound_to(tmp_path: Path):
    """Where a workbench reopens is store state, not a client's memory of it.

    A daemon restart after an overnight session must land on the branch the
    files are, or the first thing anyone sees is somebody else's slice — and
    the checkout on open would rewrite the worktree back to `main`.
    """
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        api.hub.session("churn").store.branches.fork("sweep", from_branch="main")
        await api.cells_edit(
            {"flow": "churn", "branch": "sweep", "slug": "score", "source": SWEEP_CELL}
        )
        await api.switch({"flow": "churn", "branch": "sweep"})

    async with daemon_api(root) as api:
        reopened = await api.flow_open({"flow": "churn"})
        bound = api.hub.session("churn").worktree.bound()

    assert reopened["branch"] == "sweep"
    assert bound is not None and bound.name == "sweep"
    assert "0.77" in source_of(flow, "score")


async def test_moving_the_workspace_keeps_the_checked_out_lane(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        session.store.branches.fork("sweep", from_branch="main")
        await api.cells_edit(
            {"flow": "churn", "branch": "sweep", "slug": "score", "source": SWEEP_CELL}
        )
        await api.switch({"flow": "churn", "branch": "sweep"})
        main_version = slice_of(session, "main")["score"].version_id
        before_move_step = session.store.next_step - 1

    moved_root = root.rename(tmp_path / "moved-project")
    moved_flow = moved_root / "churn.flow"

    async with daemon_api(moved_root) as api:
        reopened = await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        bound = session.worktree.bound()
        moved_transactions = [
            entry for entry in transactions(session) if entry.step > before_move_step
        ]
        main_version_after = slice_of(session, "main")["score"].version_id

    assert reopened["branch"] == "sweep"
    assert bound is not None and bound.name == "sweep"
    assert main_version_after == main_version
    assert "0.77" in source_of(moved_flow, "score")
    assert not any(
        entry.intent.startswith("offline edits:") for entry in moved_transactions
    )


async def test_rewinding_shows_that_runs_logs_not_the_latest(tmp_path: Path):
    """Every materialization keeps its own log artifact, and the baseline the
    rewind restores is what a surface reads — so the traceback on the card is
    the one that run produced, not the newest one on the branch."""
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", BROKEN_CELL)

    async with daemon_api(root) as api:
        await api.run({"flow": "churn", "target": "score"})
        at = api.hub.session("churn").store.next_step - 1
        write_cell(
            flow,
            "score",
            BROKEN_CELL.replace("the model did not converge", "the data did not load"),
        )
        await api.run({"flow": "churn", "target": "score"})
        latest = await api.cells_show({"flow": "churn", "slug": "score"})

        await api.rewind({"flow": "churn", "to_step": at})
        rewound = await api.cells_show({"flow": "churn", "slug": "score"})

    assert "the data did not load" in latest["error"]
    assert "the model did not converge" in rewound["error"]
    assert "the data did not load" not in rewound["error"]


async def test_workspace_files_are_branch_invariant(tmp_path: Path):
    """The store never versions them, so no branch verb may move them. A switch
    that rewrote `data/raw.csv` would make the shared substrate a function of
    which branch you happened to be on."""
    root = make_workspace(
        tmp_path / "project",
        files={"data/raw.csv": "n\n1\n", "helpers.py": "VALUE = 1"},
    )
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    shared = {path: (root / path).read_text("utf-8") for path in ("data/raw.csv",)}
    shared["helpers.py"] = (root / "helpers.py").read_text("utf-8")

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        at = session.store.next_step - 1
        await api.fork({"flow": "churn", "name": "sweep"})
        await api.cells_edit(
            {"flow": "churn", "branch": "sweep", "slug": "score", "source": SWEEP_CELL}
        )
        await api.switch({"flow": "churn", "branch": "sweep"})
        await api.switch({"flow": "churn", "branch": "main"})
        await api.rewind({"flow": "churn", "to_step": at})
        after = {path: (root / path).read_text("utf-8") for path in shared}

    assert after == shared
    # The cells did move — otherwise this would pass on a daemon that projects
    # nothing at all.
    assert "0.91" in source_of(flow, "score")


async def test_an_agent_session_does_not_block_a_checkout(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        api.hub.session("churn").store.branches.fork("sweep", from_branch="main")
        await api.cells_edit(
            {"flow": "churn", "branch": "sweep", "slug": "score", "source": SWEEP_CELL}
        )
        await api.agent_begin({"flow": "churn", "label": "claude-1"})

        switched = await api.switch({"flow": "churn", "branch": "sweep"})

    assert switched["branch"] == "sweep"
    assert "0.77" in source_of(flow, "score")


async def test_lock_only_force_params_are_ignored_under_an_agent(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.agent_begin({"flow": "churn", "label": "claude-1"})
        forked = await api.fork({"flow": "churn", "name": "sweep"})
        exported = await api.export({"flow": "churn", "branch": "sweep"})

        switched = await api.switch(
            {"flow": "churn", "branch": "sweep", "force": False}
        )
        renamed = await api.rename(
            {
                "flow": "churn",
                "slug": "score",
                "to": "headline",
                "force": False,
            }
        )
        deleted = await api.cells_delete(
            {"flow": "churn", "slug": "headline", "force": False}
        )
        imported = await api.import_cells(
            {"flow": "churn", "source": exported["source"], "force": False}
        )
        rewound = await api.rewind(
            {
                "flow": "churn",
                "to_step": forked["forked_at_step"],
                "force": False,
            }
        )
        checked_out = await api.flow_checkout(
            {"flow": "churn", "branch": "main", "force": False}
        )

    assert switched["branch"] == "sweep"
    assert renamed["slug"] == "headline"
    assert deleted["slug"] == "headline"
    assert [cell["slug"] for cell in imported["cells"]] == ["score"]
    assert rewound["branch"] == "sweep"
    assert checked_out["branch"] == "main"
    assert "0.91" in source_of(flow, "score")


async def test_cells_created_under_an_agent_are_written_and_not_reconciled_away(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.agent_begin({"flow": "churn", "label": "claude-1"})
        original = await api.cells_show({"flow": "churn", "slug": "score"})
        added = await api.cells_new({"flow": "churn"})
        added_immediately = (flow / "cells" / f"{added['slug']}.py").exists()
        duplicated = await api.cells_new(
            {
                "flow": "churn",
                "slug": "score_copy",
                "source": original["source"],
                "intent": "duplicated score",
            }
        )
        session = api.hub.session("churn")
        listed = await api.cells_list({"flow": "churn", "actor": "user"})
        landed = transactions(session)

    assert added["written_to_files"] is True
    assert added_immediately is True
    assert duplicated["written_to_files"] is True
    assert {cell["slug"] for cell in listed["cells"]} == {
        "score",
        "score_copy",
        added["slug"],
    }
    assert cell_files(flow) == ["score", "score_copy", added["slug"]]
    assert not any(isinstance(op, CellRemoved) for entry in landed for op in entry.ops)
    created = [
        entry
        for entry in landed
        if any(
            isinstance(op, CellAccepted) and op.slug in {"score_copy", added["slug"]}
            for op in entry.ops
        )
    ]
    assert [entry.actor for entry in created] == ["user", "user"]
    assert [
        entry.actor
        for entry in created
        if any(
            isinstance(op, CellAccepted) and op.slug == added["slug"]
            for op in entry.ops
        )
    ] == ["user"]


async def test_an_agent_mv_after_a_ui_edit_keeps_the_users_head(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        await api.agent_begin({"flow": "churn", "label": "claude-1"})
        await api.cells_edit({"flow": "churn", "slug": "score", "source": SWEEP_CELL})
        user_head = slice_of(session, "main")["score"]
        report_before = slice_of(session, "main")["report"]
        producer_versions_before = [
            op for op in ops_of(session, CellAccepted) if op.uid == user_head.uid
        ]
        (flow / "cells" / "score.py").rename(flow / "cells" / "total.py")

        await api.cells_list({"flow": "churn", "actor": "user"})
        head = slice_of(session, "main")["total"]
        report = slice_of(session, "main")["report"]
        renames = ops_of(session, Renamed)
        producer_versions = [
            op for op in ops_of(session, CellAccepted) if op.uid == head.uid
        ]
        rename_transaction = next(
            entry
            for entry in transactions(session)
            if any(
                isinstance(op, Renamed) and op.new_slug == "total" for op in entry.ops
            )
        )

    assert source_of(flow, "total") == session.store.objects.get(
        user_head.raw_source_ref
    ).decode("utf-8")
    assert [(op.old_slug, op.new_slug) for op in renames] == [("score", "total")]
    assert producer_versions == producer_versions_before
    assert rename_transaction.actor == "claude-1"
    assert head.version_id == user_head.version_id
    assert head.author == "user"
    assert not head.flags
    assert "total.summary" in source_of(flow, "report")
    assert (report.uid, report.definition_hash) == (
        report_before.uid,
        report_before.definition_hash,
    )
    assert report.manifest.consumes["summary"].uid == head.uid


async def test_a_stale_editor_is_refused_into_the_conflict_menu(tmp_path: Path):
    """Optimistic locking per cell: the edit carries the hash it started from,
    and a head that moved past it is never overwritten by accident."""
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        opened = await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        base = slice_of(session, "main")["score"].definition_hash

        await api.agent_begin({"flow": "churn", "label": "claude-1"})
        write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.95"))
        session.reconcile(tier="live")
        moved_on = slice_of(session, "main")["score"]
        transactions_before_refusal = len(transactions(session))

        with pytest.raises(EditConflict) as conflict:
            await api.cells_edit(
                {"flow": "churn", "slug": "score", "source": SWEEP_CELL, "base": base}
            )
        unchanged_head = slice_of(session, "main")["score"].version_id
        transactions_after_refusal = len(transactions(session))

        overwritten = await api.cells_edit(
            {
                "flow": "churn",
                "slug": "score",
                "source": SWEEP_CELL,
                "base": base,
                "force": True,
            }
        )

    assert opened["cells"][0]["slug"] == "score"
    assert (conflict.value.base, conflict.value.head) == (
        base,
        moved_on.definition_hash,
    )
    assert conflict.value.head_author == "claude-1"
    assert "`score`" in str(conflict.value)
    assert "save this edit to a new lane" in str(conflict.value)
    # Nothing was written until a side was picked.
    assert transactions_after_refusal == transactions_before_refusal
    assert unchanged_head == moved_on.version_id
    assert overwritten["definition_hash"] != moved_on.definition_hash


async def test_adding_a_cell_never_blocks_on_a_name(tmp_path: Path):
    """The uid is minted now and the name is owed: an unnamed cell scaffolds
    under a placeholder, flagged softly, and the flag carries the name to
    rename it to as soon as the class has one."""
    root = make_workspace(tmp_path / "project", flows=())

    async with daemon_api(root) as api:
        await api.flow_init({"name": "churn"})
        await api.flow_checkout({"flow": "churn"})
        created = await api.cells_new({"flow": "churn"})
        second = await api.cells_new({"flow": "churn"})
        named = await api.cells_edit(
            {
                "flow": "churn",
                "slug": created["slug"],
                "source": "class TrainXGB:\n"
                '    """Trains it."""\n\n'
                '    produces = {"model": "asset"}\n\n'
                "    def materialize(self, ctx):\n"
                "        return {'model': 1}\n",
            }
        )

    assert (created["slug"], second["slug"]) == ("untitled_1", "untitled_2")
    assert [flag["code"] for flag in created["flags"]] == ["placeholder_slug"]
    assert created["flags"][0]["detail"] == (
        "`untitled_1` is a placeholder name. give the cell a name"
    )
    assert named["flags"][0]["detail"] == (
        "`untitled_1` is a placeholder name. rename it to `train_xgb`"
    )
    # Checked out, so the scaffold reached the files too.
    assert created["written_to_files"] is True
    assert cell_files(root / "churn.flow") == ["untitled_1", "untitled_2"]


async def test_adding_a_cell_never_lands_on_the_one_already_named_that(
    tmp_path: Path,
):
    """No directory is there to refuse the name on this path, so the store does
    what a directory would: the cell being added is its own cell under a name
    of its own, flagged, and the one that was already there keeps its body, its
    author and its identity. Adding is never an edit to somebody else's cell."""
    root = make_workspace(tmp_path / "project", flows=())

    async with daemon_api(root) as api:
        await api.flow_init({"name": "churn"})
        await api.flow_checkout({"flow": "churn"})
        first = await api.cells_new(
            {"flow": "churn", "slug": "score", "source": SCORE_CELL}
        )
        second = await api.cells_new(
            {
                "flow": "churn",
                "slug": "score",
                "source": SWEEP_CELL,
                "actor": "claude-1",
            }
        )
        session = api.hub.session("churn")
        here = slice_of(session, "main")
        bodies = {
            slug: session.store.objects.get(version.raw_source_ref).decode("utf-8")
            for slug, version in here.items()
        }

    assert (first["slug"], second["slug"]) == ("score", "score_2")
    assert [flag["code"] for flag in second["flags"]] == ["hygiene"]
    assert second["flags"][0]["detail"] == (
        "another cell is named `score`. this one is `score_2`"
    )
    assert "0.91" in bodies["score"] and "0.77" in bodies["score_2"]
    assert here["score"].author == "user"
    assert cell_files(root / "churn.flow") == ["score", "score_2"]


async def test_path_shaped_cell_names_leave_the_lane_and_files_unchanged(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        before = slice_of(session, "main")
        journal_before = transactions(session)

        with pytest.raises(FlowError, match="path separators"):
            await api.cells_new(
                {"flow": "churn", "slug": "../../escaped", "source": SCORE_CELL}
            )
        with pytest.raises(FlowError, match="path separators"):
            await api.rename({"flow": "churn", "slug": "score", "to": "../out"})
        with pytest.raises(FlowError, match="non-empty"):
            await api.rename({"flow": "churn", "slug": "score", "to": ""})

        after = slice_of(session, "main")
        journal_after = transactions(session)

    assert after == before
    assert journal_after == journal_before
    assert cell_files(flow) == ["score"]
    assert not (root / "escaped.py").exists()
    assert not (flow / "out.py").exists()


async def test_projection_ignores_a_dangling_cell_symlink_outside_cells(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    score = write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        score.unlink()
        score.symlink_to("../../missing.py")

        checked_out = await api.flow_checkout({"flow": "churn", "branch": "main"})
        here = slice_of(api.hub.session("churn"), "main")

    assert checked_out["projected"] == {"written": [], "removed": []}
    assert list(here) == ["score"]
    assert score.is_symlink()


async def test_rename_refuses_a_name_another_cell_holds(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        before = slice_of(session, "main")

        with pytest.raises(FlowError, match=r"`report`.*already"):
            await api.rename({"flow": "churn", "slug": "score", "to": "REPORT"})

        after = slice_of(session, "main")

    assert after == before
    assert cell_files(flow) == ["report", "score"]
    assert not (flow / "cells" / "report_2.py").exists()


async def test_ending_one_session_leaves_the_other_registered(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.agent_begin({"flow": "churn", "label": "claude-1"})
        await api.agent_begin({"flow": "churn", "label": "codex-1"})
        saved = await api.cells_edit(
            {"flow": "churn", "slug": "score", "source": SWEEP_CELL}
        )
        ended = await api.agent_end({"flow": "churn", "actor": "claude-1"})
        session = api.hub.session("churn")
        registered = session.store.index.agent_sessions()

    assert saved["written_to_files"] is True
    assert ended["actor"] == "claude-1"
    assert [agent.label for agent in registered] == ["codex-1"]
    assert "0.77" in source_of(flow, "score")


async def test_an_api_only_session_never_materializes_a_worktree(tmp_path: Path):
    """The MCP path: cells live in the store, attribution rides on the ops, and
    no checkout, lock or file plane is invented for a session that never asked
    for one."""
    root = make_workspace(tmp_path / "project", flows=())

    async with daemon_api(root) as api:
        await api.flow_init({"name": "churn"})
        await api.agent_begin({"flow": "churn", "actor": "mcp-1", "label": "claude"})
        await api.cells_new(
            {
                "flow": "churn",
                "slug": "score",
                "source": SCORE_CELL,
                "actor": "mcp-1",
            }
        )
        await api.cells_edit(
            {
                "flow": "churn",
                "slug": "score",
                "source": SWEEP_CELL,
                "actor": "mcp-1",
            }
        )
        outcome = await api.run({"flow": "churn", "target": "score", "actor": "mcp-1"})
        opened = await api.flow_open({"flow": "churn", "worktree": False})

        session = api.hub.session("churn")
        authors = {version.author for version in slice_of(session, "main").values()}
        bound = session.worktree.bound()

    assert outcome["executed"] == ["score"]
    assert opened["checked_out"] is False
    assert bound is None
    assert cell_files(root / "churn.flow") == []
    assert authors == {"mcp-1"}


async def test_rewinding_the_checked_out_branch_carries_the_files_back(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        at = session.store.next_step - 1
        await api.cells_edit({"flow": "churn", "slug": "score", "source": SWEEP_CELL})
        edited = source_of(flow, "score")

        rewound = await api.rewind({"flow": "churn", "to_step": at})

    assert "0.77" in edited
    assert rewound["branch"] == "main"
    assert rewound["rewound_branch"] == "main"
    assert rewound["path"] == str(flow)
    assert rewound["checked_out"] is True
    assert rewound["to_step"] == at
    assert rewound["projected"]["written"] == ["score"]
    assert "0.91" in source_of(flow, "score")


async def test_rewinding_an_off_disk_branch_keeps_the_brief_on_disk(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        forked = await api.fork({"flow": "churn", "name": "sweep"})
        await api.cells_edit(
            {
                "flow": "churn",
                "branch": "sweep",
                "slug": "score",
                "source": SWEEP_CELL,
            }
        )

        rewound = await api.rewind(
            {
                "flow": "churn",
                "branch": "sweep",
                "to_step": forked["forked_at_step"],
            }
        )

    assert rewound["branch"] == "main"
    assert rewound["rewound_branch"] == "sweep"
    assert rewound["projected"] is None
    assert "0.91" in source_of(flow, "score")
