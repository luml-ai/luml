import math
from dataclasses import dataclass, field
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

# Scatter points sent to the dashboard per side; enough to read a cloud, small in JSON.
_PROJECTION_LIMIT = 300

# A row counts as an outlier when its squared distance exceeds the chi-square quantile the
# reference itself would exceed only 1% of the time, so a healthy window sits near 1%.
_OUTLIER_QUANTILE = 0.99
_Z_OUTLIER = 2.3263478740408408  # standard normal quantile at 0.99

# Share of outlying rows that counts as drift. Well above the 1% the reference produces,
# so ordinary sampling noise does not raise an alert.
_WARNING_RATE = 0.05
_CRITICAL_RATE = 0.10

# How far the live centre may sit from the reference centre, in reference sigmas.
_WARNING_SHIFT = 1.0
_CRITICAL_SHIFT = 2.0

# 95% confidence ellipse of a 2D Gaussian: chi-square(2) at 0.95 is 5.991.
_ELLIPSE_SCALE = math.sqrt(5.991)
_ELLIPSE_POINTS = 48


@dataclass(frozen=True)
class _PCAModel:
    """The parts of the PCA profile the metric needs, validated and aligned by order."""

    feature_names: list[str]
    scaler_mean: list[float]
    scaler_scale: list[float]
    pca_mean: list[float]
    components: list[list[float]]
    reference_mean: list[float]
    covariance: list[list[float]]  # covariance of the training PCA scores
    precision: list[list[float]]  # its inverse
    explained_variance: list[float] = field(default_factory=list)
    reference_projection: list[list[float]] = field(default_factory=list)

    @property
    def n_components(self) -> int:
        return len(self.reference_mean)


class MultivariateDriftMetric(Metric):
    """Multivariate drift as a comparison of two Gaussians in the training PCA space.

    Training leaves behind a cloud of PCA scores, summarized in the profile as a mean
    vector and a covariance matrix (``reference_distribution``). Each live row is
    standardized, projected onto the same components, and the window is summarized the
    same way — so the question becomes how far the live Gaussian has moved from the
    reference one. Three numbers answer it, because they fail in different ways:

    * **centroid shift** — Mahalanobis distance between the two centres, in reference
      sigmas: the whole population has moved.
    * **dispersion ratio** — generalized variance of the live cloud over the reference
      one, per component: the population is the same on average but wider or narrower,
      which a centroid shift cannot see.
    * **outlier rate** — share of individual rows past the 99th percentile of the
      reference chi-square: a handful of extreme calls that barely move a centroid of
      three hundred rows.

    Per-feature PSI misses all three when the marginals stay put and only the joint
    structure changes. Requires the PCA profile; a malformed profile (missing parts, a
    covariance that cannot be inverted) or a window with no complete numerical rows is
    skipped cleanly.
    """

    metric = "multivariate"

    def __init__(
        self,
        *,
        warning_rate: float = _WARNING_RATE,
        critical_rate: float = _CRITICAL_RATE,
        warning_shift: float = _WARNING_SHIFT,
        critical_shift: float = _CRITICAL_SHIFT,
    ) -> None:
        self._warning_rate = warning_rate
        self._critical_rate = critical_rate
        self._warning_shift = warning_shift
        self._critical_shift = critical_shift

    def applies(self, context: DeploymentContext) -> bool:
        return context.has_events and context.has_pca_profile

    def compute(self, data: MetricInput) -> MetricComputation:
        model = _parse_pca_profile((data.profile or {}).get("pca_profile") or {})
        if model is None:
            return _EMPTY
        rows = _numerical_rows(data.events, model.feature_names)
        if not rows:
            return _EMPTY

        scores = [_scores(row, model) for row in rows]
        squared = [_mahalanobis_squared(score, model) for score in scores]
        distances = [math.sqrt(value) for value in squared]

        limit = _chi_square_quantile(model.n_components, _Z_OUTLIER)
        outliers = [value > limit for value in squared]
        outlier_rate = sum(outliers) / len(squared)

        # The live Gaussian describes the bulk: a couple of rows with a feature far out of
        # range would otherwise inflate its covariance by orders of magnitude, and both the
        # dispersion ratio and the drawn ellipse would describe those rows instead of the
        # traffic. The tail is not swept under the rug — it is what outlier_rate reports.
        bulk = [score for score, out in zip(scores, outliers, strict=True) if not out]
        if len(bulk) < 2:
            bulk = scores
        live_mean = _column_means(bulk)
        live_covariance = _covariance(bulk, live_mean)
        delta = [live - ref for live, ref in zip(live_mean, model.reference_mean, strict=True)]
        centroid_shift = math.sqrt(max(_quadratic_form(delta, model.precision), 0.0))

        values: dict[str, Any] = {
            "centroid_shift": centroid_shift,
            "dispersion_ratio": _dispersion_ratio(live_covariance, model.covariance),
            "outlier_rate": outlier_rate,
            "outlier_threshold": math.sqrt(limit),
            "mean_distance": sum(distances) / len(distances),
            "p95_distance": _quantile(sorted(distances), 0.95),
            "count": len(rows),
            # What the dashboard panel draws: the headline number, both Gaussians as 95%
            # ellipses in the PC1 × PC2 plane, and the live rows themselves.
            "shift_metric": "centroid shift",
            "shift_value": centroid_shift,
            "shift_unit": "σ",
            "explained_variance": model.explained_variance,
            "ellipses": {
                "reference": _ellipse(model.reference_mean, model.covariance),
                "current": _ellipse(live_mean, live_covariance),
            },
            "projection": {
                "reference": model.reference_projection,
                "current": _projection(scores),
            },
        }

        signals: list[AlertSignal] = []
        shift_severity = _threshold_severity(
            centroid_shift, self._warning_shift, self._critical_shift
        )
        if shift_severity is not None:
            threshold = (
                self._critical_shift
                if shift_severity is Severity.CRITICAL
                else self._warning_shift
            )
            signals.append(
                AlertSignal("centroid_shift", centroid_shift, threshold, shift_severity)
            )

        outlier_severity = _threshold_severity(
            outlier_rate, self._warning_rate, self._critical_rate
        )
        if outlier_severity is not None:
            threshold = (
                self._critical_rate
                if outlier_severity is Severity.CRITICAL
                else self._warning_rate
            )
            signals.append(
                AlertSignal("mahalanobis_outliers", outlier_rate, threshold, outlier_severity)
            )

        return MetricComputation(
            values=values,
            severity=worst_severity(signal.severity for signal in signals),
            signals=signals,
        )


