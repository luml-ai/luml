"""Checkout, the worktree lock, and edits the daemon was handed rather than read.

The through-line: the store is written either way. What the lock decides is
only whether the files may be rewritten yet — so an edit is never lost, a
working agent never has files pulled out from under it, and every state in
between says which it is.
"""

from pathlib import Path

import pytest
from lumlflow.flow.errors import EditConflict, WorktreeLocked
from lumlflow.flow.store.models import WorktreeBound

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

    assert opened["branch"] == "main"
    assert opened["checked_out"] is True
    assert bound is not None and bound.name == "main"
    assert [op.path for op in binds] == [str(root / "churn.flow")]
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


async def test_an_agent_session_holds_the_files_against_a_checkout(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        api.hub.session("churn").store.branches.fork("sweep", from_branch="main")
        await api.agent_begin({"flow": "churn", "label": "claude-1"})

        with pytest.raises(WorktreeLocked) as locked:
            await api.switch({"flow": "churn", "branch": "sweep"})
        forced = await api.switch({"flow": "churn", "branch": "sweep", "force": True})

    assert locked.value.holder == "claude-1"
    assert "claude-1" in str(locked.value)
    assert forced["branch"] == "sweep"


async def test_an_edit_under_an_agent_session_is_saved_before_it_is_written(
    tmp_path: Path,
):
    """The store takes the edit immediately — correct attribution at the source
    — and the files wait for the agent to finish. Nothing is lost either way;
    the card just says which state it is in."""
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.agent_begin({"flow": "churn", "label": "claude-1"})
        saved = await api.cells_edit(
            {"flow": "churn", "slug": "score", "source": SWEEP_CELL}
        )
        session = api.hub.session("churn")
        while_held = (source_of(flow, "score"), session.worktree.pending())
        stored = slice_of(session, "main")["score"]

        ended = await api.agent_end({"flow": "churn", "actor": "claude-1"})
        settled = session.worktree.pending()

    assert saved["written_to_files"] is False
    assert "0.91" in while_held[0] and while_held[1] == ["score"]
    assert stored.author == "user"
    # The session ends, the projection it held back completes.
    assert ended["projected"]["written"] == ["score"]
    assert "0.77" in source_of(flow, "score")
    assert settled == []


async def test_an_agent_editing_the_stale_file_diverges_instead_of_advancing(
    tmp_path: Path,
):
    """The agent's version records the parent it actually derived from — the
    one the files held — and says so, so the head never moves on quietly over
    an edit the author never saw."""
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        original = slice_of(session, "main")["score"].version_id
        await api.agent_begin({"flow": "churn", "label": "claude-1"})
        await api.cells_edit({"flow": "churn", "slug": "score", "source": SWEEP_CELL})

        write_cell(flow, "score", source_of(flow, "score").replace("0.91", "0.95"))
        session.reconcile(tier="live")
        head = slice_of(session, "main")["score"]

    assert head.parent_version_id == original
    assert [flag.code for flag in head.flags] == ["divergent"]
    assert "save it to a new lane" in str(head.flags[0].detail)
    assert head.author == "claude-1"


async def test_a_restart_reads_a_pending_projection_off_the_files(tmp_path: Path):
    """Nothing in memory survives, so the file has to say what it is: bytes a
    known version of that cell was accepted under are a projection that never
    landed, not an edit to accept over the version that outran it."""
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.agent_begin({"flow": "churn", "label": "claude-1"})
        await api.cells_edit({"flow": "churn", "slug": "score", "source": SWEEP_CELL})
        saved = slice_of(api.hub.session("churn"), "main")["score"].version_id

    async with daemon_api(root) as api:
        session = api.hub.open(api.hub.select("churn"))
        await api.hub.quiesce(session)
        after_restart = slice_of(session, "main")["score"].version_id
        still_owed = session.worktree.pending()

        ended = await api.agent_end({"flow": "churn", "actor": "claude-1"})

    # The stale file was neither accepted nor overwritten while the session
    # held it — and the deferral was recognised from the files alone.
    assert (after_restart, still_owed) == (saved, ["score"])
    assert ended["projected"]["written"] == ["score"]
    assert "0.77" in source_of(flow, "score")


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

        with pytest.raises(EditConflict) as conflict:
            await api.cells_edit(
                {"flow": "churn", "slug": "score", "source": SWEEP_CELL, "base": base}
            )
        unwritten = slice_of(session, "main")["score"].version_id

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
    assert "save this edit to a new lane" in str(conflict.value)
    # Nothing was written until a side was picked.
    assert unwritten == moved_on.version_id
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


async def test_a_session_ending_under_another_ends_and_leaves_the_files(
    tmp_path: Path,
):
    """Two agents, one worktree: the second still holds the files when the
    first finishes, so the edit stays owed. The session ended either way —
    refusing to say so over files it no longer holds would report a failure for
    something that already happened."""
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
        holder = session.worktree.holder()
        still_owed = session.worktree.pending()

    assert saved["written_to_files"] is False
    assert (ended["actor"], ended["projected"]) == ("claude-1", None)
    assert holder is not None and holder.label == "codex-1"
    assert still_owed == ["score"] and "0.91" in source_of(flow, "score")


async def test_an_api_only_session_never_materializes_a_worktree(tmp_path: Path):
    """The MCP path: cells live in the store, attribution rides on the ops, and
    no checkout, lock or file plane is invented for a session that never asked
    for one."""
    root = make_workspace(tmp_path / "project", flows=())

    async with daemon_api(root) as api:
        await api.flow_init({"name": "churn"})
        await api.agent_begin(
            {"flow": "churn", "actor": "mcp-1", "label": "claude", "worktree": False}
        )
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
        worktree = (session.worktree.bound(), session.worktree.holder())

    assert outcome["executed"] == ["score"]
    assert opened["checked_out"] is False
    assert worktree == (None, None)
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
    assert rewound["to_step"] == at
    assert rewound["projected"]["written"] == ["score"]
    assert "0.91" in source_of(flow, "score")
