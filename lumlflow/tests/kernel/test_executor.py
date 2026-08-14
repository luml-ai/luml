"""What one run is allowed to touch, and what it leaves behind as facts.

The executor's contract is mostly about isolation: a run gets a scratch cwd it
loses, a namespace nobody else shares, no stdin, and an environment that is put
back. What survives it is exactly the declared outputs and a record of what the
cell reached for.
"""

from __future__ import annotations

import json
import os
import pickle
import threading
import time
from pathlib import Path

import pytest

from lumlflow_kernel.executor import NON_INTERACTIVE_HINT
from tests.kernel.helpers import (
    FakeLink,
    make_kernel,
    run,
    store_blobs,
    stored_log,
    stored_preview,
    stored_value,
)

DEADLINE_S = 20.0


def test_a_declared_path_moves_into_the_store_and_scratch_does_not_survive(tmp_path):
    kernel, _ = make_kernel(tmp_path)
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            from pathlib import Path
            Path("checkpoints").mkdir()
            weights = Path("checkpoints/epoch3.pt")
            weights.write_bytes(b"weights")
            return {"checkpoint": weights}
        """,
        produces={"checkpoint": "asset"},
    )

    assert record["state"] == "succeeded"
    assert record["outputs"]["checkpoint"]["kind"] == "file"
    assert stored_value(kernel, record, "checkpoint") == b"weights"
    scratch = kernel.flow_dir / ".lumlflow" / "kernel" / "scratch"
    assert list(scratch.iterdir()) == []


def test_the_next_run_cannot_see_what_the_last_one_wrote_beside_its_outputs(tmp_path):
    kernel, _ = make_kernel(tmp_path)
    run(
        kernel,
        """
        def materialize(self, ctx):
            from pathlib import Path
            Path("checkpoints").mkdir()
            Path("checkpoints/epoch3.pt").write_bytes(b"weights")
            return {}
        """,
        run_id="first",
    )
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            from pathlib import Path
            return {"seen": " ".join(sorted(p.name for p in Path(".").iterdir()))}
        """,
        run_id="second",
        produces={"seen": "asset"},
    )

    assert stored_value(kernel, record, "seen") == b""


def test_a_path_the_cell_did_not_create_under_scratch_is_copied_not_eaten(tmp_path):
    kernel, _ = make_kernel(tmp_path, files={"data/raw.csv": "a,b\n1,2\n"})
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            return {"source": ctx.workspace_dir / "data" / "raw.csv"}
        """,
        produces={"source": "asset"},
    )

    assert record["state"] == "succeeded"
    assert (kernel.workspace_dir / "data" / "raw.csv").read_text() == "a,b\n1,2\n"
    assert stored_value(kernel, record, "source") == b"a,b\n1,2\n"


def test_reaching_into_the_workspace_marks_the_run_external(tmp_path):
    kernel, link = make_kernel(tmp_path, files={"data/raw.csv": "a,b\n1,2\n"})
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            return {"text": (ctx.workspace_dir / "data" / "raw.csv").read_text()}
        """,
        produces={"text": "asset"},
    )

    assert record["external"] is True
    assert record["identity_dependent"] is False
    assert link.named("external_access")


def test_reading_the_branch_makes_the_run_identity_dependent(tmp_path):
    kernel, link = make_kernel(tmp_path)
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            return {"where": f"ran on {ctx.branch} at step {ctx.step}"}
        """,
        produces={"where": "asset"},
        ctx_info={"branch": "exp/lr-sweep", "step": 12},
    )

    assert record["identity_dependent"] is True
    assert record["external"] is False
    assert stored_value(kernel, record, "where") == b"ran on exp/lr-sweep at step 12"
    assert link.named("identity_access")


def test_a_secret_reaches_the_cell_and_nothing_the_store_keeps(tmp_path):
    secret = "sk-live-DEADBEEF"
    kernel, link = make_kernel(tmp_path, link=FakeLink(secrets={"API_KEY": secret}))
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            key = ctx.secret("API_KEY")
            print("using a key of", len(key), "characters")
            return {"length": {"characters": len(key)}}
        """,
        produces={"length": "asset"},
    )

    assert record["state"] == "succeeded"
    assert link.requests == [("secret_get", {"name": "API_KEY"})]
    assert secret.encode() not in b"".join(store_blobs(kernel))
    assert secret not in json.dumps(link.events)
    assert secret not in json.dumps(record)
    assert b"16 characters" in stored_log(kernel, record)


