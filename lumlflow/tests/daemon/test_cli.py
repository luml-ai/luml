"""The verbs, over a daemon running in this process.

Nothing is faked but the socket: `client.connect` hands back the API a real
daemon would answer with, so what runs here is the whole path a verb takes —
parsing, flow selection, the call, the store, a kernel process, and the words
that come back.

The sweep for internals is the point of several of these. `uid`s, content hashes
and memo keys are how the runtime keys its facts and are useless to a reader; a
surface that prints one has broken the Tier-0 contract, so every printed line
below is checked for them.
"""

import asyncio
import json
import re
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import typer.main
from lumlflow.cli import app
from lumlflow.flow import render
from lumlflow.flow.daemon import client, secrets
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.daemon.hub import Hub
from typer.testing import CliRunner, Result

from tests.daemon.helpers import (
    BROKEN_CELL,
    FRAME_CELL,
    REPORT_CELL,
    SCORE_CELL,
    FakeLuml,
    LocalDaemon,
    make_workspace,
    no_git_words,
    source_of,
    uv_that_locks,
    write_cell,
    write_file,
    write_lock,
)

Invoke = Callable[..., Result]

ULID = re.compile(r"\b[0-9A-HJKMNP-TV-Z]{26}\b")
SHA256 = re.compile(r"\b[0-9a-f]{64}\b")

HOLED_FRAME_CELL = """
class Rows:
    \"\"\"A frame with a hole in it, so dropping rows shows.\"\"\"
    produces = {"rows": {"type": "asset", "kind": "frame"}}

    def materialize(self, ctx):
        import pandas

        return {"rows": pandas.DataFrame({"n": [1.0, None, 3.0]})}
"""

FANOUT_CELL = """
class Fanout:
    \"\"\"Two outputs, read by two different cells.\"\"\"
    consumes = {"summary": "score.summary"}
    produces = {"curves": "experiment", "config": "asset"}

    def materialize(self, ctx, summary):
        return {"curves": {"auc": summary["auc"]}, "config": {"lr": 0.1}}
"""


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return make_workspace(tmp_path / "project", flows=())


@pytest.fixture
def platform() -> FakeLuml:
    """No verb here reaches the real platform: the daemon process is what wires
    an uploader in, and this stands in for it."""
    return FakeLuml()


@pytest.fixture
def cli(
    workspace: Path, platform: FakeLuml, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Invoke]:
    loop = asyncio.new_event_loop()
    hub = Hub(workspace, uploader=platform)
    api = Api(hub)
    monkeypatch.setattr(
        client, "connect", lambda root, **kwargs: LocalDaemon(api, loop)
    )
    runner = CliRunner()

    def invoke(*args: str, cwd: Path | None = None, stdin: str | None = None) -> Result:
        monkeypatch.chdir(cwd or workspace)
        return runner.invoke(app, list(args), input=stdin)

    try:
        yield invoke
    finally:
        loop.run_until_complete(hub.close())
        loop.close()


def test_the_tier0_loop_runs_on_names_and_leaks_no_internals(
    cli: Invoke, workspace: Path
):
    """Edit a cell, run it, read the failure, fix it, rerun — the whole product.

    Every command here names a cell and nothing else, and the failure is read
    off `status` and `cells show` rather than out of a traceback the verb raised.
    """
    cli("init", "churn")
    flow = workspace / "churn.flow"
    write_cell(flow, "score", BROKEN_CELL)

    failed = cli("run", "score")
    after = cli("status")
    shown = cli("cells", "show", "score")

    write_cell(flow, "score", SCORE_CELL)
    fixed = cli("run", "score")
    settled = cli("status")

    assert failed.exit_code == 1
    assert "failed  `score`" in failed.output
    assert "score" in after.output and "failed" in after.output
    assert "the model did not converge" in shown.output
    assert fixed.exit_code == 0
    assert "ran     `score`" in fixed.output
    assert "current" in settled.output
    for result in (failed, after, shown, fixed, settled):
        _no_internals(result)


