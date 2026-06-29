"""MLflow ``AbstractStore`` implementation backed by the luml SDK tracker.

This module wires the MLflow store API onto an ``ExperimentTracker``. The
terminology offset documented in ``SPEC.md`` (MLflow ``experiment_id`` is a luml
*group* id; MLflow ``run_id`` is a luml *experiment* id) is honored everywhere
in this file — no other module should refer to MLflow "run" or "experiment"
terms.

Tag mapping, ``metadata`` column reads/writes, and run reconstruction live in
:mod:`luml_mlflow.meta`; this file just composes those primitives.
"""

import logging
import time
import uuid
from typing import Any

from mlflow.entities import (
    Experiment,
    ExperimentTag,
    LifecycleStage,
    LoggedModel,
    LoggedModelStatus,
    Run,
    RunInfo,
    RunStatus,
    Span,
    Trace,
    TraceInfo,
    ViewType,
)
from mlflow.store.entities import PagedList
from mlflow.store.tracking.abstract_store import AbstractStore

from luml_mlflow import tracing as _tracing
from luml_mlflow._tracker import get_tracker
from luml_mlflow._unsupported import unsupported
from luml_mlflow.meta import (
    LUML_LOCAL_ONLY,
    RUN_ARTIFACT_URI,
    RUN_LIFECYCLE_STAGE,
    RUN_STATUS,
    RUN_USER_ID,
    metric_history_to_entities,
    reconstruct_run,
    write_luml_internal,
    write_run_info_field,
    write_tag,
    write_tags,
)
from luml_mlflow.uri import LumlTarget, build_artifact_uri, parse_tracking_uri

logger = logging.getLogger(__name__)

DEFAULT_EXPERIMENT_NAME = "Default"


