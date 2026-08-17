"""Reading an alert back: what fired, in what units, and where its history lives.

The worker stores an alert under a composite key — ``group:subject`` — because that is
what makes it the same alert across windows. Everything the dashboard needs to *show* it
has to be recovered from that key: which group it belongs to, which feature it is about,
how to phrase the number, and where the value sits inside a materialized window.
"""

from typing import Any

# Data-quality keys are ``feature.check``; a feature name may itself contain dots
# ("petal.length"), so the check is recognized by name rather than by the last dot.
QUALITY_CHECKS = ("missing", "type_mismatch", "range_violation", "unseen_category")

RATIO = "ratio"
MILLISECONDS = "ms"
SIGMA = "sigma"
SCORE = "score"
COUNT = "count"

_CHECK_LABELS = {
    "missing": "Missing rate",
    "type_mismatch": "Type mismatch rate",
    "range_violation": "Range violation rate",
    "unseen_category": "Unseen category rate",
}

_RUNTIME_LABELS = {
    "error_rate": "Error rate",
    "latency_p95": "Latency p95",
    "timeout_count": "Timeouts",
}

_RUNTIME_UNITS = {"latency_p95": MILLISECONDS, "timeout_count": COUNT}

_MULTIVARIATE_LABELS = {
    "centroid_shift": "Centroid shift",
    "mahalanobis_outliers": "Outlier rate",
}


class ParsedAlert:
    """The parts of an alert key, plus how to read and phrase its metric."""

    __slots__ = ("group", "subject", "feature", "check", "label", "unit")

    def __init__(
        self,
        group: str,
        subject: str,
        feature: str | None,
        check: str | None,
        label: str,
        unit: str,
    ) -> None:
        self.group = group
        self.subject = subject
        self.feature = feature
        self.check = check
        self.label = label
        self.unit = unit


def parse_alert_key(metric: str) -> ParsedAlert:
    """Split ``group:subject`` into the parts the dashboard shows.

    An unknown group is kept as-is rather than guessed at: a new metric group should show
    up in the list with a plain label instead of disappearing behind a filter.
    """
    group, _, subject = metric.partition(":")
    if not subject:
        return ParsedAlert(group, "", None, None, group.replace("_", " ").capitalize(), SCORE)

    if group == "data_quality":
        for check in QUALITY_CHECKS:
            suffix = f".{check}"
            if subject.endswith(suffix):
                feature = subject[: -len(suffix)]
                return ParsedAlert(group, subject, feature, check, _CHECK_LABELS[check], RATIO)
        return ParsedAlert(group, subject, subject, None, "Data quality", RATIO)

    if group == "feature_drift":
        return ParsedAlert(group, subject, subject, None, "PSI", SCORE)

    if group == "output_drift":
        return ParsedAlert(group, subject, None, None, "Prediction PSI", SCORE)

    if group == "runtime":
        unit = _RUNTIME_UNITS.get(subject, RATIO)
        label = _RUNTIME_LABELS.get(subject, subject.replace("_", " ").capitalize())
        return ParsedAlert(group, subject, None, None, label, unit)

    if group == "multivariate":
        unit = SIGMA if subject == "centroid_shift" else RATIO
        label = _MULTIVARIATE_LABELS.get(subject, subject.replace("_", " ").capitalize())
        return ParsedAlert(group, subject, None, None, label, unit)

    return ParsedAlert(group, subject, None, None, subject.replace("_", " "), SCORE)


def threshold_key(parsed: ParsedAlert) -> str | None:
    """The reference-profile rule that governs this alert, when the profile can set one.

    Multivariate drift has no rule in the profile — its bounds are properties of the
    Mahalanobis geometry, not of the deployment — so it keeps its built-in ones.
    """
    if parsed.group == "data_quality":
        return f"{parsed.check}_rate" if parsed.check else None
    if parsed.group in ("feature_drift", "output_drift"):
        return "psi"
    if parsed.group == "runtime":
        if parsed.subject == "latency_p95":
            return "latency_p95_ms"
        # Timeouts have no numeric bound to override: any timeout is already a breach.
        return None if parsed.subject == "timeout_count" else parsed.subject
    return None


def format_value(value: float | None, unit: str) -> str:
    """The number as a reader expects it: a rate as a percentage, latency in ms."""
    if value is None:
        return "—"
    if unit == RATIO:
        return f"{value * 100:.1f}%"
    if unit == MILLISECONDS:
        return f"{value:.0f} ms"
    if unit == SIGMA:
        return f"{value:.2f}σ"
    if unit == COUNT:
        return f"{value:.0f}"
    return f"{value:.2f}"


def history_value(parsed: ParsedAlert, values: dict[str, Any]) -> float | None:
    """The alert's own metric inside one materialized window.

    Each metric group lays its window out differently, so the path is chosen by group;
    an unknown shape yields ``None`` and simply leaves a gap in the history line.
    """
    features = values.get("features") or {}
    if parsed.group == "feature_drift":
        return _number((features.get(parsed.subject) or {}).get("psi"))
    if parsed.group == "data_quality":
        if parsed.feature is None or parsed.check is None:
            return None
        entry = features.get(parsed.feature) or {}
        return _number(entry.get(f"{parsed.check}_rate"))
    if parsed.group == "output_drift":
        return _number(values.get("psi"))
    if parsed.group == "runtime":
        return _number(values.get(parsed.subject))
    if parsed.group == "multivariate":
        key = "outlier_rate" if parsed.subject == "mahalanobis_outliers" else parsed.subject
        return _number(values.get(key))
    return None


def _number(value: Any) -> float | None:  # noqa: ANN401
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
