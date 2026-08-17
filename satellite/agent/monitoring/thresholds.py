"""Where a metric's alerting thresholds come from.

Every metric ships defaults taken from the spec, but a threshold is a property of the
deployment, not of the code: what counts as slow or drifted depends on the model and the
traffic it serves. The reference profile carries a ``thresholds`` block for exactly this,
so the profile wins when it defines a rule and the default stands in when it does not.
"""

import logging
from dataclasses import dataclass
from typing import Any

from agent.monitoring.models import Severity

logger = logging.getLogger(__name__)

# Keys as the reference profile writes them.
PSI = "psi"
ERROR_RATE = "error_rate"
LATENCY_P95_MS = "latency_p95_ms"
MISSING_RATE = "missing_rate"
TYPE_MISMATCH_RATE = "type_mismatch_rate"
RANGE_VIOLATION_RATE = "range_violation_rate"
UNSEEN_CATEGORY_RATE = "unseen_category_rate"

PROFILE = "profile"
DEFAULT = "default"


@dataclass(frozen=True)
class Threshold:
    """Warning / critical bounds for one metric.

    The spec words the two families of rules differently, and the difference is real at
    the boundary: data quality says "greater than 1 percent" (strict), PSI says "0.1 to
    0.25 is warning" (inclusive). ``warning_inclusive`` carries that wording, and it
    belongs to the metric — a profile overriding the numbers does not change it.
    """

    warning: float
    critical: float
    source: str = DEFAULT
    warning_inclusive: bool = False

    def evaluate(self, value: float) -> tuple[Severity, float] | None:
        """``(severity, the bound it broke)``, or ``None`` while the value is in range."""
        if value > self.critical:
            return Severity.CRITICAL, self.critical
        if value >= self.warning if self.warning_inclusive else value > self.warning:
            return Severity.WARNING, self.warning
        return None


def resolve(profile: dict[str, Any] | None, key: str, default: Threshold) -> Threshold:
    """The deployment's rule for ``key``, falling back to the metric's own default.

    A malformed rule is ignored rather than trusted: a threshold that is not a pair of
    numbers, or whose critical bound sits below its warning, would either silence the
    metric or make every window critical.
    """
    rule = ((profile or {}).get("thresholds") or {}).get(key)
    if not isinstance(rule, dict):
        return default

    warning = _number(rule.get("warning"))
    critical = _number(rule.get("critical"))
    if warning is None or critical is None or critical < warning:
        logger.warning("Ignoring malformed threshold %r in reference profile: %r", key, rule)
        return default
    return Threshold(
        warning=warning,
        critical=critical,
        source=PROFILE,
        warning_inclusive=default.warning_inclusive,
    )


def defines(profile: dict[str, Any] | None, key: str) -> bool:
    """Whether the profile carries a usable rule for ``key`` — used to label an alert."""
    return resolve(profile, key, Threshold(0.0, 0.0)).source == PROFILE


def _number(value: Any) -> float | None:  # noqa: ANN401
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)