class LumlTrackingStore(AbstractStore):
    """MLflow tracking store backed by a luml ``ExperimentTracker``.

    Maps MLflow ``experiment_id`` → luml **group** id and MLflow ``run_id`` →
    luml **experiment** id (the offset noted in SPEC.md).
    """

    def __init__(
        self, store_uri: str | None = None, artifact_uri: str | None = None
    ) -> None:
        super().__init__()
        self._store_uri = store_uri or ""
        self._target = self._parse_target(store_uri)
        self._tracker = get_tracker()
        self._logged_models: dict[str, dict[str, Any]] = {}
        self._ensure_default_experiment()

    @staticmethod
    def _parse_target(store_uri: str | None) -> LumlTarget:
        if not store_uri:
            return LumlTarget(org=None, orbit=None, local_only=True)
        return parse_tracking_uri(store_uri)

    @property
    def target(self) -> LumlTarget:
        return self._target

    def _ensure_default_experiment(self) -> None:
        if self._find_group_by_name(DEFAULT_EXPERIMENT_NAME) is None:
            self._tracker.create_group(DEFAULT_EXPERIMENT_NAME)

    def _find_group_by_name(self, name: str) -> Any:
        for group in self._tracker.list_groups():
            if group.name == name:
                return group
        return None

    def _artifact_uri_for_run(self, run_id: str, model_name: str | None = None) -> str:
        if self._target.local_only:
            base = f"luml://local/runs/{run_id}/artifacts"
        else:
            org = self._target.org or ""
            orbit = self._target.orbit or ""
            base = f"luml://{org}/{orbit}/runs/{run_id}/artifacts"
        return build_artifact_uri(base, model_name)

    @staticmethod
    def _ms_to_seconds(value: int | None) -> float | None:
        if value is None:
            return None
        return value / 1000.0

    @staticmethod
    def _seconds_to_ms(value: float | None) -> int | None:
        if value is None:
            return None
        return int(value * 1000)

    # ------------------------------------------------------------------ experiments

    def create_experiment(
        self,
        name: str,
        artifact_location: str | None = None,
        tags: list[Any] | None = None,
    ) -> str:
        if not name:
            raise ValueError("Experiment name must be a non-empty string")
        if self._find_group_by_name(name) is not None:
            from mlflow.exceptions import MlflowException

            raise MlflowException(f"Experiment {name!r} already exists")
        tag_entries = [_encode_group_tag(t.key, t.value) for t in tags or []]
        group = self._tracker.create_group(name, tags=tag_entries or None)
        return str(group.id)

    def get_experiment(self, experiment_id: str) -> Experiment:
        group = self._tracker.get_group(experiment_id)
        if group is None:
            from mlflow.exceptions import MlflowException

            raise MlflowException(f"Experiment {experiment_id!r} not found")
        return self._group_to_experiment(group)

    def get_experiment_by_name(self, experiment_name: str) -> Experiment | None:
        group = self._find_group_by_name(experiment_name)
        if group is None:
            return None
        return self._group_to_experiment(group)

    def _group_to_experiment(self, group: Any) -> Experiment:
        creation_ms = int(group.created_at.timestamp() * 1000)
        last_update_ms = (
            int(group.last_modified.timestamp() * 1000)
            if getattr(group, "last_modified", None) is not None
            else creation_ms
        )
        tags = [
            ExperimentTag(key, value)
            for key, value in _decode_group_tags(group.tags or []).items()
        ]
        return Experiment(
            experiment_id=str(group.id),
            name=group.name,
            artifact_location=self._artifact_uri_for_run(str(group.id)),
            lifecycle_stage=LifecycleStage.ACTIVE,
            tags=tags,
            creation_time=creation_ms,
            last_update_time=last_update_ms,
        )

    def search_experiments(
        self,
        view_type: int = ViewType.ACTIVE_ONLY,
        max_results: int = 1000,
        filter_string: str | None = None,
        order_by: list[str] | None = None,
        page_token: str | None = None,
    ) -> PagedList[Experiment]:
        groups = self._tracker.list_groups()
        if order_by:
            groups = _apply_order_by(groups, order_by)
        else:
            groups = sorted(groups, key=lambda g: g.created_at, reverse=True)
        experiments = [self._group_to_experiment(g) for g in groups]
        return PagedList(experiments[:max_results], token=None)

    def delete_experiment(self, experiment_id: str) -> None:
        unsupported(
            f"delete_experiment({experiment_id!r}) is not supported by the luml store",
            exception_factory=NotImplementedError,
        )

    def restore_experiment(self, experiment_id: str) -> None:
        unsupported(
            f"restore_experiment({experiment_id!r}) is not supported by the luml store",
            exception_factory=NotImplementedError,
        )

    def rename_experiment(self, experiment_id: str, new_name: str) -> None:
        unsupported(
            "rename_experiment is not supported by the luml store",
            exception_factory=NotImplementedError,
        )

    def set_experiment_tag(self, experiment_id: str, tag: Any) -> None:
        group = self._tracker.get_group(experiment_id)
        if group is None:
            from mlflow.exceptions import MlflowException

            raise MlflowException(f"Experiment {experiment_id!r} not found")
        tags = _decode_group_tags(group.tags or [])
        tags[tag.key] = tag.value
        self._tracker.update_group(
            experiment_id,
            tags=[_encode_group_tag(k, v) for k, v in tags.items()],
        )

    # --------------------------------------------------------------------- runs

    def create_run(
        self,
        experiment_id: str,
        user_id: str,
        start_time: int,
        tags: list[Any] | None = None,
        run_name: str | None = None,
    ) -> Run:
        group = self._tracker.get_group(experiment_id)
        if group is None:
            from mlflow.exceptions import MlflowException

            raise MlflowException(f"Experiment {experiment_id!r} not found")
        run_id = uuid.uuid4().hex
        self._tracker.start_experiment(
            name=run_name,
            group=group.name,
            experiment_id=run_id,
        )
        # MLflow's notion of "active run" is per-call (run_id parameter), not a
        # process-wide pointer; clear the SDK's so subsequent SDK calls don't
        # implicitly target this run.
        self._tracker.current_experiment_id = None

        artifact_uri = self._artifact_uri_for_run(run_id)
        write_run_info_field(self._tracker, run_id, RUN_USER_ID, user_id)
        write_run_info_field(
            self._tracker, run_id, RUN_LIFECYCLE_STAGE, LifecycleStage.ACTIVE
        )
        write_run_info_field(self._tracker, run_id, RUN_ARTIFACT_URI, artifact_uri)
        if self._target.local_only:
            write_luml_internal(self._tracker, run_id, {LUML_LOCAL_ONLY: "true"})

        if tags:
            write_tags(self._tracker, run_id, tags)

        return self.get_run(run_id)

    def get_run(self, run_id: str) -> Run:
        run = reconstruct_run(self._tracker, run_id, self._artifact_uri_for_run)
        if run is None:
            from mlflow.exceptions import MlflowException

            raise MlflowException(f"Run {run_id!r} not found")
        return run

    def update_run_info(
        self,
        run_id: str,
        run_status: int,
        end_time: int | None,
        run_name: str | None,
    ) -> RunInfo:
        terminal = run_status in RunStatus._TERMINATED_STATUSES  # noqa: SLF001
        if terminal:
            status_str = RunStatus.to_string(run_status)
            write_run_info_field(self._tracker, run_id, RUN_STATUS, status_str)
            if run_status == RunStatus.FINISHED:
                self._tracker.end_experiment(run_id)
            else:
                self._tracker.fail_experiment(run_id)
        if run_name is not None:
            self._tracker.update_experiment(run_id, name=run_name)
        info = self.get_run(run_id).info
        if terminal:
            self._maybe_autosync(run_id)
        return info

    def _maybe_autosync(self, run_id: str) -> None:
        """Trigger best-effort sync on terminal status.

        Gated by ``LUML_MLFLOW_AUTOSYNC``; never raises into user training
        code. Local-only targets are skipped silently (the sync layer already
        no-ops on them). Failures are swallowed: they are logged, captured in
        ``upload_status=failed``/``luml.upload_error``, and the user's
        ``mlflow.end_run()`` returns normally.
        """
        from luml_mlflow.config import get_settings

        settings = get_settings()
        if not settings.LUML_MLFLOW_AUTOSYNC:
            return
        if self._target.local_only:
            return
        if not self._target.sync_eligible:
            return
        try:
            from luml_mlflow.sync import sync as _sync

            _sync(run_id, tracking_uri=self._store_uri)
        except Exception:  # noqa: BLE001
            logger.exception(
                "[luml-mlflow] auto-sync raised unexpectedly for run %s", run_id
            )

    def delete_run(self, run_id: str) -> None:
        self._tracker.delete_experiment(run_id)

    def restore_run(self, run_id: str) -> None:
        unsupported(
            f"restore_run({run_id!r}) is not supported by the luml store",
            exception_factory=NotImplementedError,
        )

    # ---------------------------------------------------------- params/metrics

    def log_param(self, run_id: str, param: Any) -> None:
        self._tracker.log_static(param.key, param.value, experiment_id=run_id)

    def log_metric(self, run_id: str, metric: Any) -> None:
        self._tracker.log_dynamic(
            metric.key, metric.value, step=metric.step, experiment_id=run_id
        )

    def set_tag(self, run_id: str, tag: Any) -> None:
        write_tag(self._tracker, run_id, tag.key, tag.value)

    def delete_tag(self, run_id: str, key: str) -> None:
        from luml_mlflow.meta import delete_tag as _delete_tag

        _delete_tag(self._tracker, run_id, key)

    def log_batch(
        self,
        run_id: str,
        metrics: list[Any] | None = None,
        params: list[Any] | None = None,
        tags: list[Any] | None = None,
    ) -> None:
        for param in params or []:
            self._tracker.log_static(param.key, param.value, experiment_id=run_id)
        for metric in metrics or []:
            self._tracker.log_dynamic(
                metric.key,
                metric.value,
                step=metric.step,
                experiment_id=run_id,
            )
        if tags:
            write_tags(self._tracker, run_id, tags)

    def get_metric_history(
        self,
        run_id: str,
        metric_key: str,
        max_results: int | None = None,
        page_token: str | None = None,
    ) -> PagedList[Any]:
        history = self._tracker.get_experiment_metric_history(run_id, metric_key)
        metrics = metric_history_to_entities(metric_key, history)
        if max_results is not None:
            metrics = metrics[:max_results]
        return PagedList(metrics, token=None)

    # ------------------------------------------------------------- search runs

    def _search_runs(
        self,
        experiment_ids: list[str],
        filter_string: str,
        run_view_type: int,
        max_results: int,
        order_by: list[str] | None,
        page_token: str | None,
    ) -> tuple[list[Run], str | None]:
        ids = set(experiment_ids or [])
        records = [r for r in self._tracker.list_experiments() if r.group_id in ids]
        if order_by:
            records = _apply_order_by(records, order_by)
        else:
            records = sorted(records, key=lambda r: r.created_at, reverse=True)
        runs: list[Run] = []
        for record in records[:max_results]:
            run = reconstruct_run(self._tracker, record.id, self._artifact_uri_for_run)
            if run is not None:
                runs.append(run)
        return runs, None

    # ----------------------------------------------------------------- traces

    def start_trace(self, trace_info: TraceInfo) -> TraceInfo:
        return _tracing.start_trace(self._tracker, trace_info)

    def log_spans(
        self,
        location: str,
        spans: list[Span],
        tracking_uri: str | None = None,
    ) -> list[Span]:
        return _tracing.log_spans(self._tracker, location, spans)

    def get_trace_info(self, trace_id: str) -> TraceInfo:
        return _tracing.get_trace_info(self._tracker, trace_id)

    def get_trace(self, trace_id: str, *, allow_partial: bool = False) -> Trace:
        return _tracing.get_trace(self._tracker, trace_id)

    def set_trace_tag(self, trace_id: str, key: str, value: str) -> None:
        _tracing.set_trace_tag(self._tracker, trace_id, key, value)

    def delete_trace_tag(self, trace_id: str, key: str) -> None:
        _tracing.delete_trace_tag(self._tracker, trace_id, key)

    def search_traces(
        self,
        experiment_ids: list[str] | None = None,
        filter_string: str | None = None,
        max_results: int = 100,
        order_by: list[str] | None = None,
        page_token: str | None = None,
        model_id: str | None = None,
        locations: list[str] | None = None,
    ) -> tuple[list[TraceInfo], str | None]:
        return _tracing.search_traces(
            self._tracker, experiment_ids, max_results=max_results
        )

    # --------------------------------------------------------- logged models

    def create_logged_model(
        self,
        experiment_id: str,
        name: str | None = None,
        source_run_id: str | None = None,
        tags: list[Any] | None = None,
        params: list[Any] | None = None,
        model_type: str | None = None,
    ) -> LoggedModel:
        """Create a ``PENDING`` LoggedModel (MLflow 3.x ``log_model`` entrypoint).

        The model's ``artifact_location`` points at its source run's ``luml://``
        artifact URI, so MLflow's ``log_model_artifacts`` routes the saved model
        directory through :class:`~luml_mlflow.artifact_repo.LumlArtifactRepository`
        (fnnx conversion + luml model logging) with no further wiring.
        """
        if not experiment_id or self._tracker.get_group(experiment_id) is None:
            from mlflow.exceptions import MlflowException

            raise MlflowException(f"Experiment {experiment_id!r} not found")
        model_id = uuid.uuid4().hex
        now = self._now_ms()
        rec: dict[str, Any] = {
            "experiment_id": str(experiment_id),
            "model_id": model_id,
            "name": name or f"model-{model_id[:8]}",
            # The user-given ``name`` (if any) rides along on the artifact URI so
            # the artifact repository can store the luml model under it instead
            # of the ``<experiment>-<hash>`` fallback.
            "artifact_location": self._artifact_uri_for_run(
                source_run_id or model_id, model_name=name
            ),
            "creation_timestamp": now,
            "last_updated_timestamp": now,
            "model_type": model_type,
            "source_run_id": source_run_id,
            "status": LoggedModelStatus.PENDING,
            "tags": {t.key: t.value for t in tags or []},
            "params": {p.key: p.value for p in params or []},
        }
        self._logged_models[model_id] = rec
        return self._to_logged_model(rec)

    def get_logged_model(
        self, model_id: str, allow_deleted: bool = False
    ) -> LoggedModel:
        return self._to_logged_model(self._require_logged_model(model_id))

    def search_logged_models(
        self,
        experiment_ids: list[str],
        filter_string: str | None = None,
        datasets: list[dict[str, Any]] | None = None,
        max_results: int | None = None,
        order_by: list[dict[str, Any]] | None = None,
        page_token: str | None = None,
    ) -> PagedList[LoggedModel]:
        """Return logged models scoped to ``experiment_ids``.

        The MLflow 3.x run-details page calls this to render its Models section,
        so it must not raise (the base ``AbstractStore`` does). Logged models are
        held in-process, so a fresh server process returns an empty page rather
        than the models a separate training process logged.
        """
        wanted = set(experiment_ids or [])
        models = [
            self._to_logged_model(rec)
            for rec in self._logged_models.values()
            if rec["experiment_id"] in wanted
        ]
        models.sort(key=lambda m: m.creation_timestamp, reverse=True)
        if max_results is not None:
            models = models[:max_results]
        return PagedList(models, token=None)

    def finalize_logged_model(
        self, model_id: str, status: LoggedModelStatus
    ) -> LoggedModel:
        rec = self._require_logged_model(model_id)
        rec["status"] = status
        rec["last_updated_timestamp"] = self._now_ms()
        return self._to_logged_model(rec)

    def set_logged_model_tags(self, model_id: str, tags: list[Any]) -> None:
        rec = self._require_logged_model(model_id)
        for tag in tags or []:
            rec["tags"][tag.key] = tag.value
        rec["last_updated_timestamp"] = self._now_ms()

    def delete_logged_model_tag(self, model_id: str, key: str) -> None:
        rec = self._require_logged_model(model_id)
        rec["tags"].pop(key, None)
        rec["last_updated_timestamp"] = self._now_ms()

    def log_outputs(self, run_id: str, models: list[Any]) -> None:
        # Records the run → LoggedModel linkage. The model artifacts are already
        # persisted under the run via the artifact repository, so the linkage is
        # implicit and accepted silently here.
        return None

    def _require_logged_model(self, model_id: str) -> dict[str, Any]:
        rec = self._logged_models.get(model_id)
        if rec is None:
            from mlflow.exceptions import MlflowException

            raise MlflowException(f"LoggedModel {model_id!r} not found")
        return rec

    @staticmethod
    def _to_logged_model(rec: dict[str, Any]) -> LoggedModel:
        return LoggedModel(
            experiment_id=rec["experiment_id"],
            model_id=rec["model_id"],
            name=rec["name"],
            artifact_location=rec["artifact_location"],
            creation_timestamp=rec["creation_timestamp"],
            last_updated_timestamp=rec["last_updated_timestamp"],
            model_type=rec["model_type"],
            source_run_id=rec["source_run_id"],
            status=rec["status"],
            tags=dict(rec["tags"]),
            params=dict(rec["params"]),
        )

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)

    # ----------------------------------------------------------- unsupported

    def log_inputs(
        self,
        run_id: str,
        datasets: list[Any] | None = None,
        models: list[Any] | None = None,
    ) -> None:
        # ``models`` carries the LoggedModelOutput linkage emitted by
        # ``log_model``; the model artifacts are already persisted via the
        # artifact repository, so that linkage is implicit and accepted here.
        if datasets:
            unsupported(
                "log_inputs(datasets=...) is not yet supported by the luml store",
            )

    def link_traces_to_run(self, trace_ids: list[str], run_id: str) -> None:
        unsupported(
            "link_traces_to_run is not yet supported by the luml store",
        )