def test_asking_for_input_fails_at_once_with_the_prompt_above_the_hint(tmp_path):
    kernel, _ = make_kernel(tmp_path)
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            return {"answer": input("continue?")}
        """,
        produces={"answer": "asset"},
    )

    assert record["state"] == "failed"
    assert record["error"]["type"] == "EOFError"
    assert record["error"]["hint"] == NON_INTERACTIVE_HINT
    assert b"continue?" in stored_log(kernel, record)


def test_a_raising_cell_is_recorded_with_its_own_traceback(tmp_path):
    kernel, link = make_kernel(tmp_path)
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            raise ValueError("no training data")
        """,
        slug="train_model",
        produces={"model": "model"},
    )

    assert record["state"] == "failed"
    assert record["error"]["type"] == "ValueError"
    assert record["error"]["message"] == "no training data"
    traceback = record["error"]["traceback"]
    assert "<cell train_model>" in traceback
    assert 'raise ValueError("no training data")' in traceback
    # The author reads this. Kernel frames are not part of their bug.
    assert "executor.py" not in traceback
    assert link.names()[-1] == "failed"


def test_outputs_that_do_not_match_the_declaration_fail_in_words(tmp_path):
    kernel, _ = make_kernel(tmp_path)
    missing = run(
        kernel,
        """
        def materialize(self, ctx):
            return {"model": "m"}
        """,
        produces={"model": "model", "run": "experiment"},
    )
    extra = run(
        kernel,
        """
        def materialize(self, ctx):
            return {"model": "m", "notes": "n"}
        """,
        produces={"model": "model"},
    )
    bare = run(
        kernel,
        """
        def materialize(self, ctx):
            return "m"
        """,
        produces={"model": "model"},
    )

    assert "`run`" in missing["error"]["message"]
    assert "traceback" not in missing["error"]
    assert "`notes`" in extra["error"]["message"]
    assert "must return a dict" in bare["error"]["message"]


def test_an_unpersisted_output_keeps_a_preview_and_a_hash_nobody_can_reuse(tmp_path):
    kernel, _ = make_kernel(tmp_path)
    declaration = {"probe": {"type": "asset", "persist": False}}
    first = run(kernel, _RETURNS_NOTE, produces=declaration, run_id="first")
    second = run(kernel, _RETURNS_NOTE, produces=declaration, run_id="second")

    output = first["outputs"]["probe"]
    assert output["persisted"] is False
    assert output["value_ref"] is None
    assert stored_preview(kernel, first, "probe")["blocks"]
    # A per-materialization token, so a consumer never hits a cache it could
    # not read the bytes of.
    assert output["content_hash"] != second["outputs"]["probe"]["content_hash"]


def test_a_native_output_is_staged_exactly_like_an_inline_one(tmp_path):
    """`model`, `dataset` and `experiment` say what leaves the flow, not how it
    is kept: the bytes land in the local CAS either way, so a fork, a cold
    rerun and an offline consumer all read them without a network."""
    kernel, _ = make_kernel(tmp_path)

    record = run(
        kernel,
        """
        def materialize(self, ctx):
            ctx.tracker.log_params({"lr": 3e-4})
            ctx.tracker.log_metric("auc", 0.91)
            return {
                "model": "WEIGHTS",
                "data": "ROWS",
                "run": ctx.tracker.record,
                "notes": "read me",
            }
        """,
        produces={
            "model": "model",
            "data": "dataset",
            "run": "experiment",
            "notes": "asset",
        },
    )

    outputs = record["outputs"]
    assert record["state"] == "succeeded"
    assert all(outputs[name]["persisted"] for name in outputs)
    assert all(outputs[name]["value_ref"] for name in outputs)
    assert all(stored_value(kernel, record, name) for name in outputs)
    # The declared type never reaches the kind: what the value *is* is inferred
    # from the value, and the tracker's record is an experiment.
    assert outputs["run"]["kind"] == "experiment"
    assert stored_preview(kernel, record, "run")["blocks"] == [
        {"block": "markdown", "text": "**params**"},
        {"block": "kv", "entries": {"lr": 3e-4}},
        {"block": "markdown", "text": "**metrics**"},
        {"block": "kv", "entries": {"auc": 0.91}},
    ]