def test_json_carries_the_identifiers_the_printed_form_leaves_out(cli: Invoke):
    """`--json` is the escape hatch: a program can have what a reader cannot."""
    cli("init", "churn")
    created = cli("cells", "new", "score", "--json")
    printed = cli("cells", "new", "report")

    payload = json.loads(created.output)
    assert payload["slug"] == "score"
    assert SHA256.search(payload["definition_hash"])
    _no_internals(printed)


def test_a_flow_that_fails_says_so_in_words_and_exits_nonzero(cli: Invoke):
    cli("init", "churn")

    missing = cli("run", "nowhere")
    unknown = cli("cells", "show", "nowhere")
    as_json = cli("run", "nowhere", "--json")

    assert missing.exit_code == 1
    assert "nowhere" in missing.output
    assert "Traceback" not in missing.output
    assert unknown.exit_code == 1
    assert json.loads(as_json.output)["kind"] == "CellNotFound"
    _no_internals(missing)
    _no_internals(unknown)


def test_a_cwd_inside_a_flow_addresses_it_and_ambiguity_names_the_candidates(
    cli: Invoke, workspace: Path
):
    cli("init", "churn")
    cli("init", "sales")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)

    inside = cli("cells", "list", cwd=workspace / "churn.flow")
    outside = cli("cells", "list")
    named = cli("cells", "list", "--flow", "churn")

    assert "score" in inside.output
    assert outside.exit_code == 1
    assert "`churn`" in outside.output and "`sales`" in outside.output
    assert "--flow" in outside.output
    assert "score" in named.output


def test_cells_new_after_prefills_the_wiring_and_the_signature(
    cli: Invoke, workspace: Path
):
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)
    cli("cells", "list")

    cli("cells", "new", "report", "--after", "score", "--doc", "Reads the score.")
    source = (workspace / "churn.flow" / "cells" / "report.py").read_text("utf-8")
    wired = cli("graph")

    assert 'consumes = {"summary": "score.summary"}' in source
    assert "def materialize(self, ctx, summary):" in source
    assert "from __future__ import annotations" in source
    assert "_check: CellProtocol = Report()" in source
    assert "score.summary → report (summary)" in wired.output


def test_sliced_queries_answer_the_narrow_question(cli: Invoke, workspace: Path):
    """`--unsynced` and `--around` are what keep a big flow answerable."""
    cli("init", "churn")
    flow = workspace / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)
    write_cell(flow, "fanout", FANOUT_CELL)
    cli("run", "score")

    unsynced = cli("cells", "list", "--unsynced")
    near = cli("graph", "--around", "report", "--depth", "1")

    assert "score" not in unsynced.output.replace("score.summary", "")
    assert "report" in unsynced.output and "fanout" in unsynced.output
    # One hop from `report` is `score`; `fanout` hangs off `score` two hops away.
    assert "fanout" not in near.output
    assert "report" in near.output and "score" in near.output
    _no_internals(unsynced)
    _no_internals(near)


def test_diff_separates_an_edit_from_a_result_that_merely_moved(
    cli: Invoke, workspace: Path
):
    """The two divergences a comparison must never conflate: someone edited the
    cell, or the same code was fed something different."""
    flow = workspace / "churn.flow"
    cli("init", "churn")
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)
    cli("run", "report")
    cli("fork", "sweep", "-m", "try a higher score")
    cli("switch", "sweep")
    write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.95"))
    cli("run", "report")

    compared = cli("diff", "main", "sweep")
    narrowed = cli("asset", "diff", "report", "--branch", "main", "--branch", "sweep")
    too_many = cli("diff", "main")

    edited = compared.output.index("edited on one side")
    results = compared.output.index("same code, different results")
    assert compared.output.index("score", edited) < results
    assert compared.output.index("report", results) > results
    assert "definition same · result differs" in narrowed.output
    assert too_many.exit_code == 1
    _no_internals(compared)
    _no_internals(narrowed)


