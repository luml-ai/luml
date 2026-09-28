"""Which kind claims a value, what it writes, and what a preview may contain.

Pins the resolution order a materialization records as provenance — declared
override, then matcher by registry priority, then the pickle fallback — the
normative `metric` and `eval` shapes, and the workspace plugin scan that
imports only the modules saying they define kinds.

Serialization is asserted byte-for-byte because content hashes decide whether
downstream cells rerun; the preview envelope is asserted against its cap
because it is the UI contract and the only kernel-free tier.

pandas, polars, pyarrow and numpy are skipped into, not imported: these tests
also run under the venv floor, which holds nothing but the stdlib and pytest.
"""

import base64
import io
import math
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from lumlflow_kernel.cas import canonical_json
from lumlflow_kernel.kernel import Kernel
from lumlflow_kernel.kinds import builtin, preview, registry
from lumlflow_kernel.tracker import ExperimentRef
from tests.kernel.helpers import FakeLink, make_kernel, run, stored_preview

BADGE_PLUGIN = '''
import hashlib


class BadgeKind:
    """A workspace kind, defined without importing the kernel."""

    kind = "badge"
    priority = 15
    python_types = ("str",)

    def matches(self, value):
        return isinstance(value, str) and value.strip().lower().startswith("badge:")

    def serialize(self, value):
        return value.encode("utf-8")

    def deserialize(self, source):
        return source.read_bytes().decode("utf-8")

    def preview(self, value):
        return [{"block": "markdown", "text": value}]

    def content_hash(self, value):
        return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()

    def page(self, value, query):
        return {"badge": value, "offset": query.get("offset", 0)}


LUMLFLOW_KINDS = [BadgeKind()]
'''

TINY_PLUGIN = """
class TinyKind:
    kind = "tiny"

    def matches(self, value):
        return value == "tiny"

    def serialize(self, value):
        return b"tiny"

    def deserialize(self, source):
        return source.read_bytes().decode("utf-8")

    def preview(self, value):
        return [{"block": "markdown", "text": "tiny"}]


LUMLFLOW_KINDS = TinyKind
"""

BOOM = """
raise RuntimeError("a kind scan must not import me")
"""

SCENARIO_CELL = """
def materialize(self, ctx):
    import pandas as pd

    return {
        "frame": pd.DataFrame({"step": [1, 2], "loss": [0.5, float("nan")]}),
        "scores": {"auc": 0.91},
        "badge": "badge: green",
        "leftover": {"threshold": {"low": 0.1}},
        "headline": "badge: blue",
    }
"""

SCENARIO_PRODUCES: dict[str, Any] = {
    "frame": "asset",
    "scores": "asset",
    "badge": "asset",
    "leftover": "asset",
    "headline": {"type": "asset", "kind": "note"},
}

Scenario = tuple[Kernel, FakeLink, dict[str, Any]]


@pytest.fixture(autouse=True)
def forget_workspace_modules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Plugins are imported by module name, so a second test writing
    `kinds_plugin.py` would otherwise resolve to the first test's module."""
    monkeypatch.setattr(sys, "path", list(sys.path))
    yield
    root = str(tmp_path)
    for name, module in list(sys.modules.items()):
        origin = getattr(module, "__file__", None)
        if isinstance(origin, str) and origin.startswith(root):
            del sys.modules[name]


@pytest.fixture
def kinds() -> registry.Registry:
    return registry.build(None)


@pytest.fixture
def scenario(tmp_path: Path) -> Scenario:
    pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    kernel, link = make_kernel(
        tmp_path, files={"kinds_plugin.py": BADGE_PLUGIN, "boom.py": BOOM}
    )
    record = run(kernel, SCENARIO_CELL, produces=SCENARIO_PRODUCES)
    assert record["state"] == "succeeded", record.get("error")
    return kernel, link, record