def test_inputs_arrive_under_their_declared_names(tmp_path):
    kernel, _ = make_kernel(tmp_path)
    produced = run(
        kernel,
        """
        def materialize(self, ctx):
            return {"train": "TRAIN ROWS", "test": "TEST ROWS"}
        """,
        run_id="producer",
        produces={"train": "asset", "test": "asset"},
    )
    record = run(
        kernel,
        """
        def materialize(self, ctx, train, test):
            return {"joined": f"{train} then {test}"}
        """,
        run_id="consumer",
        produces={"joined": "asset"},
        inputs={
            "train": _input(produced, "train"),
            "test": _input(produced, "test"),
        },
    )

    assert stored_value(kernel, record, "joined") == b"TRAIN ROWS then TEST ROWS"


def test_paranoid_mode_fails_the_run_that_changed_its_input_in_place(tmp_path):
    """The scenario: a cell mutates what it consumed, and the run says so.

    The failure names the cell and the input in words, and the value the next
    reader is handed is the one the producer stored — the CAS bytes were never
    touched, so dropping the object that moved is what restores it.
    """
    kernel, _ = make_kernel(tmp_path)
    rows = _produce_rows(kernel)

    record = run(
        kernel,
        """
        def materialize(self, ctx, rows):
            rows.append(4)
            return {"total": sum(rows)}
        """,
        slug="summarize",
        run_id="consumer",
        produces={"total": "asset"},
        inputs={"rows": rows},
        paranoid=True,
    )

    assert record["state"] == "failed"
    assert "`summarize`" in record["error"]["message"]
    assert "`rows`" in record["error"]["message"]
    assert record["outputs"] == {}
    assert _cached(kernel, rows) == [1, 2, 3]


def test_a_mutation_costs_nothing_until_paranoid_mode_is_asked_for(tmp_path):
    """The honest limit: in-process Python is not sandboxed from itself.

    Off — which is the default — the mutation lands on the cached value and the
    run succeeds. That is the hazard paranoid mode exists to measure, and the
    price of measuring it is why it is opt-in.
    """
    kernel, _ = make_kernel(tmp_path)
    rows = _produce_rows(kernel)

    record = run(
        kernel,
        """
        def materialize(self, ctx, rows):
            rows.append(4)
            return {"total": sum(rows)}
        """,
        run_id="consumer",
        produces={"total": "asset"},
        inputs={"rows": rows},
    )

    assert record["state"] == "succeeded"
    assert _cached(kernel, rows) == [1, 2, 3, 4]


def test_strict_mode_copies_the_values_another_branch_is_live_on(tmp_path):
    """Strict mode is per value, not per run: the daemon says which values two
    branches read, and only those cost a copy."""
    kernel, _ = make_kernel(tmp_path)
    shared = _produce_rows(kernel) | {"shared": True}
    private = _produce_rows(kernel, run_id="other", value=[9, 9])

    record = run(
        kernel,
        """
        def materialize(self, ctx, shared, private):
            shared.append(4)
            private.append(4)
            return {"total": sum(shared) + sum(private)}
        """,
        run_id="consumer",
        produces={"total": "asset"},
        inputs={"shared": shared, "private": private},
        strict=True,
    )

    assert record["state"] == "succeeded"
    assert _cached(kernel, shared) == [1, 2, 3]
    assert _cached(kernel, private) == [9, 9, 4]