def test_force_spends_the_cost_the_store_would_have_saved(cli: Invoke, workspace: Path):
    """`--force` is the one way past memoization, and it says which run it was:
    a rerun that answered from the memo and one that recomputed read the same
    without this."""
    flow = workspace / "churn.flow"
    cli("init", "churn")
    write_cell(flow, "score", SCORE_CELL)
    cli("run", "score")

    again = cli("run", "score")
    forced = cli("run", "score", "--force")

    assert "skipped `score` · already current" in again.output
    assert "ran     `score`" in forced.output
    _no_internals(forced)


def test_leaving_a_run_nobody_is_waiting_on_says_that(cli: Invoke, workspace: Path):
    """Cancel never claims a stop it did not perform — including the case where
    there was nothing to stop."""
    cli("init", "churn")

    left = cli("cancel")

    assert "was not waiting on a run" in left.output
    _no_internals(left)


def test_rename_rewrites_the_consumers_and_costs_nothing(cli: Invoke, workspace: Path):
    flow = workspace / "churn.flow"
    cli("init", "churn")
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)
    cli("run", "report")

    renamed = cli("rename", "score", "headline", "-m", "clearer name")
    after = cli("cells", "list")
    consumer = (flow / "cells" / "report.py").read_text("utf-8")

    assert "`score` is now `headline`" in renamed.output
    assert "rewritten to match: report" in renamed.output
    assert 'consumes = {"summary": "headline.summary"}' in consumer
    assert not (flow / "cells" / "score.py").exists()
    # A rename is a spelling, not a change: nothing went stale behind it.
    assert "unsynced" not in after.output
    _no_internals(renamed)


def test_renaming_a_cell_that_does_not_parse_moves_it_rather_than_copying_it(
    cli: Invoke, workspace: Path
):
    """A broken file carries no uid line to read an identity off, and a rename
    that minted a fresh one would leave the branch holding the cell twice."""
    flow = workspace / "churn.flow"
    cli("init", "churn")
    write_cell(flow, "half", 'class Half:\n    """Mid-edit."""\n    produces = {')

    renamed = cli("rename", "half", "partial")
    listed = cli("cells", "list")

    assert renamed.exit_code == 0
    named = [name for name in ("half", "partial") if name in listed.output]
    assert named == ["partial"]
    assert not (flow / "cells" / "half.py").exists()
    assert (flow / "cells" / "partial.py").exists()


def test_forking_from_another_branch_says_which_one_it_forked_from(
    cli: Invoke, workspace: Path
):
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)
    cli("fork", "alpha")

    forked = cli("fork", "beta", "--from", "alpha", "--json")
    printed = cli("fork", "gamma", "--from", "alpha")
    shown = cli("tree")

    assert json.loads(forked.output)["from_branch"] == "alpha"
    assert "started `gamma` from `alpha`" in printed.output
    assert "beta" in shown.output and "started from alpha" in shown.output


def test_rewind_asks_nothing_and_recomputes_nothing(cli: Invoke, workspace: Path):
    """Persist-everything is what makes the verb prompt-free: every value the
    older step referenced is still in the store, so there is no preflight to
    gate on and nothing to confirm."""
    flow = workspace / "churn.flow"
    cli("init", "churn")
    write_cell(flow, "score", SCORE_CELL)
    cli("run", "score")
    at = json.loads(cli("context", "--json").output)["checkpoint"]["step"]
    write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.77"))
    cli("status")

    rewound = cli("rewind", str(at), "-m", "back to the one that scored", stdin="")
    listed = cli("cells", "list", "--json")

    assert rewound.exit_code == 0
    assert f"is back at step {at}" in rewound.output
    assert "0.91" in source_of(flow, "score")
    # Synced, not queued: the run that step referenced is still the baseline, so
    # the rewind cost a selection write and no execution.
    states = [entry["state"] for entry in json.loads(listed.output)["cells"]]
    assert states == ["synced"]
    _no_internals(rewound)


