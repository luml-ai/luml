"""The kernel-side experiment recorder, backed by the workspace's SDK."""

from __future__ import annotations

import os
import sqlite3
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DEFAULT_STORE = "~/.luml/experiments"
_DAEMON_SDK_VERSION_ENV = "LUMLFLOW_DAEMON_SDK_VERSION"

# Every attempt keeps the SDK's default five-second SQLite wait.
SQLITE_BUSY_RETRIES = 1


class TrackerError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExperimentRef:
    """The stored identity and final snapshot of a tracked experiment."""

    experiment_id: str
    group: str
    store: Path
    snapshot: dict[str, dict[str, Any]]


class Experiment:
    """A read-only view of an experiment in the tracker."""

    def __init__(self, client: SdkTrackerClient, ref: ExperimentRef) -> None:
        self._client = client
        self._ref = ref

    @property
    def id(self) -> str:
        self._record()
        return self._ref.experiment_id

    @property
    def params(self) -> dict[str, Any]:
        record = self._record()
        return dict(getattr(record, "static_params", {}) or {})

    @property
    def metrics(self) -> dict[str, Any]:
        record = self._record()
        return dict(getattr(record, "dynamic_params", {}) or {})

    def metric_history(self, name: str) -> list[dict[str, Any]]:
        self._record()
        try:
            history = self._client.get_experiment_metric_history(
                self._ref.experiment_id, str(name)
            )
        except TrackerError as failure:
            self._record()
            raise self._unreachable(failure) from None
        return [dict(point) for point in history]

    def _record(self) -> Any:
        if self._ref.store.expanduser().resolve() != self._client.store.resolve():
            raise TrackerError(
                f"experiment `{self._ref.experiment_id}` is unreachable: it was "
                f"recorded in tracker store `{self._ref.store}`, but this kernel "
                f"uses `{self._client.store}`"
            )
        try:
            record = self._client.get_experiment_record(self._ref.experiment_id)
        except TrackerError as failure:
            raise self._unreachable(failure) from None
        if record is None:
            raise TrackerError(
                f"experiment `{self._ref.experiment_id}` is missing from tracker "
                f"store `{self._ref.store}`; run the cell that produced it again"
            )
        return record

    def _unreachable(self, failure: TrackerError) -> TrackerError:
        return TrackerError(
            f"experiment `{self._ref.experiment_id}` is unreachable in tracker "
            f"store `{self._ref.store}`: {failure}"
        )


def tracker_store() -> Path:
    raw = os.environ.get("BACKEND_STORE_URI") or os.environ.get(
        "LUML_BACKEND_STORE_URI", _DEFAULT_STORE
    )
    if "://" in raw:
        _, raw = raw.split("://", 1)
    return Path(raw).expanduser().resolve()


def daemon_sdk_version() -> str | None:
    return os.environ.get(_DAEMON_SDK_VERSION_ENV) or None


def open_sdk_tracker(
    store: Path,
    *,
    daemon_version: str | None = None,
    warn: Callable[[str], None] | None = None,
) -> SdkTrackerClient:
    factory, sdk_version = _import_sdk_tracker()
    warning = sdk_version_warning(sdk_version, daemon_version)
    if warning is not None and warn is not None:
        warn(warning)
    client = _sdk_call(lambda: factory(f"sqlite://{store}"), store, sdk_version)
    return SdkTrackerClient(client, store=store, sdk_version=sdk_version)


def sdk_version_warning(sdk_version: str, daemon_version: str | None) -> str | None:
    if daemon_version is None or daemon_version == sdk_version:
        return None
    interpreter = Path(sys.executable).absolute()
    return (
        "luml-sdk version mismatch: "
        f"workspace venv `{interpreter}` uses {sdk_version}, "
        f"but the daemon uses {daemon_version}; continuing with the workspace version"
    )


class SdkTrackerClient:
    def __init__(self, client: Any, *, store: Path, sdk_version: str) -> None:
        self._client = client
        self.store = store
        self.sdk_version = sdk_version

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._client, name)
        if not callable(attribute):
            return attribute

        def write(*args: Any, **kwargs: Any) -> Any:
            return _sdk_call(
                lambda: attribute(*args, **kwargs), self.store, self.sdk_version
            )

        return write


