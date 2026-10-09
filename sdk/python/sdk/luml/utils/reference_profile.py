"""Reference-profile computation for monitoring baselines.

This module is the single source of truth for the reference profile that the
monitoring worker compares live inference data against. It is deliberately
dependency-light — it imports only numpy, scikit-learn, and pandas and must never
import ``luml``, ``fnnx``, or ``falcon`` — so a byte-identical copy can be vendored
into the Pyodide web worker.

Everything it returns is plain JSON (native numbers, lists, strings, dicts) so the
profile round-trips identically through the SDK (CPython) and the browser toolchain
with no custom encoders.
"""

from collections.abc import Callable, Mapping
from typing import Any, Literal

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

TaskType = Literal["regression", "classification", "forecasting"]

DEFAULT_BINS = 10

DEFAULT_EXPLAINED_VARIANCE = 0.90

PROJECTION_SAMPLE = 400

PROFILE_STATUS_READY = "ready"

_QUANTILE_LEVELS: dict[str, float] = {
    "q05": 0.05,
    "q25": 0.25,
    "q50": 0.50,
    "q75": 0.75,
    "q95": 0.95,
}


def compute_feature_summaries(
    features: Any,  # noqa: ANN401
    *,
    feature_names: list[str] | None = None,
    categorical_features: Mapping[str, list[str]] | None = None,
    bins: int = DEFAULT_BINS,
) -> dict[str, dict[str, Any]]:
    """Summarize each training feature into its numerical or categorical group.

    A column is numerical when its dtype is numeric (and not boolean) and it is not
    named in ``categorical_features``; otherwise it is categorical. Column position is
    1-indexed over the full input order so numerical and categorical features share a
    single position space.
    """
    frame = _as_frame(features, feature_names)
    overrides = {
        str(name): [str(c) for c in categories]
        for name, categories in (categorical_features or {}).items()
    }

    numerical: dict[str, Any] = {}
    categorical: dict[str, Any] = {}
    for position, column in enumerate(frame.columns, start=1):
        name = str(column)
        series = frame[column]
        if name in overrides:
            categorical[name] = _categorical_summary(series, position, overrides[name])
        elif _is_numerical(series):
            numerical[name] = _numerical_summary(series, position, bins)
        else:
            categorical[name] = _categorical_summary(series, position, None)

    return {"numerical_features": numerical, "categorical_features": categorical}


def compute_output_summaries(
    predictions: Any,  # noqa: ANN401
    task_type: TaskType,
    *,
    output_names: list[str] | None = None,
    scores: Mapping[str, Any] | None = None,
    bins: int = DEFAULT_BINS,
) -> dict[str, dict[str, Any]]:
    """Summarize model predictions under the group implied by the task type.

    Regression predictions land under ``numerical_outputs`` and classification
    predictions (predicted-class proportions) under ``categorical_outputs``. Any
    ``scores`` (e.g. class probabilities) are additionally summarized numerically
    under ``numerical_outputs``.
    """
    frame = _predictions_frame(predictions, output_names)
    summaries: dict[str, dict[str, Any]] = {}

    if task_type in ("regression", "forecasting"):
        summaries["numerical_outputs"] = {
            str(column): _numerical_summary(frame[column], position, bins)
            for position, column in enumerate(frame.columns, start=1)
        }
    elif task_type == "classification":
        summaries["categorical_outputs"] = {
            str(column): _categorical_summary(frame[column], position, None)
            for position, column in enumerate(frame.columns, start=1)
        }
    else:
        raise ValueError(f"Unknown task type: {task_type!r}")

    if scores:
        _add_score_summaries(summaries, scores, bins)

    return summaries


