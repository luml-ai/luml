"""The read side: the brief, the fork tree, the comparison, the preview.

These are the shapes every surface renders, so what is asserted here is the
vocabulary as much as the values — causes in words, branches by name, and no
identifier a reader has no use for.
"""

from pathlib import Path
from typing import Any

import pytest
from lumlflow.flow.errors import FlowError

from tests.daemon.helpers import (
    BROKEN_CELL,
    EXTERNAL_CELL,
    REPORT_CELL,
    SCORE_CELL,
    TRAIN_CELL,
    daemon_api,
    make_workspace,
    write_cell,
    write_file,
)


async def test_the_brief_names_what_is_unsynced_why_and_what_it_will_cost(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project", files={"helpers.py": "VALUE = 1"})
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await api.run({"flow": "churn", "target": "report"})
        write_file(root / "helpers.py", "VALUE = 2")
        brief = await api.context({"flow": "churn"})

    assert brief["branch"] == "main"
    assert brief["cells"] == 2
    assert [entry["slug"] for entry in brief["unsynced"]] == ["report", "score"]
    assert "helpers.py" in brief["unsynced"][0]["causes"][0]
    assert brief["pending"]["recompute"] == ["report", "score"]
    assert brief["failures"] == []
    assert brief["recent"][0]["intent"]
    assert brief["agent"] is None


async def test_the_brief_omits_a_focus_nobody_reported_and_carries_a_reported_one(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        unreported = await api.context({"flow": "churn"})
        await api.fork({"flow": "churn", "name": "sweep"})
        reported = await api.set_focus(
            {"flow": "churn", "asset": "report", "compare": ["main", "sweep"]}
        )
        brief = await api.context({"flow": "churn"})

    assert "focus" not in unreported
    assert reported["asset"] == "report"
    assert brief["focus"] == {
        "branch": None,
        "asset": "report",
        "compare": ["main", "sweep"],
    }


async def test_the_brief_carries_the_failure_an_agent_has_to_read(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", BROKEN_CELL)

    async with daemon_api(root) as api:
        await api.run({"flow": "churn", "target": "score"})
        brief = await api.context({"flow": "churn"})

    assert [failure["slug"] for failure in brief["failures"]] == ["score"]
    assert "the model did not converge" in brief["failures"][0]["error"]
    assert brief["checkpoint"] is None


async def test_marking_a_point_gives_the_brief_a_checkpoint_it_could_not_compute(
    tmp_path: Path,
):
    """The badge answers "is it whole"; the marker answers "is this the one".

    A branch with a failed cell can never settle, so it has no computed
    checkpoint at all — which is exactly the state somebody wants to mark a
    known-good point in.
    """
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", BROKEN_CELL)

    async with daemon_api(root) as api:
        await api.run({"flow": "churn", "target": "score"})
        assert (await api.context({"flow": "churn"}))["checkpoint"] is None

        marked = await api.checkpoint(
            {"flow": "churn", "intent": "before I rewrite the scorer"}
        )
        brief = await api.context({"flow": "churn"})

    assert marked["branch"] == "main"
    assert brief["checkpoint"]["step"] == marked["step"]
    assert brief["checkpoint"]["intent"] == "before I rewrite the scorer"
    # The marker is a journal line like any other, so it leads the history.
    assert brief["recent"][0]["intent"] == "before I rewrite the scorer"


async def test_a_checkpoint_marks_the_branch_it_was_asked_for(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.fork({"flow": "churn", "name": "sweep"})
        marked = await api.checkpoint(
            {"flow": "churn", "branch": "sweep", "intent": "swept"}
        )
        tree = await api.tree({"flow": "churn"})

    assert _branch(tree, "sweep")["checkpoint"] == marked["step"]
    assert _branch(tree, "main")["checkpoint"] != marked["step"]


async def test_a_checkpoint_with_nothing_to_say_is_refused(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        with pytest.raises(FlowError):
            await api.checkpoint({"flow": "churn", "intent": "  "})
        history = (await api.context({"flow": "churn"}))["recent"]

    assert all(entry["intent"].strip() for entry in history)


async def test_the_fork_tree_says_where_each_branch_split_and_how_it_stands(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"flow": "churn", "target": "score"})
        await api.fork({"flow": "churn", "name": "sweep", "intent": "try it higher"})
        await api.agent_begin({"flow": "churn", "label": "claude-1"})
        tree = await api.tree({"flow": "churn"})

    main = _branch(tree, "main")
    sweep = _branch(tree, "sweep")
    assert main["parent"] is None and main["checked_out"]
    assert main["agent"] == "claude-1"
    assert sweep["parent"] == "main" and sweep["forked_at_step"] > 0
    # A fork inherits the verdicts, so it does not read as never-run.
    assert sweep["states"] == {"synced": 1}
    assert sweep["agent"] is None
    assert sweep["last_intent"]["intent"] == "try it higher"


async def test_the_fork_tree_carries_the_key_the_journal_scopes_by(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.fork({"flow": "churn", "name": "sweep", "intent": "try it higher"})
        tree = await api.tree({"flow": "churn"})
        history = await api.journal_since({"flow": "churn", "cursor": 0})

    forked = _branch(tree, "sweep")["branch_id"]
    assert forked and forked != _branch(tree, "main")["branch_id"]
    # Which is the point of serving it: a client reading the stream has the
    # branch as an id and its surfaces speak names.
    scoped = [line for line in history["transactions"] if line["branch"] == forked]
    assert [line["intent"] for line in scoped] == ["try it higher"]


async def test_a_cell_summary_names_its_kinds_its_mint_step_and_what_it_reads(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project", files={"raw.csv": "n\n1\n"})
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "train", TRAIN_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        # Written after the others, so its mint step is genuinely later — and
        # its name would sort it first.
        write_cell(flow, "load", EXTERNAL_CELL)
        await api.run({"flow": "churn", "target": "load"})
        listed = await api.cells_list({"flow": "churn"})

    cells = {entry["slug"]: entry for entry in listed["cells"]}
    # The declared word wins for what leaves the flow; an `asset` is whatever
    # its value turned out to be, and nothing has run to say yet for `score`.
    assert cells["train"]["kinds"] == {"model": "model", "run": "experiment"}
    assert cells["load"]["kinds"] == {"rows": "frame"}
    assert cells["score"]["kinds"] == {"summary": "asset"}
    # Mint order, not the alphabet: `score` was written first and stays first.
    assert cells["score"]["created_step"] < cells["load"]["created_step"]
    # It read a workspace file, which the store does not version.
    assert (cells["load"]["external"], cells["score"]["external"]) == (True, False)


async def test_comparison_lists_a_cell_only_one_branch_carries(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.fork({"flow": "churn", "name": "sweep"})
        await api.cells_new({"flow": "churn", "slug": "later", "branch": "sweep"})
        compared = await api.diff({"flow": "churn", "branches": ["main", "sweep"]})

    assert compared["definition"] == []
    assert [entry["slug"] for entry in compared["shapeless"]] == ["later"]
    assert compared["shapeless"][0]["branches"] == {"main": None, "sweep": "later"}


async def test_comparison_warns_when_a_pin_drifted_and_not_when_it_was_chosen(
    tmp_path: Path,
):
    """Pin-at-fork keeps a sweep comparable; the trunk moving on is what breaks
    it. A branch holding what it forked with beside a parent that has edited the
    cell since is comparing two results computed under different code — while a
    branch that edited the cell itself is showing exactly the difference it
    chose, which is the whole point of the fork."""
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"flow": "churn", "target": "report"})
        await api.fork({"flow": "churn", "name": "sweep"})
        await api.fork({"flow": "churn", "name": "chosen"})
        await api.cells_edit(
            {
                "flow": "churn",
                "branch": "chosen",
                "slug": "score",
                "source": SCORE_CELL.replace("0.91", "0.95"),
                "intent": "try a higher score",
            }
        )
        await api.cells_edit(
            {
                "flow": "churn",
                "branch": "main",
                "slug": "score",
                "source": SCORE_CELL.replace("0.91", "0.88"),
                "intent": "correct the score",
            }
        )
        drifted = await api.diff({"flow": "churn", "branches": ["main", "sweep"]})
        deliberate = await api.diff({"flow": "churn", "branches": ["main", "chosen"]})
        siblings = await api.diff({"flow": "churn", "branches": ["sweep", "chosen"]})

    warning = drifted["integrity"][0]
    assert warning["kind"] == "divergent-pin"
    assert (warning["slug"], warning["branches"]) == ("score", ["sweep"])
    assert "`score` is pinned where these lanes split" in warning["message"]
    # A version the branch wrote itself is the difference it forked to make.
    assert deliberate["integrity"] == []
    # Neither sibling is the other's parent, so neither drifted against it.
    assert siblings["integrity"] == []
    # The edited cell is the subject of the comparison, so its sides carry what
    # each branch produced as well as what each branch says.
    edited = next(entry for entry in drifted["definition"] if entry["slug"] == "score")
    assert [side["state"] for side in edited["versions"]] == ["unsynced", "synced"]
    assert all("params" in side for side in edited["versions"])


async def test_an_output_nobody_has_run_previews_as_nothing_stored(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        before = await api.asset_preview({"flow": "churn", "target": "score"})
        await api.run({"flow": "churn", "target": "score"})
        after = await api.asset_preview({"flow": "churn", "target": "score.summary"})

    assert (before["state"], before["preview"]) == ("unmaterialized", None)
    assert after["output"] == "summary"
    assert after["kind"] == "metric"
    assert after["preview"]["schema"] == 1
    assert after["preview"]["blocks"][0]["entries"] == {"auc": 0.91}


async def test_a_note_cell_carries_its_prose_dedented_and_whole(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(
        flow,
        "summary",
        '''
class Summary:
    """The sweep so far.

    `lr=3e-4` won by a nose.
    """
''',
    )

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        note = await api.cells_show({"flow": "churn", "slug": "summary"})
        cell = await api.cells_show({"flow": "churn", "slug": "score"})

    # A note's docstring is not a description of the content; it is the content,
    # so the indentation the file needed must not reach the markdown.
    assert note["note"] is True
    assert note["doc"] == "The sweep so far.\n\n`lr=3e-4` won by a nose."
    assert cell["doc"] == "The headline metric."


async def test_a_cell_says_who_made_it_who_last_touched_it_and_under_what_intent(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.cells_edit(
            {
                "flow": "churn",
                "slug": "score",
                "source": SCORE_CELL.replace("0.91", "0.93"),
                "actor": "claude-1",
                "intent": "raised the threshold",
            }
        )
        shown = await api.cells_show({"flow": "churn", "slug": "score"})

    provenance = shown["provenance"]
    assert provenance["created_by"] == "user"
    assert provenance["last_edited_by"] == "claude-1"
    assert provenance["intent"] == "raised the threshold"
    assert provenance["step"] > provenance["created_step"]
    # Nobody else was editing, so the attribution above is a claim the store
    # can stand behind.
    assert provenance["attribution_uncertain"] is False


async def test_an_edit_in_an_agents_window_is_flagged_rather_than_named(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.agent_begin({"flow": "churn", "label": "claude-1"})
        # A file edit during a worktree session: it could be the agent, it could
        # be the human in another window. One worktree cannot tell them apart.
        write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.93"))
        shown = await api.cells_show({"flow": "churn", "slug": "score"})

    assert shown["provenance"]["last_edited_by"] == "claude-1"
    assert shown["provenance"]["attribution_uncertain"] is True


async def test_a_failure_keeps_the_author_of_the_version_that_broke(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.cells_edit(
            {
                "flow": "churn",
                "slug": "score",
                "source": BROKEN_CELL,
                "actor": "claude-1",
                "intent": "rewrote the metric",
            }
        )
        await api.run({"flow": "churn", "target": "score", "actor": "claude-1"})
        await api.cells_edit(
            {
                "flow": "churn",
                "slug": "score",
                "source": SCORE_CELL,
                "actor": "user",
                "intent": "put it back",
            }
        )
        shown = await api.cells_show({"flow": "churn", "slug": "score"})

    # The head has moved on, but the failure the branch still holds happened to
    # the agent's version — and a card decides how loudly to say so by who wrote
    # the code that broke, not by who typed last.
    assert shown["provenance"]["last_edited_by"] == "user"
    assert shown["failed_by"] == "claude-1"
    assert "the model did not converge" in shown["error"]


async def test_logs_answer_with_the_run_the_branch_observed_even_after_a_rewind(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", _talkative("first"))

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"flow": "churn", "target": "score"})
        after_first = api.hub.session("churn").store.next_step - 1
        write_cell(flow, "score", _talkative("second"))
        await api.run({"flow": "churn", "target": "score"})
        latest = await api.cells_logs({"flow": "churn", "slug": "score"})
        await api.rewind({"flow": "churn", "to_step": after_first})
        rewound = await api.cells_logs({"flow": "churn", "slug": "score"})

    assert "second" in latest["logs"] and "first" not in latest["logs"]
    # Every materialization keeps its own artifact, so a branch that moved back
    # reads what it observed then — not the newest run in the store.
    assert "first" in rewound["logs"] and "second" not in rewound["logs"]
    assert rewound["state"] == "succeeded"


async def test_a_cell_nobody_ran_has_no_logs_and_says_so_without_a_state(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        empty = await api.cells_logs({"flow": "churn", "slug": "score"})

    assert (empty["logs"], empty["state"]) == (None, None)


async def test_only_a_memo_hit_reads_as_reused_never_an_inherited_baseline(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        # Forked before anything ran, so this branch has nothing to inherit and
        # will have to ask for the result itself.
        await api.fork({"flow": "churn", "name": "early"})
        await api.run({"flow": "churn", "target": "score"})
        await api.fork({"flow": "churn", "name": "late"})
        await api.run({"flow": "churn", "target": "score", "branch": "early"})
        asked = await api.cells_list({"flow": "churn", "branch": "early"})
        inherited = await api.cells_list({"flow": "churn", "branch": "late"})
        ran = await api.cells_list({"flow": "churn"})

    # It asked, and a hit answered — which is why a cost sits on a card that
    # nothing ran for, and the one case the badge is about.
    assert asked["cells"][0]["reused"] is True
    # A fork inherits verdicts without any work having been skipped for it.
    assert inherited["cells"][0]["reused"] is False
    assert ran["cells"][0]["reused"] is False


def _talkative(word: str) -> str:
    return f"""
class Score:
    \"\"\"Prints, so the run leaves an artifact behind.\"\"\"
    produces = {{"summary": "asset"}}

    def materialize(self, ctx):
        print("{word}")
        return {{"summary": {{"auc": 0.91}}}}
"""


def _branch(tree: dict[str, Any], name: str) -> dict[str, Any]:
    return next(entry for entry in tree["branches"] if entry["branch"] == name)
