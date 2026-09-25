"""A stored model, packaged the way LUML takes one.

LUML stores models as fnnx bundles, and only the flavor that trained a model
knows how to build one — so this runs where the model's own libraries are: in
the kernel, on the value the cell returned. The daemon names the value and a
destination; what comes back is a bundle on disk it can hand to the uploader.

The packaging is `luml`'s own — the same save functions `tracker.log_model`
calls on a raw estimator — so a model published from a cell is byte-for-byte
the kind an experiment would have logged.
"""

from __future__ import annotations

import importlib
import shutil
from pathlib import Path
from typing import Any

from lumlflow_kernel.executor import CellError, Executor

#: Rows a flavor sees when inferring a model's input schema from a sample.
_SAMPLE_ROWS = 5


def export_model(
    executor: Executor,
    *,
    value_ref: str,
    kind: str,
    destination: str,
    sample: dict[str, Any] | None = None,
    flavor: str | None = None,
) -> dict[str, Any]:
    """Write the fnnx bundle for a stored model at `destination`.

    `sample` names a stored frame — the one the cell trained on — whose head
    gives the flavor its input schema. A model that names its own features
    (`feature_names_in_`) is handed only those columns, so a training frame
    still carrying the target column does not leak it into the signature.
    """
    registry, detect = _luml_flavors()
    model = executor.value(value_ref, kind)
    chosen = flavor or _detect(model, detect)
    if chosen not in registry:
        raise CellError(
            f"`{chosen}` is not a flavor luml can package "
            f"(supported: {', '.join(sorted(registry))})"
        )
    module_path, function_name = registry[chosen]
    try:
        save = getattr(importlib.import_module(module_path), function_name)
    except ImportError as failure:
        raise CellError(
            f"packaging a `{chosen}` model needs `{failure.name}` in this flow's "
            "environment"
        ) from failure
    inputs = _sample_inputs(model, _sample_value(executor, sample))
    target = Path(destination)
    try:
        if inputs is not None:
            reference = save(model, inputs, path=str(target))
        else:
            reference = save(model, path=str(target))
    except CellError:
        raise
    except Exception as failure:
        raise CellError(f"luml could not package the model: {failure}") from failure
    written = Path(str(reference.path))
    if written.resolve() != target.resolve():
        shutil.move(str(written), str(target))
    return {
        "path": str(target),
        "flavor": chosen,
        "size": target.stat().st_size,
    }


def _luml_flavors() -> tuple[dict[str, tuple[str, str]], Any]:
    try:
        from luml.experiments.tracker import _FLAVOR_REGISTRY, ExperimentTracker
    except ImportError as failure:
        raise CellError(
            "publishing a model to LUML needs `luml` in this flow's environment"
        ) from failure
    return dict(_FLAVOR_REGISTRY), ExperimentTracker._detect_flavor


def _detect(model: Any, detect: Any) -> str:
    try:
        return str(detect(model))
    except ValueError as failure:
        raise CellError(str(failure)) from failure


def _sample_value(executor: Executor, sample: dict[str, Any] | None) -> Any:
    if not sample:
        return None
    value_ref = str(sample.get("value_ref") or "")
    kind = str(sample.get("kind") or "")
    if not value_ref or not kind:
        return None
    return executor.value(value_ref, kind)


def _sample_inputs(model: Any, sample: Any) -> Any:
    """The head of the training frame, narrowed to the columns the model
    trained on where it says which those were."""
    if sample is None:
        return None
    frame = _as_pandas(sample)
    if frame is None:
        head = getattr(sample, "__getitem__", None)
        return sample[:_SAMPLE_ROWS] if head is not None else None
    names = getattr(model, "feature_names_in_", None)
    if names is not None:
        wanted = [str(name) for name in list(names)]
        if all(name in frame.columns for name in wanted):
            frame = frame[wanted]
    return frame.head(_SAMPLE_ROWS)


def _as_pandas(value: Any) -> Any:
    """A pandas frame, from pandas or polars; None for anything else."""
    if hasattr(value, "columns") and hasattr(value, "head"):
        if hasattr(value, "to_pandas") and not hasattr(value, "iloc"):
            try:
                return value.to_pandas()
            except Exception:
                return None
        return value
    return None
