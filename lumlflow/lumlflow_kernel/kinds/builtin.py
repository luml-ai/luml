"""The kinds every flow starts with.

Every serde library here imports lazily, inside the method that needs it, so a
flow that never returns a frame never pays for pyarrow — and the kernel keeps
its stdlib-only import rule. Matchers ask `sys.modules` before they ask
`isinstance`: a value of pandas' `DataFrame` cannot exist unless the cell that
made it imported pandas, so a matcher never has to import a library to rule it
out.

Serialization is deterministic on purpose. Content hashes decide whether
downstream cells rerun (early cutoff compares them per output), so a format
that stamped a timestamp into the bytes — a zip archive, say — would report a
change on every rematerialization of an unchanged value.
"""

from __future__ import annotations

import json
import pickle
import sys
from collections.abc import Callable
from pathlib import Path, PurePath
from typing import Any

from lumlflow_kernel.kinds import preview
from lumlflow_kernel.kinds.preview import Block

FRAME = "frame"
FILE = "file"
CHECKPOINT = "checkpoint"
EXPERIMENT = "experiment"
METRIC = "metric"
EVAL = "eval"
PLOT = "plot"
NOTE = "note"
PICKLE = "pickle"

_PICKLE_PROTOCOL = 4
_PLOT_DPI = 72
_VEGA_MARKS = ("mark", "marks", "layer")
_EXPERIMENT_SECTIONS = ("params", "metrics")


def asset_types() -> list[Any]:
    """Registry order is priority order: narrow claims first, pickle last."""
    return [
        FileKind(),
        PlotKind(),
        FrameKind(),
        CheckpointKind(),
        ExperimentKind(),
        MetricKind(),
        EvalKind(),
        NoteKind(),
        PickleKind(),
    ]


class FileKind:
    kind = FILE
    priority = 20
    python_types = ("pathlib.Path",)

    def matches(self, value: Any) -> bool:
        return isinstance(value, PurePath)

    def serialize(self, value: Any) -> bytes | Path:
        return Path(value)

    def deserialize(self, source: Path) -> Any:
        return source

    def preview(self, value: Any) -> list[Block]:
        path = Path(value)
        size = path.stat().st_size if path.exists() else 0
        return [preview.file(path.name, size, _content_type(path))]


class FrameKind:
    """Arrow IPC — the format a non-Python kernel could read tomorrow."""

    kind = FRAME
    priority = 40
    python_types = ("pandas.DataFrame", "polars.DataFrame")

    def matches(self, value: Any) -> bool:
        return _frame_flavor(value) is not None

    def serialize(self, value: Any) -> bytes | Path:
        import pyarrow as pa

        table = _arrow_table(value)
        sink = pa.BufferOutputStream()
        with pa.ipc.new_file(sink, table.schema) as writer:
            writer.write_table(table)
        return sink.getvalue().to_pybytes()

    def deserialize(self, source: Path) -> Any:
        import pyarrow as pa

        with pa.OSFile(str(source), "rb") as handle:
            table = pa.ipc.open_file(handle).read_all()
        if "pandas" in sys.modules or _importable("pandas"):
            return table.to_pandas()
        if "polars" in sys.modules or _importable("polars"):
            import polars

            return polars.from_arrow(table)
        return table

    def preview(self, value: Any) -> list[Block]:
        columns, dtypes = _frame_schema(value)
        rows = _frame_rows(value, 0, preview.HEAD_ROWS)
        return [preview.table(columns, dtypes, rows, len(value))]

    def page(self, value: Any, query: dict[str, Any]) -> dict[str, Any]:
        offset = max(int(query.get("offset", 0)), 0)
        limit = max(min(int(query.get("limit", 100)), 1000), 1)
        columns, dtypes = _frame_schema(value)
        return {
            "columns": columns,
            "dtypes": dtypes,
            "rows": _frame_rows(value, offset, limit),
            "offset": offset,
            "total_rows": len(value),
        }


class CheckpointKind:
    """A state dict: names to tensors.

    Pickled at protocol 4 rather than written as an archive — `.npz` and
    friends stamp their zip entries with the wall clock, which would change the
    content hash of an unchanged checkpoint on every run.
    """

    kind = CHECKPOINT
    priority = 50
    python_types = ("dict[str, numpy.ndarray]", "dict[str, torch.Tensor]")

    def matches(self, value: Any) -> bool:
        if not isinstance(value, dict) or not value:
            return False
        if not all(isinstance(name, str) for name in value):
            return False
        if not all(_is_tensor(entry) for entry in value.values()):
            return False
        # Checkpoint outranks metric, and a numpy or torch *scalar* carries
        # `shape` and `dtype` too — so `{"auc": roc_auc_score(...)}` would be
        # read as a state dict and lose its numbers to a pickle blob. A real
        # state dict always holds at least one array.
        return any(getattr(entry, "shape", ()) != () for entry in value.values())

    def serialize(self, value: Any) -> bytes | Path:
        return pickle.dumps(value, protocol=_PICKLE_PROTOCOL)

    def deserialize(self, source: Path) -> Any:
        return pickle.loads(source.read_bytes())

    def preview(self, value: Any) -> list[Block]:
        return [
            preview.kv(
                {
                    name: f"{getattr(entry, 'dtype', '?')} {tuple(entry.shape)}"
                    for name, entry in value.items()
                }
            )
        ]