def _threshold_severity(value: float, warning: float, critical: float) -> Severity | None:
    if value > critical:
        return Severity.CRITICAL
    if value > warning:
        return Severity.WARNING
    return None


def _column_means(rows: list[list[float]]) -> list[float]:
    n = len(rows)
    return [sum(row[i] for row in rows) / n for i in range(len(rows[0]))]


def _covariance(rows: list[list[float]], mean: list[float]) -> list[list[float]]:
    """Sample covariance of the window's scores; a single row has no spread to report."""
    k = len(mean)
    n = len(rows)
    if n < 2:
        return [[0.0] * k for _ in range(k)]
    matrix = [[0.0] * k for _ in range(k)]
    for row in rows:
        delta = [value - centre for value, centre in zip(row, mean, strict=True)]
        for i in range(k):
            for j in range(i, k):
                matrix[i][j] += delta[i] * delta[j]
    for i in range(k):
        for j in range(i, k):
            value = matrix[i][j] / (n - 1)
            matrix[i][j] = value
            matrix[j][i] = value
    return matrix


def _quadratic_form(vector: list[float], matrix: list[list[float]]) -> float:
    return sum(
        vector[i] * sum(value * v for value, v in zip(row, vector, strict=True))
        for i, row in enumerate(matrix)
    )


def _dispersion_ratio(live: list[list[float]], reference: list[list[float]]) -> float | None:
    """How much wider the live cloud is, per component: (det Σ_live / det Σ_ref)^(1/k).

    Computed through log-determinants — with a dozen components the raw determinants
    overflow or vanish long before the ratio does.
    """
    k = len(reference)
    live_log = _log_determinant(live)
    reference_log = _log_determinant(reference)
    if live_log is None or reference_log is None or k == 0:
        return None
    return math.exp((live_log - reference_log) / k)