def workspace_with(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (root / name).write_text(body, encoding="utf-8")
    return root


def round_trip(asset_type: Any, value: Any, tmp_path: Path) -> Any:
    """Through a blob file, the way a value reaches a consuming cell."""
    serialized = asset_type.serialize(value)
    blob = tmp_path / "blob"
    blob.write_bytes(
        serialized if isinstance(serialized, bytes) else serialized.read_bytes()
    )
    return asset_type.deserialize(blob)


def kind_sources(record: dict[str, Any]) -> dict[str, tuple[str, str]]:
    return {
        name: (output["kind"], output["kind_source"])
        for name, output in record["outputs"].items()
    }


def test_a_run_records_the_kind_it_inferred_and_where_it_came_from(
    scenario: Scenario,
) -> None:
    _, _, record = scenario
    assert kind_sources(record) == {
        "frame": (builtin.FRAME, registry.MATCHER),
        "scores": (builtin.METRIC, registry.MATCHER),
        "badge": ("badge", registry.MATCHER),
        "leftover": (builtin.PICKLE, registry.FALLBACK),
        "headline": (builtin.NOTE, registry.DECLARED),
    }


def test_a_declared_kind_beats_what_the_value_looks_like(scenario: Scenario) -> None:
    kernel, _, record = scenario
    assert kernel.registry.resolve("badge: blue").kind == "badge"
    assert record["outputs"]["headline"]["kind"] == builtin.NOTE
    assert record["outputs"]["headline"]["kind_source"] == registry.DECLARED


def test_the_daemon_hears_one_kind_inferred_event_per_output(
    scenario: Scenario,
) -> None:
    _, link, record = scenario
    heard = {
        event["output"]: (event["kind"], event["kind_source"])
        for event in link.named("kind_inferred")
    }
    assert heard == kind_sources(record)


def test_every_output_stores_a_bounded_preview_whatever_its_kind(
    scenario: Scenario,
) -> None:
    kernel, _, record = scenario
    for name, output in record["outputs"].items():
        envelope = stored_preview(kernel, record, name)
        assert envelope["schema"] == preview.PREVIEW_SCHEMA_VERSION, name
        assert envelope["kind"] == output["kind"], name
        assert envelope["blocks"], name
        assert len(canonical_json(envelope)) <= preview.MAX_PREVIEW_BYTES, name


def test_a_stored_frame_preview_carries_a_diverged_loss_as_null(
    scenario: Scenario,
) -> None:
    kernel, _, record = scenario
    block = stored_preview(kernel, record, "frame")["blocks"][0]
    assert block["rows"] == [[1, 0.5], [2, None]]


def test_a_workspace_module_declaring_kinds_registers_under_its_filename(
    tmp_path: Path,
) -> None:
    workspace = workspace_with(tmp_path / "project", {"kinds.py": BADGE_PLUGIN})
    entries = {entry["kind"]: entry for entry in registry.build(workspace).report()}
    assert entries["badge"]["provenance"] == "`kinds.py`"
    assert entries["badge"]["priority"] == 15
    assert entries["badge"]["python_types"] == ["str"]


def test_a_workspace_module_declaring_no_kinds_is_never_imported(
    tmp_path: Path,
) -> None:
    workspace = workspace_with(
        tmp_path / "project", {"kinds_plugin.py": BADGE_PLUGIN, "boom.py": BOOM}
    )
    built = registry.build(workspace)
    assert built.resolve("badge: green").kind == "badge"
    assert "boom" not in sys.modules


def test_a_declared_class_is_instantiated_and_claims_a_type_back(
    tmp_path: Path,
) -> None:
    workspace = workspace_with(tmp_path / "project", {"tiny_kind.py": TINY_PLUGIN})
    built = registry.build(workspace)
    first = built.report()[0]
    assert (first["kind"], first["priority"]) == ("tiny", registry.PLUGIN_PRIORITY)
    assert first["python_types"] == []
    assert built.resolve("tiny").kind == "tiny"
    assert built.resolve("not tiny").kind == builtin.NOTE


def test_a_plugins_content_hash_stands_in_for_the_value_hash(tmp_path: Path) -> None:
    kernel, _ = make_kernel(tmp_path, files={"kinds_plugin.py": BADGE_PLUGIN})
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            return {"green": "badge: Green", "shouted": "BADGE: GREEN  "}
        """,
        produces={"green": "asset", "shouted": "asset"},
    )
    green, shouted = record["outputs"]["green"], record["outputs"]["shouted"]
    assert green["value_ref"] != shouted["value_ref"]
    assert green["content_hash"] == shouted["content_hash"]
    assert green["content_hash"] != green["value_ref"]


def test_a_plugins_page_hook_answers_the_page_call(tmp_path: Path) -> None:
    kernel, _ = make_kernel(tmp_path, files={"kinds_plugin.py": BADGE_PLUGIN})
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            return {"badge": "badge: green"}
        """,
        produces={"badge": "asset"},
    )
    page = kernel.page(
        {
            "value_ref": record["outputs"]["badge"]["value_ref"],
            "kind": "badge",
            "query": {"offset": 3},
        }
    )
    assert page == {"badge": "badge: green", "offset": 3}