def test_strict_and_paranoid_together_leave_a_shared_value_unremarked(tmp_path):
    """The copy is what makes the re-hash find nothing: a run that mutated only
    its own copy is a run that did nothing wrong."""
    kernel, _ = make_kernel(tmp_path)
    rows = _produce_rows(kernel) | {"shared": True}

    record = run(
        kernel,
        """
        def materialize(self, ctx, rows):
            rows.append(4)
            return {"total": sum(rows)}
        """,
        run_id="consumer",
        produces={"total": "asset"},
        inputs={"rows": rows},
        paranoid=True,
        strict=True,
    )

    assert record["state"] == "succeeded"
    # The cell saw its own copy grow, which is the whole point of handing it one.
    assert pickle.loads(stored_value(kernel, record, "total")) == 10
    assert _cached(kernel, rows) == [1, 2, 3]


def test_an_input_whose_value_is_not_stored_says_which_cell_to_run(tmp_path):
    kernel, _ = make_kernel(tmp_path)
    record = run(
        kernel,
        """
        def materialize(self, ctx, train):
            return {"out": train}
        """,
        slug="holdout_eval",
        produces={"out": "asset"},
        inputs={"train": {"value_ref": "0" * 64, "kind": "note"}},
    )

    assert record["state"] == "failed"
    assert "`train`" in record["error"]["message"]
    assert "run the cell that produces it" in record["error"]["message"]


def test_a_run_puts_back_the_environment_and_the_working_directory(tmp_path):
    kernel, _ = make_kernel(tmp_path)
    before = Path.cwd()
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            import os, tempfile
            os.environ["LUMLFLOW_TEST_LEAK"] = "1"
            os.chdir(tempfile.gettempdir())
            return {}
        """,
    )

    assert record["state"] == "succeeded"
    assert "LUMLFLOW_TEST_LEAK" not in os.environ
    assert Path.cwd() == before


def test_a_tempdir_belongs_to_the_run_and_goes_with_it(tmp_path):
    kernel, _ = make_kernel(tmp_path)
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            scratch = ctx.tempdir()
            (scratch / "work.txt").write_text("interim")
            return {"where": str(scratch)}
        """,
        produces={"where": "asset"},
    )

    assert not Path(stored_value(kernel, record, "where").decode()).exists()


def test_cancelling_the_run_in_flight_records_it_as_cancelled(tmp_path):
    kernel, _ = make_kernel(tmp_path)
    marker = tmp_path / "running"
    finished: list[dict] = []
    worker = threading.Thread(
        target=lambda: finished.append(
            run(
                kernel,
                _spins_until(marker, tmp_path / "never-arrives"),
                produces={"never": "asset"},
            )
        )
    )
    worker.start()
    try:
        _await(marker.exists)
        assert kernel.cancel({"run_id": "run1"}) == {"cancelled": True}
    finally:
        worker.join(timeout=DEADLINE_S)

    assert finished[0]["state"] == "cancelled"
    assert finished[0]["outputs"] == {}


def test_cancelling_a_run_that_is_not_in_flight_says_so(tmp_path):
    kernel, _ = make_kernel(tmp_path)

    assert kernel.cancel({"run_id": "nothing-running"}) == {"cancelled": False}


def test_a_cancel_arriving_after_the_cell_is_refused_and_the_record_survives(
    tmp_path, monkeypatch
):
    """A cancel is injected at the running thread's next bytecode, so it lands
    after the call that armed it. Once the cell has returned there is nothing
    left to interrupt, and one landing in the teardown would take the record
    the daemon is waiting for with it."""
    kernel, link = make_kernel(tmp_path)
    storing, release = threading.Event(), threading.Event()
    store_outputs = kernel.executor._store_outputs

    def blocks_until_released(*args):
        storing.set()
        release.wait(DEADLINE_S)
        return store_outputs(*args)

    monkeypatch.setattr(kernel.executor, "_store_outputs", blocks_until_released)
    finished: list[dict] = []
    worker = threading.Thread(
        target=lambda: finished.append(
            run(kernel, _RETURNS_NOTE, produces={"probe": "asset"})
        )
    )
    worker.start()
    try:
        assert storing.wait(DEADLINE_S)
        refused = kernel.cancel({"run_id": "run1"})
    finally:
        release.set()
        worker.join(timeout=DEADLINE_S)

    assert refused == {"cancelled": False}
    assert finished[0]["state"] == "succeeded"
    assert finished[0]["outputs"]["probe"]["kind"] == "note"
    assert link.names()[-1] == "materialized"