def compute_pca_profile(
    features: Any,  # noqa: ANN401
    *,
    feature_names: list[str] | None = None,
    categorical_features: Mapping[str, list[str]] | None = None,
    random_state: int = 0,
    explained_variance: float = DEFAULT_EXPLAINED_VARIANCE,
) -> dict[str, Any]:
    """Fit a scaler + PCA on the numerical features and summarize the score cloud.

    Only numerical features participate (matching how multivariate drift is computed);
    categorical columns are excluded. The scaler and PCA parameters are stored as
    nested lists of native numbers, and the mean vector and covariance matrix of the
    training PCA scores are stored as ``reference_distribution`` — the reference the
    worker measures Mahalanobis distance against. Rows with any missing numerical value
    are dropped before fitting. Returns an empty dict when there are no numerical
    features (or too few rows to fit), which the worker reads defensively.

    Components are truncated at the smallest count reaching ``explained_variance``
    of the training variance: directions carrying almost nothing add noise to the
    distance and, being nearly flat, make the covariance hard to invert. A model with
    two numerical features therefore keeps both — the plane the dashboard draws needs
    two.
    """
    frame = _as_frame(features, feature_names)
    numerical_names = _numerical_feature_names(
        frame, _override_names(categorical_features)
    )
    if not numerical_names:
        return {}

    matrix = frame[numerical_names].to_numpy(dtype=float)
    matrix = matrix[~np.isnan(matrix).any(axis=1)]
    n_samples, n_features = matrix.shape
    if n_samples < 2:
        return {}

    scaler = StandardScaler().fit(matrix)
    scaled = scaler.transform(matrix)
    pca = PCA(n_components=min(n_features, n_samples), random_state=random_state)
    pca.fit(scaled)

    keep = _components_for_variance(pca.explained_variance_ratio_, explained_variance)
    components = pca.components_[:keep]
    scores = (scaled - pca.mean_) @ components.T

    return {
        "scaler": {
            "mean_": _to_vector(scaler.mean_),
            "scale_": _to_vector(scaler.scale_),
            "var_": _to_vector(scaler.var_),
            "n_features": n_features,
        },
        "pca": {
            "n_components": keep,
            "n_features": n_features,
            "components": _to_matrix(components),
            "mean_": _to_vector(pca.mean_),
            "feature_names": numerical_names,
            "explained_variance_ratio": _to_vector(
                pca.explained_variance_ratio_[:keep]
            ),
        },
        "reference_projection": _thin(scores[:, :2], PROJECTION_SAMPLE),
        "reference_distribution": {
            "mean": _to_vector(scores.mean(axis=0)),
            "covariance": _to_matrix(np.cov(scores, rowvar=False)),
            "n_samples": n_samples,
            "n_components": keep,
        },
    }