def test_a_tracker_record_is_an_experiment(kinds: registry.Registry) -> None:
    ref = ExperimentRef(
        experiment_id="exp-1",
        group="churn",
        store=Path("/tmp/experiments"),
        snapshot={
            "params": {"lr": 3e-4, "optimizer": "adamw"},
            "metrics": {"auc": 0.91},
        },
    )
    resolution = kinds.resolve(ref)
    assert (resolution.kind, resolution.source) == (
        builtin.EXPERIMENT,
        registry.MATCHER,
    )


def test_an_experiment_shaped_dict_is_not_an_experiment(
    kinds: registry.Registry,
) -> None:
    resolution = kinds.resolve({"params": {"lr": 3e-4}, "metrics": {"auc": 0.91}})
    assert (resolution.kind, resolution.source) == (builtin.PICKLE, registry.FALLBACK)


def test_experiment_serialization_requires_a_tracker_record(
    kinds: registry.Registry,
) -> None:
    with pytest.raises(TypeError, match="ctx.tracker.record"):
        kinds.get(builtin.EXPERIMENT).serialize(
            {"params": {"lr": 3e-4}, "metrics": {"auc": 0.91}}
        )


def test_an_experiment_previews_its_params_and_its_numbers(
    kinds: registry.Registry,
) -> None:
    ref = ExperimentRef(
        experiment_id="exp-1",
        group="churn",
        store=Path("/tmp/experiments"),
        snapshot={
            "params": {"lr": 3e-4},
            "metrics": {"auc": 0.91, "f1": 0.83},
        },
    )
    assert kinds.get(builtin.EXPERIMENT).preview(ref) == [
        {"block": "markdown", "text": "**params**"},
        {"block": "kv", "entries": {"lr": 3e-4}},
        {"block": "markdown", "text": "**metrics**"},
        {"block": "kv", "entries": {"auc": 0.91, "f1": 0.83}},
    ]


def test_an_experiment_that_recorded_nothing_says_so_rather_than_showing_nothing(
    kinds: registry.Registry,
) -> None:
    ref = ExperimentRef(
        experiment_id="exp-1",
        group="churn",
        store=Path("/tmp/experiments"),
        snapshot={"params": {}, "metrics": {}},
    )
    blocks = kinds.get(builtin.EXPERIMENT).preview(ref)
    assert blocks == [{"block": "markdown", "text": "*this run recorded nothing*"}]


def test_an_experiment_ref_round_trips_and_hashes_only_its_snapshot(
    kinds: registry.Registry, tmp_path: Path
) -> None:
    asset_type = kinds.get(builtin.EXPERIMENT)
    assert isinstance(asset_type, builtin.ExperimentKind)
    snapshot = {
        "params": {"lr": 3e-4},
        "metrics": {"z_score": 0.91, "accuracy": 0.83},
    }
    first = ExperimentRef(
        experiment_id="exp-1",
        group="churn",
        store=tmp_path / "first-store",
        snapshot=snapshot,
    )
    second = ExperimentRef(
        experiment_id="exp-2",
        group="another-flow",
        store=tmp_path / "second-store",
        snapshot={
            "metrics": {"accuracy": 0.83, "z_score": 0.91},
            "params": {"lr": 3e-4},
        },
    )

    restored = round_trip(asset_type, first, tmp_path)
    assert restored == first
    assert list(restored.snapshot["metrics"]) == ["z_score", "accuracy"]
    assert asset_type.content_hash(first) == asset_type.content_hash(second)
    assert asset_type.serialize(first) != asset_type.serialize(second)


