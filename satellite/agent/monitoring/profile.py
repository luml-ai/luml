"""Read model for the Reference Profile tab.

The baseline the dashboard shows is the same ``reference_profile.json`` the artifact
carries and the worker scores against — the Agent already holds it per deployment
(fetched from the model server on the deploy path). This module translates that raw
profile into the Query API's read model, so the tab shows the exact distributions the
PSI numbers were computed from rather than a separately maintained copy.
"""

from typing import Any
from uuid import UUID

from agent.monitoring.query_store import ReferenceFeatureProfile, ReferenceProfile

_QUANTILE_KEYS = ("q05", "q25", "q50", "q75", "q95")
_NUMERIC_SUMMARY_KEYS = ("mean", "std", "min", "max", "count", "missing")
_CATEGORICAL_SUMMARY_KEYS = ("count", "missing", "n_unique")

PLACEHOLDER = "placeholder"
READY = "ready"


def profile_status(raw: dict[str, Any] | None) -> str:
    """``ready`` only when a profile with real baselines is loaded for the deployment."""
    if not raw:
        return PLACEHOLDER
    if raw.get("profile_status") == PLACEHOLDER:
        return PLACEHOLDER
    return READY if _feature_summaries(raw) else PLACEHOLDER


def build_reference_profile(deployment_id: UUID, raw: dict[str, Any] | None) -> ReferenceProfile | None:
    """Map an artifact reference profile onto the Query API read model.

    Returns ``None`` when there is nothing to show — no profile at all, or one whose
    feature summaries are empty — which the service renders as the tab's empty state.
    """
    if not raw:
        return None
    summaries = _feature_summaries(raw)
    if not summaries:
        return None

    features: dict[str, ReferenceFeatureProfile] = {}
    for name, summary in (summaries.get("numerical_features") or {}).items():
        features[str(name)] = _numeric_feature(str(name), summary)
    for name, summary in (summaries.get("categorical_features") or {}).items():
        features[str(name)] = _categorical_feature(str(name), summary)

    return ReferenceProfile(
        deployment_id=deployment_id,
        status=profile_status(raw),
        baseline_label=_baseline_label(raw),
        features=features,
        document=raw,
    )


def _feature_summaries(raw: dict[str, Any]) -> dict[str, Any]:
    summaries = raw.get("feature_summaries") or {}
    if not isinstance(summaries, dict):
        return {}
    if summaries.get("numerical_features") or summaries.get("categorical_features"):
        return summaries
    return {}


def _baseline_label(raw: dict[str, Any]) -> str | None:
    """Short provenance line under the tab title: task type and reference size."""
    parts: list[str] = []
    task_type = raw.get("task_type")
    if isinstance(task_type, str) and task_type:
        parts.append(task_type)
    samples = raw.get("n_reference_samples")
    if isinstance(samples, int) and samples > 0:
        parts.append(f"{samples} reference samples")
    return " · ".join(parts) if parts else None


def _numeric_feature(name: str, summary: dict[str, Any]) -> ReferenceFeatureProfile:
    stats = {key: value for key in _NUMERIC_SUMMARY_KEYS if _is_number(value := summary.get(key))}
    quantiles = summary.get("quantiles") or {}
    for key in _QUANTILE_KEYS:
        if _is_number(value := quantiles.get(key)):
            stats[key] = float(value)

    return ReferenceFeatureProfile(
        feature=name,
        kind="numeric",
        summary={key: float(value) for key, value in stats.items()},
        bin_edges=_float_list(summary.get("bin_edges")),
        histogram=_float_list(summary.get("probabilities")),
    )


def _categorical_feature(name: str, summary: dict[str, Any]) -> ReferenceFeatureProfile:
    stats = {
        key: float(value)
        for key in _CATEGORICAL_SUMMARY_KEYS
        if _is_number(value := summary.get(key))
    }
    probabilities = summary.get("probabilities")
    categories = summary.get("categories")
    if not isinstance(categories, list):
        categories = sorted(probabilities) if isinstance(probabilities, dict) else []
    labels = [str(category) for category in categories]

    return ReferenceFeatureProfile(
        feature=name,
        kind="categorical",
        summary=stats,
        categories=labels,
        category_probabilities=_category_probabilities(labels, probabilities),
    )


def _category_probabilities(labels: list[str], probabilities: Any) -> list[float]:  # noqa: ANN401
    """Reference share per label, aligned with ``labels``.

    The artifact stores categorical shares as ``{category: probability}``; the read model
    keeps two positional lists, so the mapping is resolved here and unknown labels fall
    back to zero rather than shifting the alignment.
    """
    if isinstance(probabilities, dict):
        return [float(probabilities.get(label, 0.0) or 0.0) for label in labels]
    values = _float_list(probabilities)
    if values is None:
        return [0.0] * len(labels)
    values = values[: len(labels)]
    return values + [0.0] * (len(labels) - len(values))


def _float_list(value: Any) -> list[float] | None:  # noqa: ANN401
    if not isinstance(value, list) or not all(_is_number(item) for item in value):
        return None
    return [float(item) for item in value]


def _is_number(value: Any) -> bool:  # noqa: ANN401
    return isinstance(value, int | float) and not isinstance(value, bool)
