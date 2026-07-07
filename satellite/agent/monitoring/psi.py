import bisect
import math
from collections import Counter
from collections.abc import Iterable, Sequence

from agent.monitoring.models import Severity

# Population Stability Index bands (spec): < warning normal, [warning, critical]
# warning, > critical critical. Shared by feature drift and output drift.
PSI_WARNING = 0.1
PSI_CRITICAL = 0.25
_EPSILON = 1e-6


def psi_severity(
    psi: float, *, warning: float = PSI_WARNING, critical: float = PSI_CRITICAL
) -> tuple[Severity, float] | None:
    """Map a PSI value to ``(severity, breached threshold)``, or ``None`` when normal."""
    if psi > critical:
        return Severity.CRITICAL, critical
    if psi >= warning:
        return Severity.WARNING, warning
    return None


def numerical_psi(
    values: Sequence[float], bin_edges: Sequence[float], ref_probabilities: Sequence[float]
) -> float:
    """PSI of live numeric ``values`` against the reference distribution.

    Values are binned with the reference ``bin_edges`` (values outside the edges fall
    into the nearest edge bin) and their per-bin proportions are compared to the
    reference ``ref_probabilities``.
    """
    return _psi(_bin_proportions(values, bin_edges), ref_probabilities)


def categorical_psi(values: Iterable[str], ref_probabilities: dict[str, float]) -> float:
    """PSI of live categorical ``values`` against a reference ``{category: proportion}``.

    Categories seen live but absent from the reference contribute to the score (their
    reference proportion is zero, so the epsilon floor makes them weigh heavily).
    """
    counts = Counter(values)
    total = sum(counts.values())
    categories = list(ref_probabilities) + [c for c in counts if c not in ref_probabilities]
    live = [counts.get(c, 0) / total if total else 0.0 for c in categories]
    reference = [ref_probabilities.get(c, 0.0) for c in categories]
    return _psi(live, reference)


def has_numerical_reference(summary: dict) -> bool:
    """Whether a summary carries a usable numerical reference distribution for PSI."""
    edges = summary.get("bin_edges")
    probabilities = summary.get("probabilities")
    return (
        isinstance(edges, list)
        and isinstance(probabilities, list)
        and len(edges) >= 2
        and len(probabilities) == len(edges) - 1
    )


def has_categorical_reference(summary: dict) -> bool:
    """Whether a summary carries a usable categorical reference distribution for PSI."""
    probabilities = summary.get("probabilities")
    return isinstance(probabilities, dict) and bool(probabilities)


def _bin_proportions(values: Sequence[float], bin_edges: Sequence[float]) -> list[float]:
    n_bins = len(bin_edges) - 1
    counts = [0] * n_bins
    for value in values:
        index = bisect.bisect_right(bin_edges, value) - 1
        counts[min(max(index, 0), n_bins - 1)] += 1
    total = len(values)
    return [count / total if total else 0.0 for count in counts]


def _psi(live: Sequence[float], reference: Sequence[float]) -> float:
    total = 0.0
    for live_prop, ref_prop in zip(live, reference, strict=True):
        live_p = max(live_prop, _EPSILON)
        ref_p = max(ref_prop, _EPSILON)
        total += (live_p - ref_p) * math.log(live_p / ref_p)
    return total