class ExperimentKind:
    """A tracked run: the params a cell chose, and the numbers it got.

    The shape `ctx.tracker` records, matched by shape like `metric` and `eval`
    are — so a cell declaring `"run": "experiment"` and returning its tracker's
    record gets the rich rendering without a dict override. Nothing else claims
    it: `metric` wants numbers where this holds sections.
    """

    kind = EXPERIMENT
    priority = 55
    python_types = ("dict (params/metrics)",)

    def matches(self, value: Any) -> bool:
        if not isinstance(value, dict) or set(value) - set(_EXPERIMENT_SECTIONS):
            return False
        if not any(section in value for section in _EXPERIMENT_SECTIONS):
            return False
        return _flat(value.get("params", {}), _is_scalar) and _flat(
            value.get("metrics", {}), _is_number
        )

    def serialize(self, value: Any) -> bytes | Path:
        return _dumps({name: dict(section) for name, section in value.items()})

    def deserialize(self, source: Path) -> Any:
        return json.loads(source.read_bytes())

    def preview(self, value: Any) -> list[Block]:
        blocks: list[Block] = []
        for section in _EXPERIMENT_SECTIONS:
            entries = value.get(section) or {}
            if entries:
                blocks.extend([preview.markdown(f"**{section}**"), preview.kv(entries)])
        return blocks or [preview.markdown("*this run recorded nothing*")]


class MetricKind:
    """A flat dict of numbers — the shape `AGENTS.md` teaches."""

    kind = METRIC
    priority = 60
    python_types = ("dict[str, float]",)

    def matches(self, value: Any) -> bool:
        if not isinstance(value, dict) or not value:
            return False
        return all(isinstance(name, str) for name in value) and all(
            _is_number(entry) for entry in value.values()
        )

    def serialize(self, value: Any) -> bytes | Path:
        return _dumps(dict(value))

    def deserialize(self, source: Path) -> Any:
        return json.loads(source.read_bytes())

    def preview(self, value: Any) -> list[Block]:
        return [preview.kv(dict(value))]


class EvalKind:
    """Case rows with at least one score column — the LLM-evals shape."""

    kind = EVAL
    priority = 70
    python_types = ("list[dict]",)

    def matches(self, value: Any) -> bool:
        if not isinstance(value, list) or not value:
            return False
        if not all(isinstance(row, dict) for row in value):
            return False
        keys = set(value[0])
        if not keys or any(set(row) != keys for row in value):
            return False
        if not all(_is_scalar(entry) for row in value for entry in row.values()):
            return False
        return any(
            all(_is_number(row[key]) or isinstance(row[key], bool) for row in value)
            for key in keys
        )

    def serialize(self, value: Any) -> bytes | Path:
        return _dumps([dict(row) for row in value])

    def deserialize(self, source: Path) -> Any:
        return json.loads(source.read_bytes())

    def preview(self, value: Any) -> list[Block]:
        columns = list(value[0])
        rows = [[row.get(column) for column in columns] for row in value]
        blocks = [
            preview.table(
                columns, [""] * len(columns), rows[: preview.HEAD_ROWS], len(value)
            )
        ]
        aggregates = _aggregates(value, columns)
        if aggregates:
            blocks.append(preview.kv(aggregates))
        return blocks

    def page(self, value: Any, query: dict[str, Any]) -> dict[str, Any]:
        offset = max(int(query.get("offset", 0)), 0)
        limit = max(min(int(query.get("limit", 100)), 1000), 1)
        columns = list(value[0])
        window = value[offset : offset + limit]
        return {
            "columns": columns,
            "dtypes": [""] * len(columns),
            "rows": [[row.get(column) for column in columns] for row in window],
            "offset": offset,
            "total_rows": len(value),
        }


class PlotKind:
    kind = PLOT
    priority = 30
    python_types = ("matplotlib.figure.Figure", "dict (vega spec)")

    def matches(self, value: Any) -> bool:
        return _is_figure(value) or _is_vega(value)

    def serialize(self, value: Any) -> bytes | Path:
        return _png(value) if _is_figure(value) else _dumps(value)

    def deserialize(self, source: Path) -> Any:
        data = source.read_bytes()
        return json.loads(data) if data[:1] in (b"{", b"[") else data

    def preview(self, value: Any) -> list[Block]:
        if _is_figure(value):
            return [preview.image("image/png", _png(value))]
        return [preview.markdown(f"```json\n{json.dumps(value, indent=2)}\n```")]


