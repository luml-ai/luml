from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from pathlib import Path

DEFAULT_HEARTBEAT_FILE = "/tmp/luml-monitoring-worker-heartbeat"
DEFAULT_INTERVAL_SECONDS = 60.0


def heartbeat_file_is_fresh(
    path: Path | str,
    *,
    interval_seconds: float,
    clock: Callable[[], float] = time.time,
) -> bool:
    if interval_seconds <= 0:
        return False
    try:
        modified_at = Path(path).stat().st_mtime
    except OSError:
        return False
    return max(0.0, clock() - modified_at) <= interval_seconds * 3


def probe_settings(environment: Mapping[str, str] | None = None) -> tuple[str, float]:
    source = os.environ if environment is None else environment
    path = source.get("MONITORING_HEARTBEAT_FILE", "").strip() or DEFAULT_HEARTBEAT_FILE
    raw = source.get("MONITORING_INTERVAL_SEC", "").strip()
    if not raw:
        return path, DEFAULT_INTERVAL_SECONDS
    try:
        return path, float(raw)
    except ValueError:
        return path, DEFAULT_INTERVAL_SECONDS


def main() -> None:
    path, interval_seconds = probe_settings()
    fresh = heartbeat_file_is_fresh(path, interval_seconds=interval_seconds)
    raise SystemExit(0 if fresh else 1)


if __name__ == "__main__":
    main()