def test_a_flat_dict_of_numbers_is_a_metric(kinds: registry.Registry) -> None:
    resolution = kinds.resolve({"auc": 0.91, "steps": 40})
    assert (resolution.kind, resolution.source) == (builtin.METRIC, registry.MATCHER)


def test_scores_from_a_scoring_library_are_a_metric_not_a_checkpoint(
    kinds: registry.Registry,
) -> None:
    """`{"auc": roc_auc_score(...), "f1": f1_score(...)}` is the spec's own
    example, and sklearn hands back numpy scalars — which carry `shape` and
    `dtype` exactly like the tensors a checkpoint is made of."""
    numpy = pytest.importorskip("numpy")

    scores = {"auc": numpy.float64(0.91), "f1": numpy.float64(0.83)}
    assert kinds.resolve(scores).kind == builtin.METRIC
    # A state dict keeps its kind even when a 0-d entry rides along, the way
    # torch's `num_batches_tracked` does.
    state = {"w": numpy.zeros((2, 3)), "steps": numpy.int64(4)}
    assert kinds.resolve(state).kind == builtin.CHECKPOINT


@pytest.mark.parametrize(
    "value",
    [
        {"passed": True, "flaky": False},
        {},
        {"scores": {"auc": 0.91}},
        {1: 0.91},
    ],
)
def test_a_dict_that_is_not_flat_numbers_is_not_a_metric(
    kinds: registry.Registry, value: dict[Any, Any]
) -> None:
    resolution = kinds.resolve(value)
    assert (resolution.kind, resolution.source) == (builtin.PICKLE, registry.FALLBACK)


@pytest.mark.parametrize(
    ("value", "kind"),
    [
        ({"$schema": "https://vega.github.io/schema/v5.json", "a": 1}, builtin.PLOT),
        ({"data": {"values": [{"x": 1}]}, "mark": "bar"}, builtin.PLOT),
        ({"data": [{"x": 1}], "layer": [{"mark": "line"}]}, builtin.PLOT),
        # Plot outranks metric, so the vega matcher has to read shapes rather
        # than words: this one is a flat dict of numbers and nothing else.
        ({"data": 42, "mark": 7}, builtin.METRIC),
    ],
)
def test_a_vega_spec_is_told_from_a_metric_that_borrows_its_words(
    kinds: registry.Registry, value: dict[str, Any], kind: str
) -> None:
    assert kinds.resolve(value).kind == kind


@pytest.mark.parametrize(
    "rows",
    [
        [{"case": "a", "score": 0.5}, {"case": "b", "score": 0.9}],
        [{"case": "a", "passed": True}, {"case": "b", "passed": False}],
    ],
)
def test_uniform_rows_with_a_score_column_are_an_eval(
    kinds: registry.Registry, rows: list[dict[str, Any]]
) -> None:
    resolution = kinds.resolve(rows)
    assert (resolution.kind, resolution.source) == (builtin.EVAL, registry.MATCHER)


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [{"case": "a", "score": 0.5}, {"case": "b", "grade": 0.9}],
        [{"case": "a", "verdict": "good"}, {"case": "b", "verdict": "bad"}],
        [{"case": "a", "score": 0.5}, {"case": "b", "score": "high"}],
    ],
)
def test_ragged_or_scoreless_rows_are_not_an_eval(
    kinds: registry.Registry, rows: list[Any]
) -> None:
    resolution = kinds.resolve(rows)
    assert (resolution.kind, resolution.source) == (builtin.PICKLE, registry.FALLBACK)


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        (builtin.METRIC, {"auc": 0.91, "steps": 40}),
        (builtin.EVAL, [{"case": "a", "score": 0.5}, {"case": "b", "score": 0.9}]),
        (builtin.NOTE, "## Findings\n\nThe seed matters — café included."),
        (builtin.PLOT, {"$schema": "https://vega.github.io/schema/v5.json", "a": 1}),
        (builtin.PICKLE, {"threshold": {"low": 0.1}}),
    ],
)
def test_a_value_comes_back_equal_from_its_blob(
    kinds: registry.Registry, kind: str, value: Any, tmp_path: Path
) -> None:
    assert kinds.resolve(value).kind == kind
    assert round_trip(kinds.get(kind), value, tmp_path) == value


