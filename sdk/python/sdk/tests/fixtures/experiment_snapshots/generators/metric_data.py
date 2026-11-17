"""Metric logs for the generation 2 fixtures, and the brute-force bucket expectations
computed from them alone (stdlib only, no SDK code).

The log is replayed through `tracker.log_dynamic` in order, so overwrites, out-of-order
and sparse steps reach the database the way a training script produces them.
"""

import math
from typing import Any

SUMMABLE_LIMIT = 1e290
EXPECTED_LEVELS = (0, 2, 3, 5, 8, 13)
LONG_KEY = "train/long_running_metric/with_a_fairly_long_key_name"
# A row released SDKs stored and revision 3 cannot: a REAL step.
LEGACY_REAL_STEP = ("loss", 7.0, 2.5)

LogEntry = tuple[str, float, int]


def metric_log() -> list[LogEntry]:
    log: list[LogEntry] = []
    log += [("loss", round(2.0 * 0.97**step, 9), step) for step in range(200)]
    # Overwrites, one of them after later steps, and out-of-order steps.
    log += [("loss", round(0.5 + step / 1000, 9), step) for step in range(10, 20)]
    log += [("loss", 9.5, 5), ("loss", 0.125, 250), ("loss", 0.25, 240)]
    log += [
        ("loss", math.nan, 50),
        ("loss", math.inf, 60),
        ("loss", -math.inf, 61),
        ("loss", 5e295, 70),
        ("loss", -1.7e308, 71),
        ("loss", 1e290, 72),
        ("loss", -1e290, 73),
    ]
    sparse = [-1_000_000, -4097, -64, -1, 0, 3, 4096, 1_000_003]
    log += [
        ("sparse/negative", float(index) - 3.5, step)
        for index, step in enumerate(sparse)
    ]
    log += [("one", 3.25, 7)]
    log += [("k", 1.0, 0), ("k", math.nan, 1), ("k", math.inf, 2)]
    log += [
        (LONG_KEY, round(10 * math.sin(index / 25), 9), index * 727)
        for index in range(400)
    ]
    return log


def stored_points(log: list[LogEntry]) -> dict[str, dict[int, float | None]]:
    """Last write wins; NaN is stored as NULL."""
    points: dict[str, dict[int, float | None]] = {}
    for key, value, step in log:
        points.setdefault(key, {})[step] = None if math.isnan(value) else value
    return {
        key: dict(sorted(by_step.items())) for key, by_step in sorted(points.items())
    }


def json_number(value: float | None) -> float | str | None:
    if value is None:
        return None
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    return value


def _aggregate(points: list[tuple[int, float | None]]) -> list[Any]:
    numeric = [value for _, value in points if value is not None]
    summable = [
        value for value in numeric if -SUMMABLE_LIMIT <= value <= SUMMABLE_LIMIT
    ]
    steps = [step for step, _ in points]
    return [
        min(steps),
        max(steps),
        len(points),
        len(summable),
        json_number(min(numeric)) if numeric else None,
        json_number(max(numeric)) if numeric else None,
        math.fsum(summable) if summable else None,
    ]


def buckets(points: dict[int, float | None], level: int) -> list[list[Any]]:
    """`[bucket, first_step, last_step, count, finite_count, min, max, sum]` rows."""
    grouped: dict[int, list[tuple[int, float | None]]] = {}
    for step, value in points.items():
        grouped.setdefault(step >> (2 * level), []).append((step, value))
    return [[bucket, *_aggregate(group)] for bucket, group in sorted(grouped.items())]


def catalog(points: dict[str, dict[int, float | None]]) -> list[dict[str, Any]]:
    rows = []
    for key, by_step in points.items():
        first, last, count, _, low, high, _ = _aggregate(list(by_step.items()))
        rows.append(
            {
                "key": key,
                "first_step": first,
                "last_step": last,
                "count": count,
                "min": low,
                "max": high,
            }
        )
    return rows


def expectations(log: list[LogEntry]) -> dict[str, Any]:
    points = stored_points(log)
    return {
        "levels": list(EXPECTED_LEVELS),
        "catalog": catalog(points),
        "buckets": {
            key: {str(level): buckets(by_step, level) for level in EXPECTED_LEVELS}
            for key, by_step in points.items()
        },
    }