def _import_sdk_tracker() -> tuple[Callable[[str], Any], str]:
    try:
        from luml import __version__ as sdk_version
        from luml.experiments.tracker import ExperimentTracker
    except ImportError as failure:
        interpreter = Path(sys.executable).absolute()
        raise TrackerError(
            "could not import `luml-sdk` in the workspace environment "
            f"at `{interpreter}`; install `luml-sdk` there before running "
            f"an experiment cell ({failure})"
        ) from None
    return ExperimentTracker, str(sdk_version)


def _sdk_call(action: Callable[[], Any], store: Path, sdk_version: str) -> Any:
    for attempt in range(SQLITE_BUSY_RETRIES + 1):
        try:
            return action()
        except Exception as failure:
            if _is_sqlite_locked(failure) and attempt < SQLITE_BUSY_RETRIES:
                continue
            raise TrackerError(_sdk_failure(failure, store, sdk_version)) from None
    raise AssertionError("tracker retry loop did not return")


def _is_sqlite_locked(failure: BaseException) -> bool:
    pending: list[BaseException] = [failure]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if (
            isinstance(current, sqlite3.OperationalError)
            and "locked" in str(current).casefold()
        ):
            return True
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
    return False


def _sdk_failure(failure: Exception, store: Path, sdk_version: str) -> str:
    sentence = str(failure) or type(failure).__name__
    interpreter = Path(sys.executable).absolute()
    return (
        f"{sentence} (tracker store `{store}`; workspace venv `{interpreter}` "
        f"uses luml-sdk {sdk_version})"
    )


class Tracker:
    def __init__(
        self,
        client: Any,
        *,
        experiment_id: str,
        group: str,
        store: Path,
        params: Mapping[str, Any],
    ) -> None:
        self._client = client
        self.experiment_id = experiment_id
        self.group = group
        self.store = store
        self._params = dict(params)
        self._metrics: dict[str, float] = {}

    @classmethod
    def start(
        cls,
        client: Any,
        *,
        name: str,
        group: str,
        tags: list[str],
        store: Path,
        params: Mapping[str, Any],
    ) -> Tracker:
        experiment_id = str(client.start_experiment(name=name, group=group, tags=tags))
        return cls(
            client,
            experiment_id=experiment_id,
            group=group,
            store=store,
            params=params,
        )

    @property
    def event_fields(self) -> dict[str, str]:
        return {"experiment_id": self.experiment_id, "store": str(self.store)}

    def initialize(self, metadata: dict[str, Any]) -> None:
        self._client.set_experiment_metadata(self.experiment_id, metadata)
        for name, value in self._params.items():
            self._client.log_static(name, value, experiment_id=self.experiment_id)

    def log_param(self, name: str, value: Any) -> None:
        key = str(name)
        self._client.log_static(key, value, experiment_id=self.experiment_id)
        self._params[key] = value

    def log_params(self, values: Mapping[str, Any]) -> None:
        for name, value in values.items():
            self.log_param(name, value)

    def log_metric(self, name: str, value: float, step: int | None = None) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(
                f"`{name}` is a metric, so it takes a number — "
                "anything else belongs in a param"
            )
        key = str(name)
        self._client.log_dynamic(
            key, value, step=step, experiment_id=self.experiment_id
        )
        self._metrics[key] = value

    def log_metrics(self, values: Mapping[str, float], step: int | None = None) -> None:
        for name, value in values.items():
            self.log_metric(name, value, step=step)

    @property
    def record(self) -> ExperimentRef:
        return ExperimentRef(
            experiment_id=self.experiment_id,
            group=self.group,
            store=self.store,
            snapshot={
                "params": dict(self._params),
                "metrics": dict(self._metrics),
            },
        )

    def complete(self) -> None:
        self._client.end_experiment(self.experiment_id)

    def fail(self) -> None:
        self._client.fail_experiment(self.experiment_id)