def test_a_frame_comes_back_equal_from_its_arrow_blob(
    kinds: registry.Registry, tmp_path: Path
) -> None:
    pandas = pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    frame = pandas.DataFrame({"step": [1, 2, 3], "label": ["a", "b", "c"]})
    assert round_trip(kinds.get(builtin.FRAME), frame, tmp_path).equals(frame)


def test_a_polars_frame_stays_polars_when_pandas_is_also_installed(
    kinds: registry.Registry, tmp_path: Path
) -> None:
    pytest.importorskip("pandas")
    polars = pytest.importorskip("polars")
    pytest.importorskip("pyarrow")
    frame = polars.DataFrame({"step": [1, 2, 3], "label": ["a", "b", "c"]})

    restored = round_trip(kinds.get(builtin.FRAME), frame, tmp_path)

    assert "pandas" in sys.modules
    assert isinstance(restored, polars.DataFrame)
    assert restored.to_dict(as_series=False) == frame.to_dict(as_series=False)


def test_a_checkpoint_comes_back_array_for_array(
    kinds: registry.Registry, tmp_path: Path
) -> None:
    numpy = pytest.importorskip("numpy")
    state = {"w": numpy.arange(6, dtype="float32").reshape(2, 3), "b": numpy.zeros(3)}
    restored = round_trip(kinds.get(builtin.CHECKPOINT), state, tmp_path)
    assert list(restored) == list(state)
    assert all(numpy.array_equal(restored[name], state[name]) for name in state)


def test_a_file_is_stored_as_itself_and_read_back_as_a_path(
    kinds: registry.Registry, tmp_path: Path
) -> None:
    source = tmp_path / "rows.csv"
    source.write_text("step,loss\n1,0.5\n", encoding="utf-8")
    asset_type = kinds.get(builtin.FILE)
    assert asset_type.serialize(source) == source
    stored = round_trip(asset_type, source, tmp_path)
    assert isinstance(stored, Path)
    assert stored.read_bytes() == source.read_bytes()
    assert asset_type.preview(source) == [
        {
            "block": "file",
            "name": "rows.csv",
            "size": source.stat().st_size,
            "content_type": "text/csv",
        }
    ]


def test_the_same_frame_serializes_to_the_same_bytes(
    kinds: registry.Registry,
) -> None:
    pandas = pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    frame = pandas.DataFrame({"step": [1, 2, 3], "loss": [0.5, 0.4, 0.35]})
    asset_type = kinds.get(builtin.FRAME)
    assert asset_type.serialize(frame) == asset_type.serialize(frame)


def test_the_same_checkpoint_serializes_to_the_same_bytes(
    kinds: registry.Registry,
) -> None:
    numpy = pytest.importorskip("numpy")
    state = {"w": numpy.arange(6, dtype="float32").reshape(2, 3), "b": numpy.zeros(3)}
    asset_type = kinds.get(builtin.CHECKPOINT)
    assert asset_type.serialize(state) == asset_type.serialize(state)


def test_metric_and_eval_bytes_do_not_depend_on_key_order(
    kinds: registry.Registry,
) -> None:
    metric = kinds.get(builtin.METRIC)
    assert metric.serialize({"auc": 0.91, "f1": 0.83}) == metric.serialize(
        {"f1": 0.83, "auc": 0.91}
    )
    cases = kinds.get(builtin.EVAL)
    assert cases.serialize([{"case": "a", "score": 0.5}]) == cases.serialize(
        [{"score": 0.5, "case": "a"}]
    )


def test_a_diverged_metric_survives_its_blob(
    kinds: registry.Registry, tmp_path: Path
) -> None:
    restored = round_trip(kinds.get(builtin.METRIC), {"loss": float("nan")}, tmp_path)
    assert math.isnan(restored["loss"])