def test_a_run_that_prints_nothing_stores_no_log_artifact(tmp_path):
    kernel, _ = make_kernel(tmp_path)
    record = run(kernel, "def materialize(self, ctx):\n    return {}")

    assert record["log_ref"] is None
    assert record["cost_seconds"] >= 0


def test_each_materialization_keeps_the_logs_of_its_own_run(tmp_path):
    """Rewinding reads a materialization's own `log_ref`, so a later run of the
    same cell must not have replaced what the earlier one left."""
    kernel, _ = make_kernel(tmp_path)
    body = """
        def materialize(self, ctx):
            import sys
            print(f"training on {ctx.branch}")
            print(f"3/3 epochs on {ctx.branch}", file=sys.stderr)
            return {}
        """
    first = run(kernel, body, run_id="first", ctx_info={"branch": "main", "step": 1})
    second = run(
        kernel, body, run_id="second", ctx_info={"branch": "exp/lr-sweep", "step": 2}
    )

    assert first["log_ref"] != second["log_ref"]
    # Sorted because the two streams reach the artifact through a reader each:
    # what is pinned here is that both land in it, not their interleaving.
    assert sorted(stored_log(kernel, first).splitlines()) == [
        b"3/3 epochs on main",
        b"training on main",
    ]
    assert sorted(stored_log(kernel, second).splitlines()) == [
        b"3/3 epochs on exp/lr-sweep",
        b"training on exp/lr-sweep",
    ]


def test_the_events_narrate_the_run_in_order(tmp_path):
    kernel, link = make_kernel(tmp_path)
    run(kernel, _RETURNS_NOTE, produces={"probe": "asset"})

    assert link.names() == [
        "started",
        "kind_inferred",
        "preview",
        "materialized",
    ]


def test_two_runs_cannot_share_the_kernel(tmp_path):
    kernel, _ = make_kernel(tmp_path)
    marker, release = tmp_path / "running", tmp_path / "release"
    worker = threading.Thread(
        target=lambda: run(
            kernel,
            _spins_until(marker, release),
            run_id="first",
            produces={"never": "asset"},
        )
    )
    worker.start()
    try:
        _await(marker.exists)
        with pytest.raises(Exception, match="already running"):
            run(kernel, _RETURNS_NOTE, run_id="second")
    finally:
        release.write_text("go")
        worker.join(timeout=DEADLINE_S)


_RETURNS_NOTE = """
def materialize(self, ctx):
    return {"probe": "a note"}
"""


def _spins_until(marker: Path, release: Path) -> str:
    """A cell that announces itself, then loops in Python bytecode — where an
    injected cancel can land."""
    return f"""
def materialize(self, ctx):
    import pathlib, time
    pathlib.Path({str(marker)!r}).write_text("go")
    for _ in range(100_000):
        if pathlib.Path({str(release)!r}).exists():
            break
        time.sleep(0.001)
    return {{"never": "here"}}
"""


def _input(record: dict, output: str) -> dict:
    stored = record["outputs"][output]
    return {"value_ref": stored["value_ref"], "kind": stored["kind"]}


def _produce_rows(kernel, *, run_id: str = "producer", value=(1, 2, 3)) -> dict:
    """A materialized list — a value a consumer can change under the store."""
    record = run(
        kernel,
        f"""
        def materialize(self, ctx):
            return {{"rows": {list(value)!r}}}
        """,
        run_id=run_id,
        produces={"rows": "asset"},
    )
    return _input(record, "rows")


def _cached(kernel, spec: dict) -> object:
    """What the kernel would hand the next consumer of that value."""
    return kernel.executor.value(spec["value_ref"], spec["kind"])


def _await(condition, timeout: float = DEADLINE_S) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("the run never got going")
