from pathlib import Path
from typing import Any

import pytest
from lumlflow.flow.errors import FlowError
from lumlflow.flow.store.models import CellNoted

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
    assert marked["intent"] == "before I rewrite the scorer"
    assert brief["checkpoint"]["step"] == marked["step"]
    assert brief["checkpoint"]["mark"] == "before I rewrite the scorer"
    assert brief["recent"][0]["step"] == marked["step"]
    assert brief["recent"][0]["mark"] == "before I rewrite the scorer"
    assert brief["recent"][0]["intent"] != "before I rewrite the scorer"


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
    assert all(entry["mark"] is None for entry in history)


async def test_a_rewind_moves_the_branch_and_the_tree_says_where_it_stands(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        recent = (await api.context({"flow": "churn"}))["recent"]
        assert recent[0]["position"] is False
        earlier = next(entry["step"] for entry in recent if entry["position"])
        await api.cells_edit(
            {
                "flow": "churn",
                "slug": "score",
                "source": SCORE_CELL.replace("0.91", "0.92"),
                "intent": "raise the score",
            }
        )
        before = _branch(await api.tree({"flow": "churn"}), "main")
        await api.rewind({"flow": "churn", "to_step": earlier})
        after = _branch(await api.tree({"flow": "churn"}), "main")
        brief = await api.context({"flow": "churn"})
        forked = await api.fork({"flow": "churn", "name": "from-there"})
        child = _branch(await api.tree({"flow": "churn"}), "from-there")

    assert before["head_step"] == before["newest_step"] == before["last_intent"]["step"]
    assert after["head_step"] == earlier
    assert after["newest_step"] == before["newest_step"]
    assert after["last_intent"]["step"] == earlier
    assert brief["position"] == {"step": earlier, "newest": before["newest_step"]}
    assert [entry["step"] for entry in brief["recent"]][0] == before["newest_step"]
    assert forked["parent_step"] == earlier
    assert child["parent_step"] == earlier


async def test_a_rewind_wakes_no_sweep_and_stays_where_it_was_put(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"flow": "churn", "target": "score"})
        await api.cells_edit(
            {
                "flow": "churn",
                "slug": "score",
                "source": SCORE_CELL.replace("0.91", "0.92"),
                "intent": "raise the score",
            }
        )
        edited = (await api.context({"flow": "churn"}))["recent"][0]["step"]
        await api.run({"flow": "churn", "target": "score"})
        session = api.hub.session("churn")
        await session.reactor.settled()
        before = session.store.next_step

        await api.rewind({"flow": "churn", "to_step": edited})
        await session.reactor.settled()
        after = session.store.next_step
        position = (await api.context({"flow": "churn"}))["position"]
        lines = [
            entry for entry in session.store.journal.replay() if entry.step >= before
        ]

    assert after == before + 1
    assert [op.op for entry in lines for op in entry.ops] == ["rewound"]
    assert position["step"] == edited


async def test_a_sweep_woken_by_another_lane_leaves_a_rewound_lane_alone(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"flow": "churn", "target": "score"})
        await api.cells_edit(
            {
                "flow": "churn",
                "slug": "score",
                "source": SCORE_CELL.replace("0.91", "0.92"),
                "intent": "raise the score",
            }
        )
        edited = (await api.context({"flow": "churn"}))["recent"][0]["step"]
        await api.run({"flow": "churn", "target": "score"})
        await api.fork({"flow": "churn", "name": "sweep"})
        session = api.hub.session("churn")
        await session.reactor.settled()
        await api.rewind({"flow": "churn", "to_step": edited})

        await api.cells_edit(
            {
                "flow": "churn",
                "branch": "sweep",
                "slug": "score",
                "source": SCORE_CELL.replace("0.91", "0.93"),
                "intent": "try another score",
            }
        )
        await session.reactor.settled()
        main_id = session.store.branches.get("main").branch_id
        sweep_id = session.store.branches.get("sweep").branch_id
        main_ops = [
            op.op
            for entry in session.store.journal.replay()
            if entry.step > edited and entry.branch == main_id
            for op in entry.ops
        ]
        sweep_ops = [
            op.op
            for entry in session.store.journal.replay()
            if entry.branch == sweep_id
            for op in entry.ops
        ]
        position = (await api.context({"flow": "churn"}))["position"]

    assert main_ops[-1] == "rewound"
    assert "run_recorded" in sweep_ops
    assert position["step"] == edited