def _log_determinant(matrix: list[list[float]]) -> float | None:
    """Log of |det| via Gaussian elimination; ``None`` when the matrix is singular."""
    n = len(matrix)
    work = [list(row) for row in matrix]
    total = 0.0
    for column in range(n):
        pivot_row = max(range(column, n), key=lambda r: abs(work[r][column]))
        pivot = work[pivot_row][column]
        if abs(pivot) < 1e-12:
            return None
        work[column], work[pivot_row] = work[pivot_row], work[column]
        total += math.log(abs(pivot))
        for row in range(column + 1, n):
            factor = work[row][column] / work[column][column]
            if factor:
                work[row] = [
                    value - factor * pivot_value
                    for value, pivot_value in zip(work[row], work[column], strict=True)
                ]
    return total


def _ellipse(mean: list[float], covariance: list[list[float]]) -> list[list[float]]:
    """95% confidence ellipse of the PC1 × PC2 marginal, as a closed polygon.

    Two Gaussians are compared by their shape, not by their sample points, so the panel
    draws these rather than needing every training row to travel in the profile.
    """
    if len(mean) < 2 or len(covariance) < 2 or len(covariance[0]) < 2:
        return []
    a, b, d = covariance[0][0], covariance[0][1], covariance[1][1]
    trace, det = a + d, a * d - b * b
    gap = math.sqrt(max(trace * trace / 4.0 - det, 0.0))
    major, minor = trace / 2.0 + gap, trace / 2.0 - gap
    if major <= 0.0:
        return []
    minor = max(minor, 0.0)
    angle = 0.5 * math.atan2(2.0 * b, a - d)
    cos, sin = math.cos(angle), math.sin(angle)
    width, height = _ELLIPSE_SCALE * math.sqrt(major), _ELLIPSE_SCALE * math.sqrt(minor)

    polygon: list[list[float]] = []
    for i in range(_ELLIPSE_POINTS + 1):
        theta = 2.0 * math.pi * i / _ELLIPSE_POINTS
        x, y = width * math.cos(theta), height * math.sin(theta)
        polygon.append([mean[0] + x * cos - y * sin, mean[1] + x * sin + y * cos])
    return polygon


def _scores(row: list[float], model: _PCAModel) -> list[float]:
    """One row in the training PCA space: standardize, centre, project."""
    scaled = [
        (v - m) / s for v, m, s in zip(row, model.scaler_mean, model.scaler_scale, strict=True)
    ]
    centered = [x - m for x, m in zip(scaled, model.pca_mean, strict=True)]
    return [
        sum(c * x for c, x in zip(component, centered, strict=True))
        for component in model.components
    ]


def _mahalanobis_squared(scores: list[float], model: _PCAModel) -> float:
    delta = [s - m for s, m in zip(scores, model.reference_mean, strict=True)]
    total = 0.0
    for i, row in enumerate(model.precision):
        total += delta[i] * sum(value * d for value, d in zip(row, delta, strict=True))
    return max(total, 0.0)


def _chi_square_quantile(dof: int, z: float) -> float:
    """Wilson–Hilferty approximation of a chi-square quantile — no SciPy in the Agent."""
    if dof <= 0:
        return math.inf
    term = 1.0 - 2.0 / (9.0 * dof) + z * math.sqrt(2.0 / (9.0 * dof))
    return dof * term**3


def _quantile(ordered: list[float], q: float) -> float:
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[index]


