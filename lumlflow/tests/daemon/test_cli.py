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
import contextlib
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import typer.main
import websockets.sync.client
import yaml
from lumlflow.cli import app
from lumlflow.flow import render
from lumlflow.flow.daemon import client, docs, web
from lumlflow.flow.daemon import workspace as daemon_workspace
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.daemon.hub import Hub
from lumlflow.flow.daemon.workspace import DaemonRecord
from lumlflow.flow.store.cas import Cas
from typer.testing import CliRunner, Result

from tests.daemon.conftest import Reap
from tests.daemon.helpers import (
    BROKEN_CELL,
    FRAME_CELL,
    REPORT_CELL,
    SCORE_CELL,
    LocalDaemon,
    make_workspace,
    no_git_words,
    source_of,
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
        ctx.tracker.log_metric("auc", summary["auc"])
        return {"curves": ctx.tracker.record, "config": {"lr": 0.1}}
"""


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return make_workspace(tmp_path / "project", flows=())


@pytest.fixture
def cli(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Invoke]:
    loop = asyncio.new_event_loop()
    hub = Hub()
    api = Api(hub, directory=workspace)
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


def test_status_env_and_context_name_the_interpreter_and_its_source(
    cli: Invoke, workspace: Path
) -> None:
    cli("init", "churn")
    expected = f"python    {Path(sys.executable)} · source lumlflow's own interpreter"

    shown = [cli("status"), cli("env", "status"), cli("context")]
    context_payload = json.loads(cli("context", "--json").output)

    assert all(expected in result.output for result in shown)
    assert context_payload["python"] == {
        "path": str(Path(sys.executable)),
        "source": "lumlflow",
    }


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


def test_status_and_init_take_a_directory(
    cli: Invoke, workspace: Path, tmp_path: Path
) -> None:
    requested = make_workspace(tmp_path / "requested", flows=("sales",))

    status = cli("status", str(requested), "--json")
    created = cli("init", "sweep", str(requested), "--json")

    assert status.exit_code == 0, status.output
    assert [flow["path"] for flow in json.loads(status.output)["flows"]] == [
        str(requested / "sales.flow")
    ]
    assert created.exit_code == 0, created.output
    assert json.loads(created.output)["path"] == str(requested / "sweep.flow")
    assert (requested / "sweep.flow").is_dir()


def test_agents_cli_lists_consents_sets_up_and_removes(
    cli: Invoke,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "agent-home"
    binary_dir = tmp_path / "agent-bin"
    for name in ("claude", "lumlflow"):
        executable = write_file(binary_dir / name, "#!/bin/sh")
        executable.chmod(0o755)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setenv("PATH", str(binary_dir))

    listed = cli("agents", "list")
    declined = cli("agents", "setup", "claude-code", stdin="n\n")
    config = home / ".claude.json"

    assert listed.exit_code == 0, listed.output
    assert "Claude Code (claude-code) · not set up" in listed.output
    assert declined.exit_code == 0, declined.output
    assert "was not set up" in declined.output
    assert not config.exists()

    set_up = cli("agents", "setup", "claude-code", stdin="y\n")
    removed = cli("agents", "remove", "claude-code")

    assert set_up.exit_code == 0, set_up.output
    assert "Claude Code · set up" in set_up.output
    assert "approve the server when Claude Code asks" in set_up.output
    assert removed.exit_code == 0, removed.output
    assert "removed lumlflow from Claude Code" in removed.output
    assert json.loads(config.read_text("utf-8"))["mcpServers"] == {}


def test_guide_prints_the_same_text_the_mcp_resource_serves(cli: Invoke) -> None:
    guided = cli("guide")

    assert guided.exit_code == 0
    assert guided.output == docs.CHEATSHEET


def test_status_from_each_cwd_reaches_one_daemon_and_lists_only_that_directory(
    cli: Invoke, workspace: Path, tmp_path: Path
) -> None:
    subdirectory = workspace / "sub"
    subdirectory.mkdir()
    other = make_workspace(tmp_path / "other", flows=("sales",))

    from_subdirectory = cli("status", "--json", cwd=subdirectory)
    from_other = cli("status", "--json", cwd=other)

    assert from_subdirectory.exit_code == 0, from_subdirectory.output
    assert from_other.exit_code == 0, from_other.output
    empty = json.loads(from_subdirectory.output)
    sales = json.loads(from_other.output)
    assert empty["pid"] == sales["pid"]
    assert empty["workspace"] == str(subdirectory)
    assert empty["flows"] == []
    assert sales["workspace"] == str(other)
    assert [flow["path"] for flow in sales["flows"]] == [str(other / "sales.flow")]


def test_cells_new_after_prefills_the_wiring_and_the_signature(
    cli: Invoke, workspace: Path
):
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)
    cli("cells", "list")

    cli(
        "cells",
        "new",
        "report",
        "--after",
        "score",
        "--doc",
        "Reads the score.",
    )
    anchored = cli(
        "cells", "new", "note", "--anchor", "score", "--doc", "Beside score."
    )
    source = (workspace / "churn.flow" / "cells" / "report.py").read_text("utf-8")
    wired = cli("graph")
    order = yaml.safe_load((workspace / "churn.flow" / "flow.yaml").read_text())[
        "order"
    ]

    assert anchored.exit_code == 0, anchored.output
    assert len(order) == 2
    assert 'consumes = {"summary": "score.summary"}' in source
    assert "def materialize(self, ctx, summary):" in source
    assert "from __future__ import annotations" in source
    assert "_check: CellProtocol = Report()" in source
    assert "score.summary → report (summary)" in wired.output


def test_cells_new_all_outputs_keeps_the_previous_downstream_wiring(
    cli: Invoke, workspace: Path
) -> None:
    cli("init", "churn")
    write_cell(
        workspace / "churn.flow",
        "train",
        """
class Train:
    produces = {"model": "model", "run": "experiment"}
""",
    )
    cli("cells", "list")

    added = cli("cells", "new", "report", "--after", "train", "--all-outputs")
    assert added.exit_code == 0, added.output
    source = (workspace / "churn.flow" / "cells" / "report.py").read_text("utf-8")
    assert 'consumes = {"model": "train.model", "run": "train.run"}' in source
    assert "def materialize(self, ctx, model, run):" in source


def test_cells_move_places_a_cell_beside_its_neighbour(
    cli: Invoke, workspace: Path
) -> None:
    cli("init", "churn")
    cli("cells", "new", "first")
    cli("cells", "new", "last")
    cli("cells", "new", "moved")

    moved = cli("cells", "move", "moved", "--before", "last", "--json")
    listed = cli("cells", "list", "--json")

    assert moved.exit_code == 0, moved.output
    payload = json.loads(moved.output)
    by_slug = {cell["slug"]: cell for cell in json.loads(listed.output)["cells"]}
    assert payload["slug"] == "moved"
    assert payload["uid"]
    assert (
        Decimal(str(by_slug["first"]["order"]))
        < Decimal(payload["order"])
        < Decimal(str(by_slug["last"]["order"]))
    )
    assert payload["order"] == by_slug["moved"]["order"]


def test_sliced_queries_answer_the_narrow_question(cli: Invoke, workspace: Path):
    """`--stale` and `--around` are what keep a big flow answerable."""
    cli("init", "churn")
    flow = workspace / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)
    write_cell(flow, "fanout", FANOUT_CELL)
    cli("run", "score")

    stale = cli("cells", "list", "--stale")
    near = cli("graph", "--around", "report", "--depth", "1")

    assert "score" not in stale.output.replace("score.summary", "")
    assert "report" in stale.output and "fanout" in stale.output
    # One hop from `report` is `score`; `fanout` hangs off `score` two hops away.
    assert "fanout" not in near.output
    assert "report" in near.output and "score" in near.output
    _no_internals(stale)
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
    cli("lane", "new", "sweep", "-m", "try a higher score")
    cli("lane", "use", "sweep")
    write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.95"))
    cli("run", "report")

    compared = cli("diff", "main", "sweep")
    too_many = cli("diff", "main")

    edited = compared.output.index("edited on one side")
    results = compared.output.index("same code, different results")
    assert compared.output.index("score", edited) < results
    assert compared.output.index("report", results) > results
    assert too_many.exit_code == 1
    _no_internals(compared)


def test_asset_diff_is_not_a_command(cli: Invoke) -> None:
    removed = cli("asset", "diff", "report", "--lane", "main", "--lane", "sweep")

    assert removed.exit_code == 2
    assert "No such command 'diff'" in removed.output


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


def test_run_without_a_target_runs_the_lane_and_reports_when_it_is_current(
    cli: Invoke, workspace: Path
) -> None:
    cli("init", "churn")
    flow = workspace / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)

    ran = cli("run")
    current = cli("run")
    write_cell(flow, "broken", BROKEN_CELL)
    write_cell(flow, "other_broken", BROKEN_CELL)
    failed = cli("run")

    assert ran.exit_code == 0, ran.output
    assert "`score`" in ran.output and "`report`" in ran.output
    assert current.exit_code == 0, current.output
    assert "nothing to do. every leaf is current" in current.output
    assert failed.exit_code == 1
    assert "failed  `broken`" in failed.output
    assert "failed  `other_broken`" in failed.output


def test_run_without_a_target_exits_one_when_a_leaf_cannot_be_planned(
    cli: Invoke, workspace: Path
) -> None:
    cli("init", "churn")
    write_cell(
        workspace / "churn.flow",
        "dangling",
        """
        class Dangling:
            consumes = {"value": "missing.value"}
            produces = {"result": "asset"}

            def materialize(self, ctx, value):
                return {"result": value}
        """,
    )

    failed = cli("run")

    assert failed.exit_code == 1
    assert "could not plan `dangling`" in failed.output
    assert "missing.value" in failed.output


def test_run_stops_only_the_daemon_it_started(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    monkeypatch.chdir(root)
    runner = CliRunner()

    stopped = runner.invoke(app, ["run"])

    assert stopped.exit_code == 0, stopped.output
    assert daemon_workspace.read_record() is None
    assert not daemon_workspace.lock_held()

    refused = runner.invoke(app, ["run", "missing"])
    assert refused.exit_code == 1
    assert daemon_workspace.read_record() is None
    assert not daemon_workspace.lock_held()

    kept = runner.invoke(app, ["run", "--keep-daemon"])
    record = _answering_daemon()
    reused = runner.invoke(app, ["run"])

    assert kept.exit_code == 0, kept.output
    assert reused.exit_code == 0, reused.output
    assert daemon_workspace.read_record() == record
    assert client.is_alive(record)


def test_agent_begin_leaves_its_started_daemon_for_agent_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project")
    monkeypatch.chdir(root)
    runner = CliRunner()

    begun = runner.invoke(app, ["agent", "begin", "--label", "codex"])
    record = _answering_daemon()
    ended = runner.invoke(app, ["agent", "end", "--actor", "codex"])

    assert begun.exit_code == 0, begun.output
    assert ended.exit_code == 0, ended.output
    assert daemon_workspace.read_record() == record
    assert client.is_alive(record)


@pytest.mark.parametrize(
    ("attachment", "fails", "expected"),
    [
        ("lease", False, "leased agent session"),
        ("stream", True, "stream subscriber"),
        ("flow", False, "other open flow"),
    ],
)
def test_run_leaves_its_daemon_when_an_attachment_arrives(
    tmp_path: Path,
    servers: Reap,
    attachment: str,
    fails: bool,
    expected: str,
) -> None:
    root = make_workspace(tmp_path / "project", flows=("churn", "other"))
    flow = root / "churn.flow"
    ending = (
        'raise RuntimeError("pipeline failed")'
        if fails
        else 'return {"summary": {"auc": 0.91}}'
    )
    write_cell(
        flow,
        "gated",
        f"""
        class Gated:
            produces = {{"summary": "asset"}}

            def materialize(self, ctx):
                import time

                while not (ctx.workspace_dir / "go").exists():
                    time.sleep(0.05)
                {ending}
        """,
    )
    running = subprocess.Popen(
        [sys.executable, "-m", "lumlflow.cli", "run", "--flow", "churn"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    servers(running)
    record = _answering_daemon()
    try:
        with contextlib.ExitStack() as stack:
            paired = None
            opener = None
            stream = None
            _wait_for_running(record)
            if attachment == "lease":
                paired = stack.enter_context(client.attach(record))
                paired.call(
                    "agent.begin",
                    {
                        "flow": str(flow),
                        "actor": "codex",
                        "label": "Codex",
                        "lease": True,
                    },
                )
            elif attachment == "stream":
                stream = stack.enter_context(
                    websockets.sync.client.connect(
                        f"ws://127.0.0.1:{record.web_port}{web.STREAM_PATH}"
                        f"?token={record.token}",
                        open_timeout=30,
                    )
                )
                stream.send(json.dumps({"subscribe": "journal", "flow": str(flow)}))
                _receive_caught_up(stream)
            else:
                opener = stack.enter_context(client.attach(record))
                opener.call(
                    "flow.open",
                    {"flow": str(root / "other.flow"), "worktree": False},
                )

            (root / "go").touch()
            output, errors = running.communicate(timeout=90)

            assert running.returncode == (1 if fails else 0), errors
            assert "left the daemon running" in output
            assert expected in output
            assert client.is_alive(record)
            if paired is not None:
                ended = paired.call("agent.end", {"flow": str(flow), "actor": "codex"})
                assert ended["actor"] == "codex"
            elif stream is not None:
                stream.send(json.dumps({"subscribe": "journal", "flow": str(flow)}))
                _receive_caught_up(stream)
            else:
                assert opener is not None
                opened = opener.call(
                    "flow.open",
                    {"flow": str(root / "other.flow"), "worktree": False},
                )
                assert opened["path"] == str(root / "other.flow")
    finally:
        (root / "go").touch()

    assert client.is_alive(record)


@pytest.mark.parametrize(
    "command",
    [
        ("cells", "delete", "score", "--force"),
        ("import", "carried.py", "--force"),
        ("rename", "score", "headline", "--force"),
        ("rewind", "1", "--force"),
        ("lane", "use", "sweep", "--force"),
    ],
)
def test_lock_only_force_options_are_unknown(
    cli: Invoke, command: tuple[str, ...]
) -> None:
    refused = cli(*command)

    assert refused.exit_code == 2
    assert "No such option: --force" in refused.output


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


def test_starting_from_another_lane_says_which_one_it_started_from(
    cli: Invoke, workspace: Path
):
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)
    cli("lane", "new", "alpha")

    forked = cli("lane", "new", "beta", "--from", "alpha", "--json")
    printed = cli("lane", "new", "gamma", "--from", "alpha")
    shown = cli("lane", "list")

    assert json.loads(forked.output)["from_branch"] == "alpha"
    assert "started `gamma` from `alpha`" in printed.output
    assert "beta" in shown.output and "started from alpha" in shown.output


def test_starting_a_lane_and_listing_it_quote_the_same_parent_step(
    cli: Invoke, workspace: Path
) -> None:
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)
    before = json.loads(cli("lane", "list", "--json").output)
    main = next(branch for branch in before["branches"] if branch["branch"] == "main")
    parent_step = main["last_intent"]["step"]

    started = cli("lane", "new", "sweep")
    listed = cli("lane", "list")
    payload = json.loads(cli("lane", "list", "--json").output)
    sweep = next(
        branch for branch in payload["branches"] if branch["branch"] == "sweep"
    )

    assert f"started `sweep` from `main` at step {parent_step}" in started.output
    assert f"started from main at step {parent_step}" in listed.output
    assert "a root lane" in listed.output
    assert sweep["parent_step"] == parent_step
    assert sweep["forked_at_step"] > parent_step


def test_checkpoint_marks_the_lane_on_disk(cli: Invoke, workspace: Path) -> None:
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)

    newest = json.loads(cli("context", "--json").output)["recent"][0]["step"]

    marked = cli("checkpoint", "-m", "the one that scored")
    match = re.search(
        r"marked `main` at step (\d+) · the one that scored", marked.output
    )
    context = json.loads(cli("context", "--json").output)

    assert marked.exit_code == 0, marked.output
    assert match is not None
    # The words land on the newest step; marking adds none.
    assert int(match.group(1)) == newest
    assert context["recent"][0]["step"] == newest
    assert context["checkpoint"]["step"] == newest
    assert context["checkpoint"]["mark"] == "the one that scored"
    assert "the one that scored" in cli("context").output
    _no_internals(marked)


def test_checkpoint_marks_a_named_step(cli: Invoke, workspace: Path) -> None:
    flow = workspace / "churn.flow"
    cli("init", "churn")
    write_cell(flow, "score", SCORE_CELL)
    earlier = json.loads(cli("context", "--json").output)["recent"][0]["step"]
    write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.77"))
    cli("status")

    marked = cli("checkpoint", "--step", str(earlier), "-m", "the original")
    context = json.loads(cli("context", "--json").output)

    assert marked.exit_code == 0, marked.output
    assert f"marked `main` at step {earlier} · the original" in marked.output
    assert context["checkpoint"]["step"] == earlier
    assert context["recent"][0]["step"] > earlier

    refused = cli("checkpoint", "--step", "10000", "-m", "x")
    assert refused.exit_code == 1
    assert "not on main" in refused.output
    assert "Traceback" not in refused.output


def test_checkpoint_marks_another_lane(cli: Invoke) -> None:
    cli("init", "churn")
    cli("lane", "new", "sweep")

    marked = cli("checkpoint", "--lane", "sweep", "-m", "baseline")
    match = re.search(r"marked `sweep` at step (\d+) · baseline", marked.output)
    tree = json.loads(cli("lane", "list", "--json").output)
    by_name = {branch["branch"]: branch for branch in tree["branches"]}

    assert marked.exit_code == 0, marked.output
    assert match is not None
    assert by_name["sweep"]["checkpoint"] == int(match.group(1))
    assert by_name["main"]["checkpoint"] != int(match.group(1))


def test_checkpoint_requires_an_intent_without_writing(cli: Invoke) -> None:
    cli("init", "churn")
    before = json.loads(cli("context", "--json").output)["recent"]

    refused = cli("checkpoint")
    after = json.loads(cli("context", "--json").output)["recent"]

    assert refused.exit_code == 2
    assert "--intent" in refused.output
    assert after == before


def test_checkpoint_passes_a_blank_intent_to_the_daemon(cli: Invoke) -> None:
    cli("init", "churn")

    refused = cli("checkpoint", "-m", "   ")

    assert refused.exit_code == 1
    assert "a checkpoint needs a one-line intent" in refused.output


def test_checkpoint_refuses_an_unknown_lane_without_writing(cli: Invoke) -> None:
    cli("init", "churn")
    before = json.loads(cli("context", "--json").output)["recent"]

    refused = cli("checkpoint", "--lane", "nowhere", "-m", "x")
    after = json.loads(cli("context", "--json").output)["recent"]

    assert refused.exit_code == 1
    assert "no lane named nowhere" in refused.output
    assert "Traceback" not in refused.output
    assert after == before


def test_checkpoint_returns_json(cli: Invoke) -> None:
    cli("init", "churn")

    marked = cli("checkpoint", "-m", "baseline", "--json")
    payload = json.loads(marked.output)

    assert marked.exit_code == 0, marked.output
    assert set(payload) == {"branch", "step", "intent", "ts", "settled"}
    assert payload["branch"] == "main"
    assert payload["intent"] == "baseline"


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
    context_json = json.loads(cli("context", "--json").output)
    context_text = cli("context")

    assert rewound.exit_code == 0
    assert f"is back at step {at}" in rewound.output
    assert "0.91" in source_of(flow, "score")
    # Synced, not queued: the run that step referenced is still the baseline, so
    # the rewind cost a selection write and no execution.
    states = [entry["state"] for entry in json.loads(listed.output)["cells"]]
    assert states == ["synced"]
    # The rewind is not a step of the lane: the history still tops out at the
    # edit, the lane stands at the step it was moved to, and the brief says so.
    newest = context_json["recent"][0]["step"]
    assert newest > at
    assert context_json["position"] == {"step": at, "newest": newest}
    assert f"at step {at} · behind its newest step {newest}" in context_text.output
    rewrite = context_json["last_cells_rewrite"]
    assert rewrite["verb"] == "rewind" and rewrite["lane"] == "main"
    assert rewrite["step"] > newest
    assert (
        f"last `cells/` rewrite: rewind · `main` · step {rewrite['step']}"
    ) in context_text.output
    assert context_text.output.rstrip().endswith("full agent guide: `lumlflow guide`")
    _no_internals(rewound)


def test_a_change_after_a_rewind_moves_the_lane_on_from_there(
    cli: Invoke, workspace: Path
):
    flow = workspace / "churn.flow"
    cli("init", "churn")
    write_cell(flow, "score", SCORE_CELL)
    at = json.loads(cli("context", "--json").output)["recent"][0]["step"]
    write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.77"))
    cli("status")
    cli("rewind", str(at))
    behind = json.loads(cli("context", "--json").output)["position"]

    write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.85"))
    cli("status")
    moved = json.loads(cli("context", "--json").output)

    assert behind["step"] == at and behind["newest"] > at
    assert moved["position"]["step"] == moved["position"]["newest"]
    assert moved["position"]["step"] > behind["newest"]
    assert "behind its newest step" not in cli("context").output


def test_adopt_takes_the_winner_and_never_overwrites_a_side_silently(
    cli: Invoke, workspace: Path
):
    """The whole v1 merge story: one asset, picked per branch. A cell both
    sides moved since the fork is a conflict, not a last-write-wins."""
    flow = workspace / "churn.flow"
    cli("init", "churn")
    write_cell(flow, "score", SCORE_CELL)
    cli("run", "score")
    cli("lane", "new", "sweep")
    cli("lane", "use", "sweep")
    write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.95"))
    cli("status")
    cli("lane", "use", "main")

    adopted = cli("adopt", "score", "--from", "sweep", "-m", "the sweep won")
    took = source_of(flow, "score")
    # Now main moves too, so the next adopt has two sides that both edited.
    write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.42"))
    cli("status")
    cli("lane", "use", "sweep")
    write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.96"))
    cli("status")
    cli("lane", "use", "main")
    refused = cli("adopt", "score", "--from", "sweep", stdin="")
    forced = cli("adopt", "score", "--from", "sweep", "--force")

    assert adopted.exit_code == 0
    assert "0.95" in took
    assert refused.exit_code == 1
    assert "pick a side" in refused.output
    assert forced.exit_code == 0
    assert "0.96" in source_of(flow, "score")
    _no_internals(adopted)
    _no_internals(refused)
    _no_internals(forced)


def test_a_brief_on_another_branch_does_not_claim_the_agents_files(
    cli: Invoke, workspace: Path
):
    """A registration is shown only on the lane whose files are checked out."""
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)
    cli("lane", "new", "alpha")
    cli("agent", "begin", "--label", "claude-1")

    here = cli("context", "--json")
    there = cli("context", "--lane", "alpha", "--json")
    printed = cli("context", "--lane", "alpha")

    assert json.loads(here.output)["checked_out"] is True
    assert json.loads(here.output)["agent"] == "claude-1"
    assert json.loads(there.output)["checked_out"] is False
    assert json.loads(there.output)["agent"] is None
    assert "(not on disk)" in printed.output
    # The session still shows up in the history, which is true; what it must
    # not do is claim to be working in a branch nobody checked out.
    assert "is working here" not in printed.output


def test_deleting_a_cell_is_per_branch_and_says_so(cli: Invoke, workspace: Path):
    flow = workspace / "churn.flow"
    cli("init", "churn")
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)
    cli("cells", "list")
    cli("lane", "new", "sweep")

    deleted = cli("cells", "delete", "score", "-m", "not needed here")
    here = cli("cells", "list")
    there = cli("cells", "list", "--lane", "sweep")

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


def test_lumlflow_actor_owns_a_reconcile_triggered_by_a_verb(
    cli: Invoke,
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flow = workspace / "churn.flow"
    cli("init", "churn")
    write_cell(flow, "score", SCORE_CELL)
    cli("cells", "list")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("LUMLFLOW_ACTOR", "codex-2")
    write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.93"))

    shown = cli("cells", "show", "score", "--json")

    assert json.loads(shown.output)["provenance"]["last_edited_by"] == "codex-2"


def test_a_bare_verb_uses_the_harness_marker_without_registering_a_session(
    cli: Invoke,
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flow = workspace / "churn.flow"
    cli("init", "churn")
    write_cell(flow, "score", SCORE_CELL)
    cli("cells", "list")
    for marker in ("CLAUDECODE", "CURSOR_AGENT", "GEMINI_CLI"):
        monkeypatch.delenv(marker, raising=False)
    monkeypatch.delenv("LUMLFLOW_ACTOR", raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")

    edited = cli(
        "cells",
        "edit",
        "score",
        "-m",
        "raise score",
        stdin=SCORE_CELL.replace("0.91", "0.93"),
    )
    shown = json.loads(cli("cells", "show", "score", "--json").output)
    context_json = json.loads(cli("context", "--json").output)

    assert edited.exit_code == 0, edited.output
    assert shown["provenance"]["last_edited_by"] == "claude-code"
    assert context_json["recent"][0]["actor"] == "claude-code"
    assert context_json["agent"] is None
    assert (flow / "cells" / "score.py").exists()


def test_a_working_agent_does_not_block_switching_the_files(
    cli: Invoke, workspace: Path
):
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)
    cli("lane", "new", "sweep")
    cli("agent", "begin", "--label", "claude-1")

    switched = cli("lane", "use", "sweep")
    seen = cli("lane", "list")

    assert switched.exit_code == 0
    assert "claude-1 is working here" in seen.output
    _no_internals(switched)


def test_an_output_with_no_bytes_says_what_to_do_about_it(cli: Invoke, workspace: Path):
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)

    early = cli("asset", "download", "score", "--json")

    assert early.exit_code == 1
    answered = json.loads(early.output)
    assert answered["kind"] == "ValueNotStored"
    assert "run `score` first" in answered["error"]


def test_asset_download_refuses_to_overwrite_unless_forced(
    cli: Invoke, workspace: Path
) -> None:
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)
    ran = cli("run", "score")
    destination = workspace / "train.model"
    destination.write_bytes(b"keep me")

    refused = cli("asset", "download", "score.summary", "--to", "./train.model")
    held = destination.read_bytes()
    forced = cli(
        "asset",
        "download",
        "score.summary",
        "--to",
        "./train.model",
        "--force",
    )

    assert ran.exit_code == 0
    assert refused.exit_code == 1
    assert str(destination) in refused.output
    assert "already exists" in refused.output
    assert held == b"keep me"
    assert forced.exit_code == 0
    assert destination.read_bytes() != b"keep me"
    _no_internals(refused)
    _no_internals(forced)


def test_promote_is_not_a_command(cli: Invoke) -> None:
    removed = cli("promote")

    assert removed.exit_code == 2
    assert "No such command 'promote'" in removed.output


def test_secrets_and_package_writes_are_not_commands(cli: Invoke) -> None:
    secret = cli("secrets")
    added = cli("env", "add", "lightgbm")
    removed = cli("env", "remove", "pandas")

    assert secret.exit_code == 2
    assert "No such command 'secrets'" in secret.output
    for result, command in ((added, "add"), (removed, "remove")):
        assert result.exit_code == 2
        assert f"No such command '{command}'" in result.output


def test_env_status_stays_read_only(cli: Invoke, workspace: Path) -> None:
    write_lock(workspace, {"pandas": "2.2.0"})

    listed = cli("env", "status")
    help_page = cli("env", "--help")

    assert "pandas 2.2.0" in listed.output
    assert "status" in help_page.output
    assert "add" not in help_page.output
    assert "remove" not in help_page.output
    _no_internals(listed)


def test_an_agent_session_brackets_the_command_it_runs(cli: Invoke, workspace: Path):
    cli("init", "churn")

    argv = ("agent", "exec", "--label", "claude-1", "--", sys.executable, "-c", "pass")
    session = cli(*argv)
    tree = cli("lane", "list")

    assert session.exit_code == 0
    # The session ended, so no agent remains registered.
    assert "is working here" not in tree.output


def test_agent_session_help_describes_attribution_not_file_ownership(
    cli: Invoke,
) -> None:
    begun = cli("agent", "begin", "--help")
    ended = cli("agent", "end", "--help")

    assert "session for attribution" in begun.output
    assert "agent attribution session" in ended.output
    assert "owns the flow's files" not in begun.output
    assert "releasing the files" not in ended.output


def test_root_is_gone_and_daemon_status_answers_without_a_flow(
    cli: Invoke, workspace: Path
) -> None:
    where = cli("root")
    daemon = cli("daemon", "status")

    assert where.exit_code != 0
    assert "No such command 'root'" in where.output
    assert "daemon is not running" in daemon.output


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


def test_gc_reports_reclaimed_bytes(cli: Invoke, workspace: Path) -> None:
    cli("init", "churn")
    values = Cas(workspace / "churn.flow" / ".lumlflow" / "values")
    first = values.put(b"first orphan")

    shown = cli("gc")

    second = values.put(b"second orphan")
    encoded = cli("gc", "--json")
    payload = json.loads(encoded.output)

    assert shown.exit_code == 0, shown.output
    assert f"{len(b'first orphan')} bytes reclaimed" in shown.output
    assert encoded.exit_code == 0, encoded.output
    assert payload["freed_bytes"] == len(b"second orphan")
    assert payload["collected"] == 1
    assert not values.exists(first)
    assert not values.exists(second)
    _no_internals(shown)


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


def test_an_edit_reaches_the_files_while_an_agent_is_registered(
    cli: Invoke, workspace: Path
) -> None:
    flow = workspace / "churn.flow"
    cli("init", "churn")
    write_cell(flow, "score", SCORE_CELL)
    cli("agent", "begin", "--label", "claude-1")

    edited = cli("cells", "edit", "score", stdin=SCORE_CELL.replace("0.91", "0.77"))
    status = cli("status")

    assert edited.exit_code == 0
    assert "0.77" in source_of(flow, "score")
    assert "not yet written" not in status.output
    _no_internals(status)


def test_an_off_disk_edit_says_the_checked_out_files_are_unchanged(
    cli: Invoke, workspace: Path
) -> None:
    flow = workspace / "churn.flow"
    cli("init", "churn")
    write_cell(flow, "score", SCORE_CELL)
    cli("lane", "new", "sweep")

    edited = cli(
        "cells",
        "edit",
        "score",
        "--lane",
        "sweep",
        stdin=SCORE_CELL.replace("0.91", "0.77"),
    )

    assert edited.exit_code == 0
    assert "cells/ unchanged" in edited.output
    assert "not yet written" not in edited.output
    assert "0.91" in source_of(flow, "score")


def test_an_intent_typed_at_a_verb_is_what_the_history_reads_back(
    cli: Invoke, workspace: Path
):
    """`-m` is the whole reason a journal is worth reading twice."""
    cli("init", "churn")
    write_cell(workspace / "churn.flow", "score", SCORE_CELL)

    cli("lane", "new", "sweep", "-m", "try it with the wider window")
    read_back = cli("lane", "list")

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


def _answering_daemon(timeout: float = 30.0) -> DaemonRecord:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        record = daemon_workspace.read_record()
        if record is not None and client.is_alive(record):
            return record
        time.sleep(0.05)
    raise AssertionError("the daemon did not start")


def _wait_for_running(record: DaemonRecord, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with client.attach(record) as live:
            if live.call("ping")["running"]:
                return
        time.sleep(0.05)
    raise AssertionError("the pipeline did not start")


def _receive_caught_up(
    stream: "websockets.sync.client.ClientConnection", timeout: float = 30.0
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        frame = json.loads(stream.recv(timeout=timeout))
        if frame.get("type") == "caught_up":
            return
    raise AssertionError("the stream did not catch up")


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


def test_the_lane_group_holds_the_lane_verbs(cli: Invoke):
    cli("init", "churn")
    started = cli("lane", "new", "sweep", "-m", "a lower lr")
    listed = cli("lane", "list")
    used = cli("lane", "use", "sweep")
    archived = cli("lane", "archive", "sweep")

    assert "started `sweep` from `main`" in started.output
    assert "sweep" in listed.output and "started from main" in listed.output
    assert "on `sweep`" in used.output
    assert "archived `sweep`" in archived.output


@pytest.mark.parametrize(
    "command",
    [
        ("fork", "sweep"),
        ("switch", "sweep"),
        ("tree",),
        ("archive", "sweep"),
        ("variant", "list"),
    ],
)
def test_retired_commands_are_unknown(cli: Invoke, command: tuple[str, ...]) -> None:
    removed = cli(*command)

    assert removed.exit_code == 2
    assert f"No such command '{command[0]}'" in removed.output


def test_retired_option_spellings_are_unknown(cli: Invoke):
    cli("init", "churn")
    cli("lane", "new", "sweep", "-m", "a lower lr")

    by_lane = cli("context", "--lane", "sweep")
    by_variant = cli("context", "--variant", "sweep")
    by_branch = cli("context", "--branch", "sweep")
    stale = cli("cells", "list", "--stale")
    unsynced = cli("cells", "list", "--unsynced")

    assert by_lane.exit_code == 0
    assert "sweep" in by_lane.output
    assert stale.exit_code == 0
    for removed in (by_variant, by_branch, unsynced):
        assert removed.exit_code == 2
        assert "No such option" in removed.output


def test_no_visible_help_speaks_the_vocabulary_git_owns():
    """A flow lives inside a git repository, so its verbs must not sound alike."""
    runner = CliRunner()
    for path in _visible_paths():
        result = runner.invoke(app, [*path, "--help"])
        assert result.exit_code == 0, f"`{' '.join(path)} --help` failed"
        no_git_words(result.output, f"`lumlflow {' '.join(path)} --help`")


def test_ui_help_warns_about_an_unauthenticated_tracker_on_non_loopback() -> None:
    result = CliRunner().invoke(app, ["ui", "--help"])

    assert result.exit_code == 0, result.output
    for phrase in ("tracker API", "unauthenticated", "non-loopback bind"):
        assert phrase in result.output


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
        ("checkpoint", "-m", "worth keeping"),
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
