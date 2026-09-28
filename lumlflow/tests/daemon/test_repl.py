"""`eval` through the daemon: a branch's values, addressed by name.

The whole path runs here — the API resolves the branch, names its stored
outputs, and a real kernel process evaluates against them. What the daemon owes
this surface is what the store owes it: viewing a branch is a read, so a branch
nobody checked out evaluates like any other, and nothing an expression does
reaches the journal.
"""

from pathlib import Path

from tests.daemon.helpers import (
    SCORE_CELL,
    daemon_api,
    make_workspace,
    transactions,
    values_in,
    write_cell,
)

FANOUT_CELL = """
class Fanout:
    \"\"\"Two outputs, one of them the one a reader came for.\"\"\"
    produces = {"curves": "experiment", "config": "asset"}

    def materialize(self, ctx):
        ctx.tracker.log_metric("auc", 0.91)
        return {"curves": ctx.tracker.record, "config": {"lr": 0.1}}
"""


async def test_eval_reads_a_branch_nobody_checked_out_and_records_nothing(
    tmp_path: Path,
):
    """A fork inherits the values it was pinned to, and reading them is free.

    No checkout, no version, no materialization, no journal line: the REPL is a
    read of what the branch already observed.
    """
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"target": "score"})
        await api.fork({"name": "sweep"})
        session = api.hub.session("churn")
        before, stored = len(transactions(session)), values_in(root / "churn.flow")

        answered = await api.eval({"code": "score['auc']", "branch": "sweep"})

        after = len(transactions(session))

    assert answered["branch"] == "sweep"
    assert answered["repr"] == "0.91"
    assert answered["error"] is None
    assert after == before
    assert values_in(root / "churn.flow") == stored


async def test_a_mutation_on_one_branch_is_not_there_on_another(tmp_path: Path):
    """The scenario's last clause: other branches see nothing.

    A fork shares its parent's values, so both branches resolve `score` to the
    same bytes and the same entry in the kernel's hot cache. Handing out the
    cached object rather than a copy is exactly how scratch code typed on the
    fork would turn up on `main`.
    """
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"target": "score"})
        await api.fork({"name": "sweep"})

        mutated = await api.eval(
            {"code": "score.clear(); len(score)", "branch": "sweep"}
        )
        elsewhere = await api.eval({"code": "len(score)", "branch": "main"})

    assert mutated["repr"] == "0"
    assert elsewhere["repr"] == "1"


async def test_a_cell_is_in_scope_by_name_and_every_output_by_its_own(
    tmp_path: Path,
):
    """`fanout` is the output its card opens on; the others are `cell_output`."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "fanout", FANOUT_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"target": "fanout"})

        answered = await api.eval(
            {
                "code": (
                    "[fanout.snapshot['metrics'], "
                    "fanout_curves.snapshot['metrics'], fanout_config]"
                )
            }
        )

    assert answered["repr"] == "[{'auc': 0.91}, {'auc': 0.91}, {'lr': 0.1}]"
    assert answered["names"] == ["fanout", "fanout_config", "fanout_curves"]


async def test_an_output_nothing_has_run_is_not_a_name(tmp_path: Path):
    """Unmaterialized is a state, not an empty value: the name is simply absent."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})

        answered = await api.eval({"code": "score"})

    assert answered["names"] == []
    assert answered["error"]["type"] == "NameError"
