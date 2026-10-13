from __future__ import annotations

import importlib
import inspect
import shutil
from pathlib import Path
from typing import Any

from lumlflow_kernel.executor import CellError, Executor

_SAMPLE_ROWS = 5


def export_model(
    executor: Executor,
    *,
    value_ref: str,
    kind: str,
    destination: str,
    samples: list[dict[str, Any]] | None = None,
    flavor: str | None = None,
) -> dict[str, Any]:
    """Write the fnnx bundle for a stored model at `destination`.

    `samples` name the stored frames the cell consumed, in manifest order.
    The head of one gives the flavor its input schema: the first whose
    columns cover the features the model names (`feature_names_in_`), or
    the first frame when the model names none. A model that names its
    features is handed only those columns, so a training frame still
    carrying the target column does not leak it into the signature.
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
    inputs = _sample_inputs(model, _sample_value(executor, model, samples))
    target = Path(destination)
    takes_inputs, needs_inputs = _inputs_parameter(save)
    if inputs is None and needs_inputs:
        raise CellError(
            f"packaging a `{chosen}` model needs a sample of its inputs, and the "
            "cell read no stored frame to take one from. consume the frame the "
            "model trained on as a cell input"
        )
    try:
        if takes_inputs:
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


def _inputs_parameter(save: Any) -> tuple[bool, bool]:
    """Whether the flavor's save function takes a sample, and whether it
    insists on one: sklearn does, xgboost and lightgbm take it or not,
    catboost and langgraph never ask."""
    try:
        parameters = inspect.signature(save).parameters
    except (TypeError, ValueError):
        return True, False
    parameter = parameters.get("inputs")
    if parameter is None:
        return False, False
    return True, parameter.default is inspect.Parameter.empty


def _sample_value(
    executor: Executor, model: Any, samples: list[dict[str, Any]] | None
) -> Any:
    loaded: list[Any] = []
    for sample in samples or []:
        value_ref = str(sample.get("value_ref") or "")
        kind = str(sample.get("kind") or "")
        if not value_ref or not kind:
            continue
        loaded.append(executor.value(value_ref, kind))
    if not loaded:
        return None
    names = getattr(model, "feature_names_in_", None)
    if names is not None:
        wanted = [str(name) for name in list(names)]
        for value in loaded:
            frame = _as_pandas(value)
            if frame is not None and all(name in frame.columns for name in wanted):
                return value
    return loaded[0]


def _sample_inputs(model: Any, sample: Any) -> Any:
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
    if hasattr(value, "columns") and hasattr(value, "head"):
        if hasattr(value, "to_pandas") and not hasattr(value, "iloc"):
            try:
                return value.to_pandas()
            except Exception:
                return None
        return value
    return None