def _projection(scores: list[list[float]]) -> list[list[float]]:
    """The live window in the PC1 × PC2 plane, capped so the payload stays small."""
    if not scores or len(scores[0]) < 2:
        return []
    step = max(1, len(scores) // _PROJECTION_LIMIT)
    return [[point[0], point[1]] for point in scores[::step][:_PROJECTION_LIMIT]]


def _numerical_rows(events: list[InferenceEvent], feature_names: list[str]) -> list[list[float]]:
    """Rows of the required numerical features, in profile order; incomplete rows dropped.

    One event may carry a batch: the recorded inputs are ``{feature: [observation, ...]}``
    (a scalar counts as a batch of one), and the per-feature lists are positionally
    aligned, so observation ``i`` of every feature belongs to the same row. A distance
    needs a complete row, so a row missing or mistyping any feature is skipped rather than
    zero-filled.
    """
    rows: list[list[float]] = []
    for event in events:
        inputs = event.inputs or {}
        columns = [_observations(inputs.get(name)) for name in feature_names]
        for observations in zip(*columns, strict=False):
            row: list[float] = []
            for value in observations:
                if not _is_number(value) or math.isnan(value):
                    break
                row.append(float(value))
            else:
                rows.append(row)
    return rows


def _observations(raw: Any) -> list[Any]:  # noqa: ANN401
    """Per-observation values of one feature; a scalar is a batch of one."""
    return raw if isinstance(raw, list) else [raw]


def _parse_pca_profile(pca_profile: dict) -> _PCAModel | None:
    pca = pca_profile.get("pca") or {}
    scaler = pca_profile.get("scaler") or {}
    reference = pca_profile.get("reference_distribution") or {}

    feature_names = _str_list(pca.get("feature_names"))
    if feature_names is None:
        return None
    n = len(feature_names)

    scaler_mean = _number_list(scaler.get("mean_"), n)
    scaler_scale = _number_list(scaler.get("scale_"), n)
    pca_mean = _number_list(pca.get("mean_"), n)
    components = _component_matrix(pca.get("components"), n)
    if (
        scaler_mean is None
        or scaler_scale is None
        or pca_mean is None
        or components is None
        or any(scale == 0.0 for scale in scaler_scale)
    ):
        return None

    k = len(components)
    reference_mean = _number_list(reference.get("mean"), k)
    covariance = _square_matrix(reference.get("covariance"), k)
    if reference_mean is None or covariance is None:
        return None
    # A component with no spread has no scale to measure a distance in; that reference
    # cannot answer "how far is this row", so the metric steps aside instead of dividing
    # by an all-but-zero variance and calling every window an outlier.
    if any(covariance[i][i] <= 0.0 for i in range(k)):
        return None
    precision = _invert(covariance)
    if precision is None:
        return None

    return _PCAModel(
        feature_names=feature_names,
        scaler_mean=scaler_mean,
        scaler_scale=scaler_scale,
        pca_mean=pca_mean,
        components=components,
        reference_mean=reference_mean,
        covariance=covariance,
        precision=precision,
        explained_variance=_float_list(pca.get("explained_variance_ratio")),
        reference_projection=_point_list(pca_profile.get("reference_projection")),
    )


def _invert(matrix: list[list[float]]) -> list[list[float]] | None:
    """Gauss-Jordan inverse with partial pivoting; ``None`` when the matrix is singular.

    A near-singular covariance (a component with no spread) is nudged by a small ridge
    before giving up, so a degenerate direction costs precision rather than the metric.
    """
    for ridge in (0.0, 1e-9, 1e-6):
        inverted = _invert_once(matrix, ridge)
        if inverted is not None:
            return inverted
    return None


def _invert_once(matrix: list[list[float]], ridge: float) -> list[list[float]] | None:
    n = len(matrix)
    work = [list(row) + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(matrix)]
    for i in range(n):
        work[i][i] += ridge

    for column in range(n):
        pivot_row = max(range(column, n), key=lambda r: abs(work[r][column]))
        if abs(work[pivot_row][column]) < 1e-12:
            return None
        work[column], work[pivot_row] = work[pivot_row], work[column]

        pivot = work[column][column]
        work[column] = [value / pivot for value in work[column]]
        for row in range(n):
            if row == column:
                continue
            factor = work[row][column]
            if factor:
                work[row] = [
                    value - factor * pivot_value
                    for value, pivot_value in zip(work[row], work[column], strict=True)
                ]
    return [row[n:] for row in work]


def _square_matrix(value: Any, size: int) -> list[list[float]] | None:  # noqa: ANN401
    if not isinstance(value, list) or len(value) != size:
        return None
    matrix: list[list[float]] = []
    for row in value:
        parsed = _number_list(row, size)
        if parsed is None:
            return None
        matrix.append(parsed)
    return matrix


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


def _float_list(value: Any) -> list[float]:  # noqa: ANN401
    if not isinstance(value, list):
        return []
    return [float(item) for item in value if _is_number(item)]


def _point_list(value: Any) -> list[list[float]]:  # noqa: ANN401
    """Stored PC1 × PC2 points, keeping only well-formed pairs."""
    if not isinstance(value, list):
        return []
    return [
        [float(point[0]), float(point[1])]
        for point in value
        if isinstance(point, list) and len(point) >= 2 and all(_is_number(v) for v in point[:2])
    ]


def _str_list(value: Any) -> list[str] | None:  # noqa: ANN401
    if not isinstance(value, list) or not value:
        return None
    if not all(isinstance(item, str) for item in value):
        return None
    return list(value)


def _is_number(value: Any) -> bool:  # noqa: ANN401
    return isinstance(value, int | float) and not isinstance(value, bool)