def _thin(points: np.ndarray, limit: int) -> list[list[float]]:
    """Evenly spaced sample of ``points``, at most ``limit`` of them.

    Deterministic (a stride, not a random draw) so the profile stays reproducible, and
    capped so a million-row training set does not bloat the artifact.
    """
    if points.ndim != 2 or points.shape[1] < 2 or points.shape[0] == 0:
        return []
    stride = max(1, points.shape[0] // limit)
    return _to_matrix(points[::stride][:limit])


def _components_for_variance(ratios: np.ndarray, target: float) -> int:
    """Return the component count needed to reach the target variance."""
    cumulative = np.cumsum(ratios)
    reached = int(np.searchsorted(cumulative, min(target, float(cumulative[-1]))))
    return min(len(ratios), reached + 1)


def build_reference_profile(
    features: Any,  # noqa: ANN401
    task_type: TaskType,
    predict: Callable[[Any], Any],
    *,
    feature_names: list[str] | None = None,
    categorical_features: Mapping[str, list[str]] | None = None,
    output_names: list[str] | None = None,
    predict_proba: Callable[[Any], Any] | None = None,
    class_names: list[str] | None = None,
    horizons: list[str] | None = None,
    bins: int = DEFAULT_BINS,
) -> dict[str, Any]:
    """Assemble the full reference profile: feature + output summaries and PCA profile.

    ``predict`` is the way to obtain predictions from the model; when
    ``predict_proba`` is supplied for a classification task, its per-sample confidence
    (the maximum class probability) is summarized as an extra numerical score output.

    Besides the summaries the profile declares what the monitoring runtime keys off:
    ``task_type`` (which output-drift adapter applies), ``output_summary`` (the single
    monitored prediction — its name, kind, and reference distribution, picked out of
    ``output_summaries``), and ``profile_status`` (``ready``: these baselines came from
    real reference data, not a placeholder).
    """
    feature_summaries = compute_feature_summaries(
        features,
        feature_names=feature_names,
        categorical_features=categorical_features,
        bins=bins,
    )

    scores: dict[str, Any] | None = None
    probability_summary: dict[str, Any] | None = None
    if task_type == "classification" and predict_proba is not None:
        proba = np.asarray(predict_proba(features), dtype=float)
        scores = {"y_score": _confidence_scores(proba)}
        probability_summary = _probability_summary(proba, class_names, bins)

    output_summaries = compute_output_summaries(
        predict(features),
        task_type,
        output_names=output_names,
        scores=scores,
        bins=bins,
    )

    pca_profile = compute_pca_profile(
        features,
        feature_names=feature_names,
        categorical_features=categorical_features,
    )

    profile = {
        "profile_status": PROFILE_STATUS_READY,
        "task_type": task_type,
        "feature_summaries": feature_summaries,
        "output_summaries": output_summaries,
        "output_summary": _primary_output_summary(output_summaries, task_type),
        "pca_profile": pca_profile,
    }
    if probability_summary is not None:
        profile["probability_summary"] = probability_summary
    if task_type == "forecasting" and horizons:
        profile["forecast_summary"] = {"name": "y", "horizons": list(horizons)}
    return profile


def _primary_output_summary(
    output_summaries: dict[str, dict[str, Any]], task_type: TaskType
) -> dict[str, Any]:
    """The monitored prediction, flattened out of the per-group ``output_summaries``.

    Output drift scores one prediction against one reference distribution, so the
    profile names it explicitly instead of leaving the runtime to guess a group and a
    key. A regression profile points at the first numerical output (score columns are
    appended after the predictions, so the prediction stays first); a classification
    profile points at the first categorical output — its predicted-class proportions.
    """
    numeric = task_type in ("regression", "forecasting")
    group = "numerical_outputs" if numeric else "categorical_outputs"
    kind = "numerical" if numeric else "categorical"
    summaries = output_summaries.get(group) or {}
    if not summaries:
        return {}
    name, summary = next(iter(summaries.items()))
    return {"name": name, "type": kind, "summary": summary}


def _numerical_summary(series: pd.Series, position: int, bins: int) -> dict[str, Any]:
    total = int(series.shape[0])
    values = series.to_numpy(dtype=float)
    values = values[~np.isnan(values)]
    count = int(values.size)
    missing = total - count
    if count == 0:
        return _empty_numerical_summary(position, missing)

    frequencies, edges = np.histogram(values, bins=bins)
    counts = [int(c) for c in frequencies]
    edge_list = [float(e) for e in edges]
    centres = [
        (edge_list[i] + edge_list[i + 1]) / 2.0 for i in range(len(edge_list) - 1)
    ]

    return {
        "position": position,
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "quantiles": {
            name: float(np.quantile(values, q)) for name, q in _QUANTILE_LEVELS.items()
        },
        "bin_edges": edge_list,
        "bin_centres": centres,
        "frequencies": counts,
        "probabilities": [c / count for c in counts],
        "count": count,
        "missing": missing,
    }


def _empty_numerical_summary(position: int, missing: int) -> dict[str, Any]:
    return {
        "position": position,
        "mean": 0.0,
        "std": 0.0,
        "min": 0.0,
        "max": 0.0,
        "quantiles": dict.fromkeys(_QUANTILE_LEVELS, 0.0),
        "bin_edges": [],
        "bin_centres": [],
        "frequencies": [],
        "probabilities": [],
        "count": 0,
        "missing": missing,
    }


def _categorical_summary(
    series: pd.Series, position: int, categories: list[str] | None
) -> dict[str, Any]:
    missing = int(series.isna().sum())
    present = series.dropna().astype(str)
    count = int(present.shape[0])
    value_counts = present.value_counts()

    if categories is None:
        known = sorted(str(c) for c in value_counts.index)
    else:
        known = [str(c) for c in categories]

    frequencies = [int(value_counts.get(category, 0)) for category in known]
    probabilities = {
        category: (frequency / count if count else 0.0)
        for category, frequency in zip(known, frequencies, strict=True)
    }

    return {
        "position": position,
        "categories": known,
        "frequencies": frequencies,
        "probabilities": probabilities,
        "count": count,
        "missing": missing,
        "n_unique": len(known),
    }


def _add_score_summaries(
    summaries: dict[str, dict[str, Any]],
    scores: Mapping[str, Any],
    bins: int,
) -> None:
    numerical = summaries.setdefault("numerical_outputs", {})
    start = len(numerical)
    for offset, (name, values) in enumerate(scores.items(), start=1):
        series = pd.Series(np.asarray(values, dtype=float).ravel())
        numerical[str(name)] = _numerical_summary(series, start + offset, bins)


def _as_frame(features: Any, feature_names: list[str] | None) -> pd.DataFrame:  # noqa: ANN401
    if isinstance(features, pd.DataFrame):
        return features
    array = np.asarray(features)
    if array.ndim == 1:
        array = array.reshape(-1, 1)
    if array.ndim != 2:
        raise ValueError("features must be 1D or 2D")
    names = feature_names or [f"x{i}" for i in range(array.shape[1])]
    return pd.DataFrame(array, columns=names)


def _predictions_frame(
    predictions: Any,  # noqa: ANN401
    output_names: list[str] | None,
) -> pd.DataFrame:
    if isinstance(predictions, pd.DataFrame):
        return predictions
    array = np.asarray(predictions)
    if array.ndim == 1:
        array = array.reshape(-1, 1)
    if array.ndim != 2:
        raise ValueError("predictions must be 1D or 2D")

    if output_names is not None:
        names = output_names
    elif array.shape[1] == 1:
        names = ["y_pred"]
    else:
        names = [f"y_pred_{i}" for i in range(array.shape[1])]
    return pd.DataFrame(array, columns=names)


def _is_numerical(series: pd.Series) -> bool:
    dtype = series.dtype
    if isinstance(dtype, pd.CategoricalDtype):
        return False
    return bool(
        pd.api.types.is_numeric_dtype(dtype) and not pd.api.types.is_bool_dtype(dtype)
    )


def _override_names(categorical_features: Mapping[str, list[str]] | None) -> set[str]:
    return {str(name) for name in (categorical_features or {})}


def _numerical_feature_names(
    frame: pd.DataFrame, override_names: set[str]
) -> list[str]:
    """Ordered numerical columns, applying the same classification as the summaries."""
    return [
        str(column)
        for column in frame.columns
        if str(column) not in override_names and _is_numerical(frame[column])
    ]


def _to_vector(array: np.ndarray) -> list[float]:
    return [float(value) for value in np.asarray(array, dtype=float).ravel()]


def _to_matrix(array: np.ndarray) -> list[list[float]]:
    matrix = np.atleast_2d(np.asarray(array, dtype=float))
    return [[float(value) for value in row] for row in matrix]


BINARY_DECISION_THRESHOLD = 0.5
THRESHOLD_BAND = 0.05


def _probability_summary(
    proba: np.ndarray, class_names: list[str] | None, bins: int
) -> dict[str, Any]:
    """Per-class probability baselines, and the decision-boundary rate for binary tasks.

    For every class: a numerical summary of that class's probability across the training
    rows. A binary task additionally records how often training predictions sat near the
    decision threshold, so the live "coin-flip zone" rate has a calibrated reference.
    """
    if proba.ndim == 1:
        proba = np.column_stack([1.0 - proba, proba])
    n_classes = proba.shape[1]
    names = (
        [str(name) for name in class_names]
        if class_names is not None and len(class_names) == n_classes
        else [f"class_{i}" for i in range(n_classes)]
    )
    summary: dict[str, Any] = {
        "name": "y_proba",
        "classes": names,
        "per_class": {
            name: _numerical_summary(pd.Series(proba[:, i]), i + 1, bins)
            for i, name in enumerate(names)
        },
    }
    if n_classes == 2:
        positive = proba[:, 1]
        near = np.abs(positive - BINARY_DECISION_THRESHOLD) < THRESHOLD_BAND
        summary["positive_class"] = names[1]
        summary["decision_threshold"] = BINARY_DECISION_THRESHOLD
        summary["threshold_band"] = THRESHOLD_BAND
        summary["reference_near_threshold_rate"] = float(near.mean())
    return summary


def _confidence_scores(proba: Any) -> np.ndarray:  # noqa: ANN401
    array = np.asarray(proba, dtype=float)
    if array.ndim == 1:
        return array
    return array.max(axis=1)