def test_adopt_takes_the_winner_and_never_overwrites_a_side_silently(
    cli: Invoke, workspace: Path
):
    """The whole v1 merge story: one asset, picked per branch. A cell both
    sides moved since the fork is a conflict, not a last-write-wins."""
    flow = workspace / "churn.flow"
    cli("init", "churn")
    write_cell(flow, "score", SCORE_CELL)
    cli("run", "score")
    cli("fork", "sweep")
    cli("switch", "sweep")
    write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.95"))
    cli("status")
    cli("switch", "main")

    adopted = cli("adopt", "score", "--from", "sweep", "-m", "the sweep won")
    took = source_of(flow, "score")
    # Now main moves too, so the next adopt has two sides that both edited.
    write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.42"))
    cli("status")
    cli("switch", "sweep")
    write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.96"))
    cli("status")
    cli("switch", "main")
    refused = cli("adopt", "score", "--from", "sweep", stdin="")

    assert adopted.exit_code == 0
    assert "0.95" in took
    assert refused.exit_code == 1
    assert "pick a side" in refused.output
    # Refused means refused: main keeps the version it had.
    assert "0.42" in source_of(flow, "score")
    _no_internals(adopted)
    _no_internals(refused)


def test_a_brief_on_another_branch_does_not_claim_the_agents_files(
    cli: Invoke, workspace: Path
):
    """Viewing a branch is a store read: the worktree, and whoever holds it,
    belong to the branch that is checked out and to no other."""
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)
    cli("fork", "alpha")
    cli("agent", "begin", "--label", "claude-1")

    here = cli("context", "--json")
    there = cli("context", "--branch", "alpha", "--json")
    printed = cli("context", "--branch", "alpha")

    assert json.loads(here.output)["checked_out"] is True
    assert json.loads(here.output)["agent"] == "claude-1"
    assert json.loads(there.output)["checked_out"] is False
    assert json.loads(there.output)["agent"] is None
    assert "(not on disk)" in printed.output
    # The session still shows up in the history, which is true; what it must
    # not do is claim to be working in a branch nobody checked out.
    assert "is working here" not in printed.output


def test_a_secret_belongs_to_the_flow_whose_history_names_it(
    cli: Invoke, workspace: Path
):
    cli("init", "churn")
    cli("init", "sales")

    cli("secrets", "set", "API_KEY", "--value", "hunter2", "--flow", "churn")
    churn = cli("secrets", "list", "--flow", "churn")
    sales = cli("secrets", "list", "--flow", "sales")

    assert "API_KEY" in churn.output
    assert "no secrets set here" in sales.output
    # The value is scoped the same way the names are, so the two agree.
    assert secrets.get(workspace / "churn.flow", "API_KEY") == "hunter2"
    assert secrets.get(workspace / "sales.flow", "API_KEY") is None


def test_deleting_a_cell_is_per_branch_and_says_so(cli: Invoke, workspace: Path):
    flow = workspace / "churn.flow"
    cli("init", "churn")
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)
    cli("cells", "list")
    cli("fork", "sweep")

    deleted = cli("cells", "delete", "score", "-m", "not needed here")
    here = cli("cells", "list")
    there = cli("cells", "list", "--branch", "sweep")

    assert "other lanes are untouched" in deleted.output
    assert "left pointing at nothing here: report" in deleted.output
    assert "score" not in here.output.replace("score.summary", "")
    assert "score" in there.output
    _no_internals(deleted)


def test_preview_reads_the_stored_preview_without_starting_a_kernel(
    cli: Invoke, workspace: Path
):
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)
    cli("run", "score")
    cli("daemon", "stop")

    previewed = cli("asset", "preview", "score")

    assert "score.summary · main · current" in previewed.output
    assert "auc: 0.91" in previewed.output
    _no_internals(previewed)


def test_a_multi_output_cell_previews_its_primary_output(cli: Invoke, workspace: Path):
    """The card opens on the experiment, not on the config dump beside it."""
    flow = workspace / "churn.flow"
    cli("init", "churn")
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "fanout", FANOUT_CELL)
    cli("run", "fanout")

    primary = cli("asset", "preview", "fanout")
    named = cli("asset", "preview", "fanout.config")

    assert "fanout.curves" in primary.output
    assert "fanout.config" in named.output


