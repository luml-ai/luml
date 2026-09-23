import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from luml_heartbeat import heartbeat_file_is_fresh as heartbeat_file_is_fresh

from luml_satellite.monitoring.compute.health import (
    DeploymentHealth,
    HealthSnapshot,
    MetricFailure,
)


@dataclass(frozen=True)
class MergedWorkerHeartbeat:
    running: bool
    last_tick_at: datetime
    deployment: DeploymentHealth
    window_seconds: float
    interval_seconds: float

    @property
    def snapshot(self) -> HealthSnapshot:
        return HealthSnapshot(
            running=self.running,
            last_tick_at=self.last_tick_at,
            deployment=self.deployment,
        )


@dataclass(frozen=True)
class WorkerHeartbeat:
    shard_index: int
    shard_count: int
    tick_at: datetime
    window_seconds: float
    interval_seconds: float
    deployments: dict[str, DeploymentHealth]

    def __post_init__(self) -> None:
        if self.shard_count <= 0:
            raise ValueError("shard_count must be greater than zero")
        if not 0 <= self.shard_index < self.shard_count:
            raise ValueError("shard_index must be within shard_count")

    def to_json(self) -> str:
        deployments = {
            deployment_id: {
                "windows_processed": health.windows_processed,
                "last_window_end": _format_datetime(health.last_window_end),
                "last_processed_at": _format_datetime(health.last_processed_at),
                "last_lag_seconds": health.last_lag_seconds,
                "failures": [
                    {
                        "metric": failure.metric,
                        "error": failure.error,
                        "at": _format_datetime(failure.at),
                    }
                    for failure in health.failures
                ],
            }
            for deployment_id, health in self.deployments.items()
        }
        return json.dumps(deployments, separators=(",", ":"), sort_keys=True)

    @classmethod
    def from_json(
        cls,
        *,
        shard_index: int,
        shard_count: int,
        tick_at: datetime,
        window_seconds: float,
        interval_seconds: float,
        deployments_json: str,
    ) -> WorkerHeartbeat:
        raw: Any = json.loads(deployments_json)
        if not isinstance(raw, dict):
            raise ValueError("heartbeat deployments must be an object")
        deployments: dict[str, DeploymentHealth] = {}
        for deployment_id, value in raw.items():
            if not isinstance(deployment_id, str) or not isinstance(value, dict):
                raise ValueError("invalid heartbeat deployment")
            failures_value = value.get("failures", [])
            if not isinstance(failures_value, list):
                raise ValueError("heartbeat failures must be a list")
            failures = tuple(_parse_failure(item) for item in failures_value)
            deployments[deployment_id] = DeploymentHealth(
                windows_processed=int(value.get("windows_processed", 0)),
                last_window_end=_parse_optional_datetime(value.get("last_window_end")),
                last_processed_at=_parse_optional_datetime(value.get("last_processed_at")),
                last_lag_seconds=_parse_optional_float(value.get("last_lag_seconds")),
                failures=failures,
            )
        return cls(
            shard_index=shard_index,
            shard_count=shard_count,
            tick_at=tick_at,
            window_seconds=window_seconds,
            interval_seconds=interval_seconds,
            deployments=deployments,
        )

    @classmethod
    def merge(
        cls,
        heartbeats: Iterable[WorkerHeartbeat],
        deployment_id: UUID | str,
        *,
        now: datetime | None = None,
    ) -> MergedWorkerHeartbeat | None:
        latest = _latest_generation(heartbeats)
        if not latest:
            return None
        moment = now or datetime.now(UTC)
        newest = max(latest, key=lambda heartbeat: heartbeat.tick_at)
        deployment_key = str(deployment_id)
        owner = next(
            (heartbeat for heartbeat in latest if deployment_key in heartbeat.deployments),
            None,
        )
        health = owner.deployments[deployment_key] if owner is not None else DeploymentHealth()
        liveness = owner or newest
        age = max(0.0, (moment - liveness.tick_at).total_seconds())
        return MergedWorkerHeartbeat(
            running=age <= liveness.interval_seconds * 3,
            last_tick_at=newest.tick_at,
            deployment=health,
            window_seconds=liveness.window_seconds,
            interval_seconds=liveness.interval_seconds,
        )


def deployment_shard(deployment_id: str, shard_count: int) -> int:
    if shard_count <= 0:
        raise ValueError("shard_count must be greater than zero")
    digest = hashlib.sha256(deployment_id.encode()).digest()
    return int.from_bytes(digest[:8], "big") % shard_count


def _latest_generation(heartbeats: Iterable[WorkerHeartbeat]) -> list[WorkerHeartbeat]:
    values = list(heartbeats)
    if not values:
        return []
    newest = max(values, key=lambda heartbeat: heartbeat.tick_at)
    generation = [heartbeat for heartbeat in values if heartbeat.shard_count == newest.shard_count]
    latest_by_shard: dict[int, WorkerHeartbeat] = {}
    for heartbeat in generation:
        current = latest_by_shard.get(heartbeat.shard_index)
        if current is None or heartbeat.tick_at > current.tick_at:
            latest_by_shard[heartbeat.shard_index] = heartbeat
    return list(latest_by_shard.values())


def _parse_failure(value: object) -> MetricFailure:
    if not isinstance(value, dict):
        raise ValueError("invalid heartbeat failure")
    at = _parse_optional_datetime(value.get("at"))
    if at is None:
        raise ValueError("heartbeat failure requires a timestamp")
    return MetricFailure(
        metric=str(value.get("metric", "")),
        error=str(value.get("error", "")),
        at=at,
    )


def _format_datetime(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value is not None else None


def _parse_optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("heartbeat timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _parse_optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise ValueError("heartbeat number must be numeric")
    return float(value)