async def test_a_checkpoint_marks_the_step_it_names_and_adds_none(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        before = (await api.context({"flow": "churn"}))["recent"]
        await api.cells_edit(
            {
                "flow": "churn",
                "slug": "score",
                "source": SCORE_CELL.replace("0.91", "0.92"),
                "intent": "raise the score",
            }
        )
        after_edit = (await api.context({"flow": "churn"}))["recent"]
        marked = await api.checkpoint(
            {"flow": "churn", "step": before[0]["step"], "intent": "the original"}
        )
        after_mark = (await api.context({"flow": "churn"}))["recent"]
        with pytest.raises(FlowError, match="not on main"):
            await api.checkpoint({"flow": "churn", "step": 10_000, "intent": "x"})
        with pytest.raises(FlowError, match="`step` must be an integer"):
            await api.checkpoint({"flow": "churn", "step": "soon", "intent": "x"})

    assert marked["step"] == before[0]["step"]
    assert marked["intent"] == "the original"
    assert [entry["step"] for entry in after_mark] == [
        entry["step"] for entry in after_edit
    ]
    by_step = {entry["step"]: entry for entry in after_mark}
    assert by_step[marked["step"]]["mark"] == "the original"
    assert by_step[after_edit[0]["step"]]["mark"] is None


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
    assert sweep["states"] == {"synced": 1}
    assert sweep["agent"] is None
    assert sweep["last_intent"]["intent"] == "try it higher"


async def test_the_fork_tree_carries_the_parent_step_the_child_copied(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.fork({"flow": "churn", "name": "sweep"})
        await api.cells_edit(
            {
                "flow": "churn",
                "branch": "main",
                "slug": "score",
                "source": SCORE_CELL.replace("0.91", "0.92"),
                "intent": "main at the split",
            }
        )
        marked_main = await api.checkpoint(
            {"flow": "churn", "branch": "main", "intent": "main at the split"}
        )
        await api.cells_edit(
            {
                "flow": "churn",
                "branch": "sweep",
                "slug": "score",
                "source": SCORE_CELL.replace("0.91", "0.93"),
                "intent": "sweep moved on",
            }
        )
        forked = await api.fork(
            {"flow": "churn", "name": "exp/lr", "from_branch": "main"}
        )
        at_fork = await api.tree({"flow": "churn"})
        await api.cells_edit(
            {
                "flow": "churn",
                "branch": "main",
                "slug": "score",
                "source": SCORE_CELL.replace("0.91", "0.94"),
                "intent": "main moved on",
            }
        )
        after_main_moved = await api.tree({"flow": "churn"})

    main = _branch(at_fork, "main")
    experiment = _branch(at_fork, "exp/lr")
    assert main["parent"] is None and main["parent_step"] is None
    assert forked["parent_step"] == marked_main["step"]
    assert experiment["parent_step"] == marked_main["step"]
    assert forked["forked_at_step"] == experiment["forked_at_step"]
    assert forked["forked_at_step"] > marked_main["step"]
    assert _branch(after_main_moved, "exp/lr")["parent_step"] == marked_main["step"]


async def test_a_fork_right_after_its_parent_uses_the_parents_creation_step(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        fresh = await api.fork({"flow": "churn", "name": "fresh"})
        nested = await api.fork(
            {"flow": "churn", "name": "fresh/a", "from_branch": "fresh"}
        )
        tree = await api.tree({"flow": "churn"})

    assert nested["parent_step"] == fresh["forked_at_step"]
    assert _branch(tree, "fresh/a")["parent_step"] == fresh["forked_at_step"]


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
    scoped = [line for line in history["transactions"] if line["branch"] == forked]
    assert [line["intent"] for line in scoped] == ["try it higher"]


async def test_a_cell_summary_names_its_kinds_its_steps_and_what_it_reads(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project", files={"raw.csv": "n\n1\n"})
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "train", TRAIN_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.cells_edit(
            {
                "flow": "churn",
                "slug": "score",
                "source": SCORE_CELL.replace("0.91", "0.92"),
            }
        )
        write_cell(flow, "load", EXTERNAL_CELL)
        await api.run({"flow": "churn", "target": "load"})
        listed = await api.cells_list({"flow": "churn"})

    cells = {entry["slug"]: entry for entry in listed["cells"]}
    assert cells["train"]["kinds"] == {"model": "model", "run": "experiment"}
    assert cells["load"]["kinds"] == {"rows": "frame"}
    assert cells["score"]["kinds"] == {"summary": "asset"}
    assert len({cell["uid"] for cell in cells.values()}) == len(cells)
    assert cells["score"]["created_step"] < cells["load"]["created_step"]
    assert cells["score"]["changed_step"] > cells["score"]["created_step"]
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
    assert deliberate["integrity"] == []
    assert siblings["integrity"] == []
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

    assert note["note"] is True
    assert note["doc"] == "The sweep so far.\n\n`lr=3e-4` won by a nose."
    assert cell["doc"] == "The headline metric."


async def test_cell_show_exposes_the_latest_note_per_kind(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        branch_id = session.store.branches.get("main").branch_id
        (version,) = session.store.index.slice_versions(branch_id).values()
        committed = session.store.commit(
            [
                CellNoted(
                    uid=version.uid,
                    kind="projection_completed",
                    sentence="restored score to its selected version",
                    version_id=version.version_id,
                )
            ],
            intent="recorded projection completion",
            actor="system",
            branch=branch_id,
        )

        shown = await api.cells_show({"flow": "churn", "slug": "score"})

    assert shown["notes"] == [
        {
            "kind": "projection_completed",
            "sentence": "restored score to its selected version",
            "version": version.version_id,
            "step": committed.step,
            "actor": "system",
        }
    ]


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
    assert "first" in rewound["logs"] and "second" not in rewound["logs"]
    assert rewound["state"] == "succeeded"


async def test_a_cell_summary_names_the_result_the_branch_observed(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", _talkative("first"))

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        unrun = await api.cells_list({"flow": "churn"})
        await api.run({"flow": "churn", "target": "score"})
        after_first = api.hub.session("churn").store.next_step - 1
        first = await api.cells_list({"flow": "churn"})
        write_cell(flow, "score", _talkative("second"))
        await api.run({"flow": "churn", "target": "score"})
        second = await api.cells_list({"flow": "churn"})
        await api.rewind({"flow": "churn", "to_step": after_first})
        rewound = await api.cells_list({"flow": "churn"})

    assert unrun["cells"][0]["mat_id"] is None
    first_id, second_id = first["cells"][0]["mat_id"], second["cells"][0]["mat_id"]
    assert first_id is not None and second_id not in (None, first_id)
    assert rewound["cells"][0]["mat_id"] == first_id


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
        await api.fork({"flow": "churn", "name": "early"})
        await api.run({"flow": "churn", "target": "score"})
        await api.fork({"flow": "churn", "name": "late"})
        await api.run({"flow": "churn", "target": "score", "branch": "early"})
        asked = await api.cells_list({"flow": "churn", "branch": "early"})
        inherited = await api.cells_list({"flow": "churn", "branch": "late"})
        ran = await api.cells_list({"flow": "churn"})

    assert asked["cells"][0]["reused"] is True
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


async def test_the_fork_tree_says_which_registered_agents_are_really_there(
    tmp_path: Path,
):
    from lumlflow.flow.daemon.api import Api
    from lumlflow.flow.daemon.hub import Hub

    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    address = str(root / "churn.flow")
    held: set[tuple[str | None, str, str]] = {
        (address, "codex", "Codex"),
        (str(root / "other.flow"), "gemini", "G"),
    }

    hub = Hub()
    try:
        api = Api(hub, directory=root, leases=lambda: held)
        await api.flow_open({"flow": "churn"})
        await api.agent_begin({"flow": "churn", "actor": "codex", "label": "Codex"})
        await api.agent_begin({"flow": "churn", "label": "claude-1"})
        tree = await api.tree({"flow": "churn"})
        status = await api.status({"flow": "churn"})
    finally:
        await hub.close()

    by_actor = {row["actor"]: row for row in tree["agent_sessions"]}
    assert by_actor["codex"]["leased"] is True
    assert by_actor["claude-1"]["leased"] is False
    assert "gemini" not in by_actor
    assert _branch(tree, "main")["agent"] == "claude-1"
    assert status["flows"][0]["agent_sessions"] == tree["agent_sessions"]