def test_an_edit_that_started_from_a_moved_head_is_a_question(
    cli: Invoke, workspace: Path
):
    """The optimistic lock the UI's editor takes, reachable from a terminal."""
    flow = workspace / "churn.flow"
    cli("init", "churn")
    write_cell(flow, "score", SCORE_CELL)
    base = json.loads(cli("cells", "show", "score", "--json").output)["definition_hash"]
    write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.93"))
    cli("cells", "list")

    edited = SCORE_CELL.replace("0.91", "0.99")
    refused = cli("cells", "edit", "score", "--base", base, stdin=edited)
    forced = cli("cells", "edit", "score", "--base", base, "--force", stdin=edited)

    assert refused.exit_code == 1
    assert "has a newer version than this edit started from" in refused.output
    assert "save this edit to a new lane" in refused.output
    assert forced.exit_code == 0
    assert "0.99" in (flow / "cells" / "score.py").read_text("utf-8")
    _no_internals(refused)


def test_a_working_agent_holds_the_files_until_it_is_forced_off(
    cli: Invoke, workspace: Path
):
    flow = workspace / "churn.flow"
    cli("init", "churn")
    write_cell(flow, "score", SCORE_CELL)
    cli("fork", "sweep")
    cli("agent", "begin", "--label", "claude-1")

    blocked = cli("switch", "sweep")
    seen = cli("tree")
    forced = cli("switch", "sweep", "--force")

    assert blocked.exit_code == 1
    assert "claude-1 holds these files" in blocked.output
    assert "force this through" in blocked.output
    assert "claude-1 is working here" in seen.output
    assert forced.exit_code == 0
    _no_internals(blocked)


def test_an_output_with_no_bytes_says_what_to_do_about_it(cli: Invoke, workspace: Path):
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)

    early = cli("asset", "download", "score", "--json")

    assert early.exit_code == 1
    answered = json.loads(early.output)
    assert answered["kind"] == "ValueNotStored"
    assert "run `score` first" in answered["error"]


def test_promote_publishes_a_stored_output_and_names_only_the_cell(
    cli: Invoke, workspace: Path, platform: FakeLuml
):
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)
    cli("run", "score")

    published = cli("promote", "score.summary", "-m", "shipping the baseline")
    answered = json.loads(cli("promote", "score.summary", "--json").output)

    assert "`score.summary` is published" in published.output
    assert [request.slug for request in platform.received] == ["score"]
    # The reference is a `--json` fact: a printed line speaks the cell.
    assert answered["reference"]["collection"] == "col-1"
    _no_internals(published)


def test_promote_offline_says_it_is_queued_rather_than_claiming_a_publish(
    cli: Invoke, workspace: Path, platform: FakeLuml
):
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)
    cli("run", "score")
    platform.offline = True

    failed = cli("promote", "score.summary")

    assert "did not upload" in failed.output
    assert "unreachable" in failed.output
    assert "tries again" in failed.output
    _no_internals(failed)


def test_secrets_are_named_but_never_shown(cli: Invoke):
    cli("init", "churn")

    stored = cli("secrets", "set", "API_KEY", "--value", "hunter2")
    listed = cli("secrets", "list")

    assert "API_KEY" in stored.output and "hunter2" not in stored.output
    assert listed.output.strip() == "API_KEY"


