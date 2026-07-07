import math
from dataclasses import dataclass
from typing import Any

from agent.monitoring.metric import Metric, MetricInput
from agent.monitoring.models import (
    AlertSignal,
    DeploymentContext,
    InferenceEvent,
    MetricComputation,
    Severity,
    worst_severity,
)

_EMPTY = MetricComputation(values={}, severity=Severity.NORMAL, signals=[])


@dataclass(frozen=True)
class _PCAModel:
    """The parts of the PCA profile the metric needs, validated and aligned by order."""

    feature_names: list[str]
    scaler_mean: list[float]
    scaler_scale: list[float]
    pca_mean: list[float]
    components: list[list[float]]
    ref_mean: float
    ref_std: float


class MultivariateDriftMetric(Metric):
    """Multivariate drift via PCA reconstruction error on the numerical features.

    For the live window each row's numerical features are standardized with the stored
    scaler, projected onto the stored principal components and reconstructed back; the
    reconstruction error is the Euclidean distance between the standardized row and its
    reconstruction. The window mean error is compared to the training baseline: a value
    more than ``sigma`` reference standard deviations above the reference mean means the
    live data no longer matches the correlation structure the PCA learned, which
    per-feature drift can miss. Requires the PCA profile; a malformed profile or a window
    with no complete numerical rows is skipped cleanly.
    """

    metric = "multivariate"

    def __init__(self, *, sigma: float = 3.0) -> None:
        self._sigma = sigma

    def applies(self, context: DeploymentContext) -> bool:
        return context.has_events and context.has_pca_profile

    def compute(self, data: MetricInput) -> MetricComputation:
        model = _parse_pca_profile((data.profile or {}).get("pca_profile") or {})
        if model is None:
            return _EMPTY
        rows = _numerical_rows(data.events, model.feature_names)
        if not rows:
            return _EMPTY

        errors = _reconstruction_errors(rows, model)
        mean_error = sum(errors) / len(errors)
        threshold = model.ref_mean + self._sigma * model.ref_std

        values: dict[str, Any] = {
            "mean_reconstruction_error": mean_error,
            "threshold": threshold,
            "reference_mean": model.ref_mean,
            "reference_std": model.ref_std,
            "count": len(rows),
        }
        signals: list[AlertSignal] = []
        if mean_error > threshold:
            signals.append(
                AlertSignal("reconstruction_error", mean_error, threshold, Severity.CRITICAL)
            )
        severity = worst_severity(signal.severity for signal in signals)
        return MetricComputation(values=values, severity=severity, signals=signals)


def _reconstruction_errors(rows: list[list[float]], model: _PCAModel) -> list[float]:
    """Per-row PCA reconstruction error in standardized space (sklearn convention)."""
    n_features = len(model.feature_names)
    errors: list[float] = []
    for row in rows:
        scaled = [
            (v - m) / s for v, m, s in zip(row, model.scaler_mean, model.scaler_scale, strict=True)
        ]
        centered = [x - m for x, m in zip(scaled, model.pca_mean, strict=True)]
        scores = [
            sum(c * x for c, x in zip(component, centered, strict=True))
            for component in model.components
        ]
        reconstructed = list(model.pca_mean)
        for score, component in zip(scores, model.components, strict=True):
            for j in range(n_features):
                reconstructed[j] += score * component[j]
        errors.append(
            math.sqrt(sum((a - b) ** 2 for a, b in zip(scaled, reconstructed, strict=True)))
        )
    return errors


def _numerical_rows(events: list[InferenceEvent], feature_names: list[str]) -> list[list[float]]:
    """Rows of the required numerical features, in profile order; incomplete rows dropped."""
    rows: list[list[float]] = []
    for event in events:
        inputs = event.inputs or {}
        row: list[float] = []
        for name in feature_names:
            value = inputs.get(name)
            if not _is_number(value) or math.isnan(value):
                break
            row.append(float(value))
        else:
            rows.append(row)
    return rows


def _parse_pca_profile(pca_profile: dict) -> _PCAModel | None:
    pca = pca_profile.get("pca") or {}
    scaler = pca_profile.get("scaler") or {}
    reference = pca_profile.get("reconstruction_error_reference") or {}

    feature_names = _str_list(pca.get("feature_names"))
    if feature_names is None:
        return None
    n = len(feature_names)

    scaler_mean = _number_list(scaler.get("mean_"), n)
    scaler_scale = _number_list(scaler.get("scale_"), n)
    pca_mean = _number_list(pca.get("mean_"), n)
    components = _component_matrix(pca.get("components"), n)
    ref_mean = reference.get("mean")
    ref_std = reference.get("std")

    if (
        scaler_mean is None
        or scaler_scale is None
        or pca_mean is None
        or components is None
        or not _is_number(ref_mean)
        or not _is_number(ref_std)
        or any(scale == 0.0 for scale in scaler_scale)
    ):
        return None

    return _PCAModel(
        feature_names=feature_names,
        scaler_mean=scaler_mean,
        scaler_scale=scaler_scale,
        pca_mean=pca_mean,
        components=components,
        ref_mean=float(ref_mean),
        ref_std=float(ref_std),
    )


def _component_matrix(value: Any, n_features: int) -> list[list[float]] | None:  # noqa: ANN401
    if not isinstance(value, list) or not value:
        return None
    matrix: list[list[float]] = []
    for component in value:
        row = _number_list(component, n_features)
        if row is None:
            return None
        matrix.append(row)
    return matrix


def _number_list(value: Any, length: int) -> list[float] | None:  # noqa: ANN401
    if not isinstance(value, list) or len(value) != length:
        return None
    if not all(_is_number(item) for item in value):
        return None
    return [float(item) for item in value]


def _str_list(value: Any) -> list[str] | None:  # noqa: ANN401
    if not isinstance(value, list) or not value:
        return None
    if not all(isinstance(item, str) for item in value):
        return None
    return list(value)


def _is_number(value: Any) -> bool:  # noqa: ANN401
    return isinstance(value, int | float) and not isinstance(value, bool)