def _encode_group_tag(key: str, value: str) -> str:
    """Encode an MLflow experiment tag into a luml group's flat ``tags`` list.

    A group exposes only ``list[str]`` for tags (no key/value metadata column),
    so each experiment tag is stored as ``"key=value"`` and decoded back by
    splitting on the first ``=`` (see :func:`_decode_group_tags`).
    """
    return f"{key}={value}"


def _decode_group_tags(raw_tags: list[str]) -> dict[str, str]:
    """Inverse of :func:`_encode_group_tag`.

    Splits on the first ``=`` so values may contain ``=``; a bare entry with no
    ``=`` (e.g. a luml-native flag set outside MLflow) decodes to an empty value.
    """
    out: dict[str, str] = {}
    for raw in raw_tags:
        key, sep, value = raw.partition("=")
        out[key] = value if sep else ""
    return out


def _apply_order_by(items: list[Any], order_by: list[str]) -> list[Any]:
    """Apply a minimal ``order_by`` clause list.

    Supports the small set of keys real MLflow callers exercise on a tracking
    store with no SQL filter engine: ``created_at`` / ``start_time`` /
    ``last_modified`` / ``name`` with an optional ``ASC``/``DESC`` direction.
    Unknown keys silently fall back to ``created_at`` order.
    """
    if not order_by:
        return items

    def parse(clause: str) -> tuple[str, bool]:
        parts = clause.strip().split()
        key = parts[0].lower()
        direction = parts[1].upper() if len(parts) > 1 else "ASC"
        return key, direction == "DESC"

    sorted_items = items
    for clause in reversed(order_by):
        key, reverse = parse(clause)
        if key in {"created_at", "creation_time", "start_time"}:
            sorted_items = sorted(
                sorted_items,
                key=lambda item: item.created_at,
                reverse=reverse,
            )
        elif key == "name":
            sorted_items = sorted(
                sorted_items,
                key=lambda item: (item.name or "").lower(),
                reverse=reverse,
            )
        elif key in {"last_modified", "last_update_time"}:
            sorted_items = sorted(
                sorted_items,
                key=lambda item: (
                    getattr(item, "last_modified", None) or item.created_at
                ),
                reverse=reverse,
            )
    return sorted_items


__all__ = ["DEFAULT_EXPERIMENT_NAME", "LumlTrackingStore"]
