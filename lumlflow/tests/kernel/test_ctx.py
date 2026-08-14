"""`ctx`: what a cell may reach for, and what reaching for it costs.

Two of these handles are recorded rather than trusted — reading the branch
makes a run identity-dependent, reaching outside the flow makes it external —
because the scheduler's claims about reuse depend on knowing.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from lumlflow_kernel.ctxobj import EXTERNAL, IDENTITY, Ctx


def test_reading_identity_and_external_handles_is_observed(tmp_path):
    seen: list[tuple[str, str]] = []
    ctx = _ctx(tmp_path, observe=lambda fact, detail: seen.append((fact, detail)))

    assert ctx.branch == "main"
    assert ctx.step == 7
    assert ctx.workspace_dir == tmp_path
    assert ctx.flow_dir == tmp_path / "churn.flow"
    assert [fact for fact, _ in seen] == [IDENTITY, IDENTITY, EXTERNAL, EXTERNAL]
    assert "`ctx.branch`" in seen[0][1]


def test_a_cell_that_touches_nothing_is_observed_as_nothing(tmp_path):
    seen: list[tuple[str, str]] = []
    _ctx(tmp_path, observe=lambda fact, detail: seen.append((fact, detail)))

    assert seen == []


def test_seed_applies_the_declared_seed(tmp_path):
    ctx = _ctx(tmp_path, params={"seed": 1337})

    ctx.seed()
    first = [random.random() for _ in range(3)]
    ctx.seed()

    assert [random.random() for _ in range(3)] == first


def test_seed_reaches_numpy_when_the_cell_has_imported_it(tmp_path):
    numpy = pytest.importorskip("numpy")
    ctx = _ctx(tmp_path, params={"seed": 1337})

    ctx.seed()
    first = numpy.random.rand(3).tolist()
    ctx.seed()

    assert numpy.random.rand(3).tolist() == first


def test_seed_without_a_declared_seed_says_where_to_put_one(tmp_path):
    ctx = _ctx(tmp_path, params={"lr": 3e-4})

    with pytest.raises(ValueError, match="`params`"):
        ctx.seed()


def test_tempdir_lands_inside_the_run_scratch(tmp_path):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    ctx = _ctx(tmp_path, scratch=scratch)

    first, second = ctx.tempdir(), ctx.tempdir()

    assert first != second
    assert first.parent == scratch
    assert first.is_dir()


def test_the_tracker_records_locally_and_reaches_nothing(tmp_path):
    seen: list[tuple[str, str]] = []
    ctx = _ctx(tmp_path, observe=lambda fact, detail: seen.append((fact, detail)))

    ctx.tracker.log_params({"lr": 3e-4, "optimizer": "adamw"})
    ctx.tracker.log_param("seed", 1337)
    ctx.tracker.log_metrics({"auc": 0.91})
    ctx.tracker.log_metric("f1", 0.83)

    assert ctx.tracker.record == {
        "params": {"lr": 3e-4, "optimizer": "adamw", "seed": 1337},
        "metrics": {"auc": 0.91, "f1": 0.83},
    }
    # Recording is not identity, and it is not a reach outside the flow: a run
    # that only logged its own numbers stays memoizable.
    assert seen == []


def test_the_tracker_is_one_recorder_for_the_run(tmp_path):
    ctx = _ctx(tmp_path)

    assert ctx.tracker is ctx.tracker


def test_a_metric_that_is_not_a_number_says_where_it_belongs(tmp_path):
    ctx = _ctx(tmp_path)

    with pytest.raises(ValueError, match="param"):
        ctx.tracker.log_metric("notes", "ran overnight")
    # A bool is not a measurement either — it would render as 1 and compare as
    # one, which is not what was recorded.
    with pytest.raises(ValueError, match="number"):
        ctx.tracker.log_metric("converged", True)
    assert ctx.tracker.record["metrics"] == {}


def test_the_record_is_a_copy_a_cell_cannot_write_back_through(tmp_path):
    ctx = _ctx(tmp_path)
    ctx.tracker.log_metric("auc", 0.91)

    ctx.tracker.record["metrics"]["auc"] = 0.0

    assert ctx.tracker.record["metrics"] == {"auc": 0.91}


def test_a_secret_is_asked_for_by_name_and_never_held(tmp_path):
    asked: list[str] = []
    ctx = _ctx(tmp_path, ask_secret=lambda name: asked.append(name) or "sk-live-1")

    assert ctx.secret("API_KEY") == "sk-live-1"
    assert asked == ["API_KEY"]


def _ctx(
    tmp_path: Path,
    *,
    params: dict | None = None,
    scratch: Path | None = None,
    observe=lambda fact, detail: None,
    ask_secret=lambda name: "",
) -> Ctx:
    return Ctx(
        branch="main",
        step=7,
        workspace_dir=tmp_path,
        flow_dir=tmp_path / "churn.flow",
        params=params or {},
        scratch=scratch or tmp_path,
        observe=observe,
        ask_secret=ask_secret,
    )