@pytest.mark.skipif(
    sys.platform == "win32", reason="the uv stub is a POSIX shell script"
)
def test_env_verbs_move_the_lockfile_and_name_the_kernel_left_behind(
    cli: Invoke, workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The install lands, the results stand, and the one thing that has to be
    said out loud is that the running kernel is holding the older code."""
    write_lock(workspace, {"pandas": "1.0.0"})
    log = uv_that_locks(tmp_path, {"pandas": "9.9.9", "lightgbm": "4.5.0"}, monkeypatch)
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "rows", FRAME_CELL)
    cli("run", "rows")

    added = cli("env", "add", "lightgbm", "-m", "trying lightgbm")
    listed = cli("env", "status")
    status = cli("status")
    shown = cli("cells", "show", "rows")

    assert log.read_text("utf-8").strip() == "add lightgbm"
    assert "lightgbm 4.5.0" in added.output
    assert "lightgbm 4.5.0" in listed.output
    assert "restart the kernel to apply `pandas`" in status.output
    assert "computed under an older env" in shown.output
    for result in (added, listed, status, shown):
        _no_internals(result)


def test_an_agent_session_brackets_the_command_it_runs(cli: Invoke, workspace: Path):
    cli("init", "churn")

    argv = ("agent", "exec", "--label", "claude-1", "--", sys.executable, "-c", "pass")
    session = cli(*argv)
    tree = cli("tree")

    assert session.exit_code == 0
    # The session ended, so nobody holds the files any more.
    assert "is working here" not in tree.output


def test_root_and_daemon_status_answer_without_a_flow(cli: Invoke, workspace: Path):
    where = cli("root")
    daemon = cli("daemon", "status")

    assert where.output.strip() == str(workspace)
    assert "not running" in daemon.output


def test_status_says_what_the_flow_costs_on_disk(cli: Invoke, workspace: Path):
    """Nothing here is prunable on request, so the number has to be honest —
    it is what the flow costs, not what a sweep could give back."""
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)
    cli("run", "score")

    reported = cli("status")
    as_json = json.loads(cli("status", "--json").output)

    store = workspace / "churn.flow" / ".lumlflow"
    on_disk = sum(path.stat().st_size for path in store.rglob("*") if path.is_file())
    assert as_json["flows"][0]["disk_bytes"] == on_disk
    assert "on disk" in reported.output
    _no_internals(reported)


def test_status_notes_shared_code_that_wandered_into_the_flow(
    cli: Invoke, workspace: Path
):
    """A flow is one directory of cells. A stray module still works — it is
    shared code, hashed with the rest — but nothing says so unless status does."""
    cli("init", "churn")
    write_file(workspace / "churn.flow" / "util.py", "SCALE = 2")

    noted = cli("status")
    payload = json.loads(cli("status", "--json").output)

    (note,) = payload["flows"][0]["hygiene"]
    assert "`churn.flow/util.py`" in note and "not a cell" in note
    assert note in noted.output
    # Shared code, not a rejected cell: it is hashed with the rest and the
    # branch holds nothing by that name.
    assert payload["flows"][0]["cells"] == []
    _no_internals(noted)


def test_status_carries_the_did_you_mean_a_broken_reference_earns(
    cli: Invoke, workspace: Path
):
    """A flag is never a rejection: the cell is accepted, `status` says what is
    wrong with it in words, and the loop carries on around it."""
    flow = workspace / "churn.flow"
    cli("init", "churn")
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL.replace("score.summary", "score.summry"))

    listed = cli("status")
    ran = cli("run", "score")

    assert "did you mean `score.summary`?" in listed.output
    assert ran.exit_code == 0
    _no_internals(listed)


def test_status_names_an_edit_the_files_have_not_been_told_about(
    cli: Invoke, workspace: Path
):
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)
    cli("agent", "begin", "--label", "claude-1")

    cli("cells", "edit", "score", stdin=SCORE_CELL.replace("0.91", "0.77"))
    held = cli("status")

    assert "saved, not yet written to files: `score`" in held.output
    _no_internals(held)


def test_an_intent_typed_at_a_verb_is_what_the_history_reads_back(
    cli: Invoke, workspace: Path
):
    """`-m` is the whole reason a journal is worth reading twice."""
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)

    cli("fork", "sweep", "-m", "try it with the wider window")
    read_back = cli("tree")

    assert "last: user · try it with the wider window" in read_back.output
    _no_internals(read_back)


def test_the_scratch_repl_hands_out_copies_and_writes_nothing(
    cli: Invoke, workspace: Path
):
    """`lumlflow eval` against a frame, mutating it — and the store is untouched.

    The mutation is real inside the expression that made it, which is what a
    REPL is for; the next one starts from the branch's value again, and nothing
    in between became a stored value.
    """
    pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    cli("init", "churn")
    flow = workspace / "churn.flow"
    write_cell(flow, "train_df", HOLED_FRAME_CELL)
    cli("run", "train_df")
    stored = _stored_values(flow)

    mutated = cli("eval", "train_df.dropna(inplace=True); len(train_df)")
    again = cli("eval", "len(train_df)")

    assert mutated.output.strip() == "2"
    assert again.output.strip() == "3"
    assert _stored_values(flow) == stored
    _no_internals(mutated)


def test_a_failing_expression_prints_its_traceback_and_exits_nonzero(
    cli: Invoke, workspace: Path
):
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)
    cli("run", "score")

    failed = cli("eval", "score['missing']")

    assert failed.exit_code == 1
    assert "KeyError" in failed.output
    _no_internals(failed)


def test_paging_reads_a_window_into_a_value_a_preview_only_summarises(
    cli: Invoke, workspace: Path
):
    pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "rows", FRAME_CELL)
    cli("run", "rows")

    previewed = cli("asset", "preview", "rows")
    paged = cli("asset", "page", "rows.rows", "--offset", "10", "--limit", "3")

    assert "50 rows in all" in previewed.output
    assert json.loads(paged.output)["rows"] == [[10], [11], [12]]


def test_export_writes_a_file_import_reads_back_into_another_flow(
    cli: Invoke, workspace: Path, tmp_path: Path
):
    """The round trip, as a user drives it: two verbs and a file between them."""
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)
    write_cell(workspace / "churn.flow", "report", REPORT_CELL)
    carried = tmp_path / "carried.py"

    exported = cli("export", str(carried))
    cli("init", "copy")
    imported = cli("import", str(carried), "--flow", "copy", "-m", "took churn's cells")
    landed = cli("cells", "list", "--flow", "copy")

    assert f"wrote {carried} · 2 cells from `main`" in exported.output
    assert "this file holds the cells" in exported.output
    assert "imported 2 cells into `main`: `score`, `report`" in imported.output
    assert source_of(workspace / "copy.flow", "score") == source_of(
        workspace / "churn.flow", "score"
    )
    assert "score" in landed.output and "report" in landed.output
    for result in (exported, imported, landed):
        _no_internals(result)


def test_export_says_when_the_file_it_wrote_is_workspace_code(
    cli: Invoke, workspace: Path
):
    """A `.py` in the workspace is shared code, whatever a person meant by it —
    and shared code moving is what marks every cell unsynced."""
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)

    inside = cli("export", "flow.py")

    assert "note: flow.py sits in the workspace" in inside.output
    assert (workspace / "flow.py").exists()


def test_export_json_carries_the_file_a_program_would_write(
    cli: Invoke, tmp_path: Path
):
    cli("init", "churn")

    answered = json.loads(cli("export", str(tmp_path / "carried.py"), "--json").output)

    assert answered["source"].startswith("# lumlflow file export")
    assert answered["path"] == str(tmp_path / "carried.py")


def test_importing_something_that_is_not_an_export_says_what_writes_one(
    cli: Invoke, tmp_path: Path
):
    cli("init", "churn")
    stray = write_file(tmp_path / "notes.py", "print('hello')")

    refused = cli("import", str(stray))
    missing = cli("import", str(tmp_path / "gone.py"))

    assert refused.exit_code == 1
    assert "not a lumlflow export" in refused.output
    assert missing.exit_code == 1
    assert "cannot read" in missing.output


def _stored_values(flow: Path) -> list[str]:
    """Every value the flow holds, by content — a new one would be a new name."""
    values = flow / ".lumlflow" / "values"
    return sorted(path.name for path in values.rglob("*") if path.is_file())


def _no_internals(result: Result) -> None:
    """No uid, content hash, or memo key reaches a printed line.

    An echoed cell file is exempt, and only that: the uid line is in the file
    the author is about to edit, so showing the source without it would show a
    file that does not exist.
    """
    spoken = result.output.split(render.SOURCE_RULE)[0]
    leaked = ULID.findall(spoken) + SHA256.findall(spoken)
    assert not leaked, f"internals leaked: {leaked}\n{spoken}"


def test_the_lane_group_holds_the_verbs_that_were_spelled_like_gits(cli: Invoke):
    """One noun group, and the four spellings it replaced still answering.

    The rename is a reading change, not a wire change: `lane new` is the `fork`
    daemon method under a name that collides with neither git nor the rest of
    this platform, and the old verb keeps working so no script breaks on it.
    """
    cli("init", "churn")
    started = cli("lane", "new", "sweep", "-m", "a lower lr")
    listed = cli("lane", "list")
    used = cli("lane", "use", "sweep")
    retired = cli("fork", "second", "-m", "the old spelling still answers")

    assert "started `sweep` from `main`" in started.output
    assert "sweep" in listed.output and "started from main" in listed.output
    assert "on `sweep`" in used.output
    assert retired.exit_code == 0
    assert "started `second` from `sweep`" in retired.output


def test_the_group_the_lane_group_replaced_still_answers_unlisted(cli: Invoke):
    """`lumlflow variant` was this word's previous spelling. It is hidden, not
    removed: the group is mounted twice, so both names reach the same verbs."""
    cli("init", "churn")
    started = cli("variant", "new", "sweep", "-m", "the previous spelling")
    listed = cli("variant", "list")

    assert started.exit_code == 0
    assert "started `sweep` from `main`" in started.output
    assert "sweep" in listed.output
    assert "variant" not in cli("--help").output


def test_the_retired_option_spellings_still_select_a_lane(cli: Invoke):
    """`--variant`, `--branch` and `--unsynced` are hidden, not removed."""
    cli("init", "churn")
    cli("lane", "new", "sweep", "-m", "a lower lr")

    by_lane = cli("context", "--lane", "sweep")
    by_variant = cli("context", "--variant", "sweep")
    by_branch = cli("context", "--branch", "sweep")
    stale = cli("cells", "list", "--unsynced")

    assert [named.exit_code for named in (by_lane, by_variant, by_branch)] == [0, 0, 0]
    assert all("sweep" in named.output for named in (by_lane, by_variant, by_branch))
    assert stale.exit_code == 0


def test_no_visible_help_speaks_the_vocabulary_git_owns():
    """A flow lives inside a git repository, so its verbs must not sound alike.

    Hidden commands are exempt by definition: each one *is* a git spelling,
    kept reachable for scripts and shown to nobody.
    """
    runner = CliRunner()
    for path in _visible_paths():
        result = runner.invoke(app, [*path, "--help"])
        assert result.exit_code == 0, f"`{' '.join(path)} --help` failed"
        no_git_words(result.output, f"`lumlflow {' '.join(path)} --help`")


def test_no_verb_prints_the_vocabulary_git_owns(cli: Invoke, workspace: Path):
    """The same sweep over what the verbs actually say, not what they promise."""
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)
    cli("run", "score")
    cli("lane", "new", "sweep", "-m", "a lower lr")

    spoken = [
        ("status",),
        ("context",),
        ("lane", "list"),
        ("cells", "list"),
        ("graph",),
        ("preflight", "score"),
        ("diff", "main", "sweep"),
        ("lane", "use", "sweep"),
        ("lane", "archive", "sweep"),
    ]
    for verb in spoken:
        result = cli(*verb)
        assert result.exit_code == 0, f"`{' '.join(verb)}` failed:\n{result.output}"
        no_git_words(result.output, f"`lumlflow {' '.join(verb)}`")


def _visible_paths(
    command: Any = None, path: tuple[str, ...] = ()
) -> Iterator[tuple[str, ...]]:
    """Every command a reader can reach from `--help`, and none they cannot."""
    if command is None:
        command = typer.main.get_command(app)
    yield path
    for name, child in getattr(command, "commands", {}).items():
        if not child.hidden:
            yield from _visible_paths(child, (*path, name))