def test_non_finite_metrics_are_strings_in_the_stored_preview(tmp_path: Path) -> None:
    kernel, _ = make_kernel(tmp_path)
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            return {
                "scores": {
                    "loss": float("nan"),
                    "upper": float("inf"),
                    "lower": float("-inf"),
                }
            }
        """,
        produces={"scores": "asset"},
    )

    envelope = stored_preview(kernel, record, "scores")

    assert envelope["blocks"][0]["entries"] == {
        "loss": "nan",
        "upper": "inf",
        "lower": "-inf",
    }
    canonical_json(envelope)


def test_the_envelope_states_its_schema_its_kind_and_its_blocks() -> None:
    assert preview.envelope("metric", [preview.kv({"auc": 0.91})]) == {
        "schema": preview.PREVIEW_SCHEMA_VERSION,
        "kind": "metric",
        "blocks": [{"block": "kv", "entries": {"auc": 0.91}}],
        "truncated": False,
    }


def test_a_frame_preview_holds_head_rows_and_the_true_total(
    kinds: registry.Registry,
) -> None:
    pandas = pytest.importorskip("pandas")
    rows = preview.HEAD_ROWS * 3
    frame = pandas.DataFrame({"step": range(rows), "loss": [0.5] * rows})
    block = kinds.get(builtin.FRAME).preview(frame)[0]
    assert block["block"] == "table"
    assert block["columns"] == ["step", "loss"]
    assert len(block["rows"]) == preview.HEAD_ROWS
    assert block["rows"][0] == [0, 0.5]
    assert block["total_rows"] == rows


def test_a_wide_frame_preview_and_page_share_the_column_bound_and_normalizer(
    kinds: registry.Registry,
) -> None:
    pandas = pytest.importorskip("pandas")
    long_text = "x" * 200
    columns: dict[str, list[Any]] = {
        "loss": [float("nan")],
        "when": [pandas.Timestamp("2026-08-29T12:30:00")],
        "detail": [long_text],
    }
    columns.update({f"column_{index}": [index] for index in range(197)})
    frame = pandas.DataFrame(columns)
    asset_type = kinds.get(builtin.FRAME)
    assert isinstance(asset_type, builtin.FrameKind)

    head = asset_type.preview(frame)[0]
    page = asset_type.page(frame, {"offset": 0, "limit": 10})

    assert len(head["columns"]) == 40
    assert head["total_columns"] == 200
    assert len(page["columns"]) == 40
    assert len(page["dtypes"]) == 40
    assert page["total_columns"] == 200
    assert page["rows"][0][0] is None
    assert isinstance(page["rows"][0][1], str)
    assert page["rows"][0][2] == long_text
    canonical_json(page)


def test_an_eval_page_normalizes_cells_and_bounds_columns(
    kinds: registry.Registry,
) -> None:
    row: dict[str, Any] = {"loss": float("inf")}
    row.update({f"column_{index}": index for index in range(44)})
    asset_type = kinds.get(builtin.EVAL)
    assert isinstance(asset_type, builtin.EvalKind)

    page = asset_type.page([row], {"offset": 0})

    assert len(page["columns"]) == 40
    assert len(page["rows"][0]) == 40
    assert page["total_columns"] == 45
    assert page["rows"][0][0] is None
    canonical_json(page)


def test_a_preview_over_the_cap_comes_back_under_it_and_says_so() -> None:
    columns = [f"c{index}" for index in range(30)]
    rows = [["y" * 200] * len(columns) for _ in range(preview.HEAD_ROWS)]
    envelope = preview.envelope(
        "frame", [preview.table(columns, [""] * len(columns), rows, 5000)]
    )
    block = envelope["blocks"][0]
    assert len(canonical_json(envelope)) <= preview.MAX_PREVIEW_BYTES
    assert envelope["truncated"] is True
    assert 0 < len(block["rows"]) < preview.HEAD_ROWS
    assert block["total_rows"] == 5000


def test_an_oversized_text_preview_is_clipped_with_a_marker() -> None:
    envelope = preview.envelope(
        "note", [preview.markdown("x" * (4 * preview.MAX_PREVIEW_BYTES))]
    )
    assert len(canonical_json(envelope)) <= preview.MAX_PREVIEW_BYTES
    assert envelope["truncated"] is True
    block = envelope["blocks"][0]
    assert block["block"] == "markdown"
    assert "truncated" in block["text"]


def test_an_oversized_key_value_preview_keeps_its_first_entries() -> None:
    entries = {f"key_{index}": index for index in range(10_000)}

    envelope = preview.envelope("metric", [preview.kv(entries)])

    assert len(canonical_json(envelope)) <= preview.MAX_PREVIEW_BYTES
    assert envelope["truncated"] is True
    kept = envelope["blocks"][0]
    assert kept["block"] == "kv"
    assert 0 < len(kept["entries"]) < len(entries)
    assert list(kept["entries"]) == list(entries)[: len(kept["entries"])]


def test_an_oversized_figure_preview_keeps_a_downscaled_image(
    kinds: registry.Registry,
) -> None:
    image_module = pytest.importorskip("PIL.Image")
    figure_module = pytest.importorskip("matplotlib.figure")
    numpy = pytest.importorskip("numpy")
    figure = figure_module.Figure(figsize=(12, 8))
    axes = figure.subplots()
    axes.imshow(numpy.random.default_rng(7).random((600, 900, 3)))
    axes.set_axis_off()
    original = kinds.get(builtin.PLOT).preview(figure)[0]
    assert len(base64.b64decode(original["data"])) > preview.MAX_PREVIEW_BYTES

    envelope = preview.envelope(builtin.PLOT, [original])

    assert len(canonical_json(envelope)) <= preview.MAX_PREVIEW_BYTES
    assert envelope["truncated"] is True
    downscaled = envelope["blocks"][0]
    assert downscaled["block"] == "image"
    with image_module.open(io.BytesIO(base64.b64decode(original["data"]))) as before:
        original_size = before.size
    with image_module.open(io.BytesIO(base64.b64decode(downscaled["data"]))) as after:
        assert after.width < original_size[0]
        assert after.height < original_size[1]


@pytest.mark.parametrize("total", [preview.MAX_POINTS + 1, 2000, 5000])
def test_a_long_series_keeps_its_ends_within_the_point_cap(total: int) -> None:
    block = preview.series("loss", [float(step) for step in range(total)])
    assert len(block["points"]) <= preview.MAX_POINTS
    assert block["points"][0] == [0, 0.0]
    assert block["points"][-1] == [total - 1, float(total - 1)]
    assert block["total_points"] == total


def test_a_short_series_keeps_every_point() -> None:
    block = preview.series("loss", [0.5, 0.4, 0.35])
    assert block["points"] == [[0, 0.5], [1, 0.4], [2, 0.35]]
    assert block["total_points"] == 3


def test_nan_and_numpy_scalars_leave_the_preview_json_safe() -> None:
    numpy = pytest.importorskip("numpy")
    envelope = preview.envelope(
        "metric",
        [
            preview.kv(
                {
                    "auc": numpy.float64(0.91),
                    "steps": numpy.int64(40),
                    "loss": float("nan"),
                }
            ),
            preview.series("loss", [numpy.float32(1.0), float("inf"), 0.5]),
        ],
    )
    assert envelope["blocks"][0]["entries"] == {
        "auc": 0.91,
        "steps": 40,
        "loss": None,
    }
    assert envelope["blocks"][1]["points"] == [[0, 1.0], [1, None], [2, 0.5]]
    # `canonical_json` refuses NaN and Infinity, which is why the cells above
    # are None: an unencodable preview would take the whole run's record down.
    assert b"NaN" not in canonical_json(envelope)


def test_an_unknown_declared_kind_names_itself_in_the_error(
    kinds: registry.Registry,
) -> None:
    with pytest.raises(registry.KindError) as raised:
        kinds.resolve({"auc": 0.91}, "frame_v2")
    assert "frame_v2" in str(raised.value)
    assert "metric" in str(raised.value)


def test_the_report_lists_the_builtins_in_priority_order(
    kinds: registry.Registry,
) -> None:
    builtins = [entry for entry in kinds.report() if entry["provenance"] == "builtin"]
    assert [(entry["kind"], entry["priority"]) for entry in builtins] == [
        (builtin.FILE, 20),
        (builtin.PLOT, 30),
        (builtin.FRAME, 40),
        (builtin.CHECKPOINT, 50),
        (builtin.EXPERIMENT, 55),
        (builtin.METRIC, 60),
        (builtin.EVAL, 70),
        (builtin.NOTE, 80),
        (builtin.PICKLE, 1000),
    ]
    assert all(entry["python_types"] for entry in builtins)