class NoteKind:
    kind = NOTE
    priority = 80
    python_types = ("str",)

    def matches(self, value: Any) -> bool:
        return isinstance(value, str)

    def serialize(self, value: Any) -> bytes | Path:
        return value.encode("utf-8")

    def deserialize(self, source: Path) -> Any:
        return source.read_bytes().decode("utf-8")

    def preview(self, value: Any) -> list[Block]:
        return [preview.markdown(value)]


class PickleKind:
    """The fallback. It claims everything, so it is registered last."""

    kind = PICKLE
    priority = 1000
    python_types = ("object",)

    def matches(self, value: Any) -> bool:
        return True

    def serialize(self, value: Any) -> bytes | Path:
        pickler = _pickler()
        return pickler.dumps(value, protocol=_PICKLE_PROTOCOL)

    def deserialize(self, source: Path) -> Any:
        return pickle.loads(source.read_bytes())

    def preview(self, value: Any) -> list[Block]:
        if _is_curve(value):
            return [preview.series("values", value)]
        return [
            preview.kv(
                {
                    "type": type(value).__name__,
                    "value": repr(value),
                    "serialized with": _pickler().__name__,
                }
            )
        ]


def _pickler() -> Any:
    """cloudpickle when the venv has it — it handles the closures and locally
    defined classes a notebook-shaped cell produces; stdlib pickle otherwise."""
    try:
        import cloudpickle

        return cloudpickle
    except ImportError:
        return pickle


def _png(figure: Any) -> bytes:
    import io

    buffer = io.BytesIO()
    # `Software` carries the matplotlib version into the PNG; dropping it keeps
    # the same figure hashing the same across upgrades.
    figure.savefig(buffer, format="png", dpi=_PLOT_DPI, metadata={"Software": None})
    return buffer.getvalue()


def _dumps(value: Any) -> bytes:
    """Canonical JSON, except that NaN survives: a diverged loss is a real
    metric value, and the blob is only ever read back by the kind that wrote
    it."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _frame_flavor(value: Any) -> str | None:
    for name in ("pandas", "polars"):
        module = sys.modules.get(name)
        frame_type = getattr(module, "DataFrame", None) if module else None
        if frame_type is not None and isinstance(value, frame_type):
            return name
    return None


def _arrow_table(value: Any) -> Any:
    import pyarrow as pa

    if _frame_flavor(value) == "polars":
        return value.to_arrow()
    return pa.Table.from_pandas(value)


def _frame_schema(value: Any) -> tuple[list[str], list[str]]:
    columns = [str(column) for column in value.columns]
    dtypes = [str(dtype) for dtype in value.dtypes]
    return columns, dtypes


def _frame_rows(value: Any, offset: int, limit: int) -> list[list[Any]]:
    if _frame_flavor(value) == "polars":
        return [list(row) for row in value.slice(offset, limit).rows()]
    window = value.iloc[offset : offset + limit]
    return [list(row) for row in window.itertuples(index=False, name=None)]


def _aggregates(rows: list[dict[str, Any]], columns: list[str]) -> dict[str, Any]:
    """Per-column means over the numeric score columns."""
    means = {}
    for column in columns:
        values = [row[column] for row in rows if _is_number(row[column])]
        if len(values) == len(rows):
            means[f"mean {column}"] = sum(values) / len(values)
    return means


def _flat(section: Any, entry: Callable[[Any], bool]) -> bool:
    return isinstance(section, dict) and all(
        isinstance(name, str) and entry(value) for name, value in section.items()
    )


def _is_tensor(value: Any) -> bool:
    return hasattr(value, "shape") and hasattr(value, "dtype")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _is_curve(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and bool(value)
        and all(_is_number(entry) for entry in value)
    )


def _is_figure(value: Any) -> bool:
    module = sys.modules.get("matplotlib.figure")
    figure_type = getattr(module, "Figure", None) if module else None
    return figure_type is not None and isinstance(value, figure_type)


def _is_vega(value: Any) -> bool:
    """A spec, not a dict that happens to use the words.

    Key names alone would claim `{"data": 42, "mark": 7}`, and a flat dict of
    numbers is normatively a `metric` — plot outranks metric in the registry,
    so the values have to be spec-shaped too: vega's data is an object or an
    array and its marks are named or listed, never numbers.
    """
    if not isinstance(value, dict):
        return False
    schema = value.get("$schema")
    if isinstance(schema, str) and "vega" in schema:
        return True
    if not isinstance(value.get("data"), (dict, list)):
        return False
    return any(isinstance(value.get(mark), (str, dict, list)) for mark in _VEGA_MARKS)


def _importable(name: str) -> bool:
    from importlib.util import find_spec

    try:
        return find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _content_type(path: Path) -> str:
    from mimetypes import guess_type

    return guess_type(path.name)[0] or "application/octet-stream"
