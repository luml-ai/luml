"""Tag/metadata mapping between MLflow's data model and the luml SDK store.

The MLflow data model has key-value tags; the luml SDK has flat flag-style
``tags`` (list[str]), static params (``log_static``), a free-form per-experiment
``metadata`` JSON column, and a dedicated ``upload_status`` column. This module
encodes the routing rule documented in ``SPEC.md`` under "Tag mapping":

* ``luml.*`` is reserved — user writes go through the shared ``unsupported``
  chokepoint; the plugin's own internal writes bypass this module entirely and
  set the dedicated columns directly.
* ``mlflow.*`` is MLflow's own namespace — stored on the ``metadata`` column
  silently and round-tripped faithfully.
* User tags whose value is ``"true"`` or ``""`` (flag-shaped) → luml flat
  ``tags`` flags, lossless round-trip.
* Any other user tag → luml static param (``log_static``) with a warning, not
  round-tripped back as an MLflow tag.

``get_run`` reconstruction is built from native params/metrics, the ``metadata``
column, and the dedicated ``upload_status`` column.
"""

import json
import logging
from collections.abc import Iterable
from typing import Any

from mlflow.entities import (
    LifecycleStage,
    Metric,
    Param,
    Run,
    RunData,
    RunInfo,
    RunStatus,
    RunTag,
)

from luml_mlflow._tracker import ThreadSafeTracker
from luml_mlflow._unsupported import unsupported

logger = logging.getLogger(__name__)

RESERVED_TAG_PREFIX = "luml."
MLFLOW_TAG_PREFIX = "mlflow."
FLAG_TRUE_VALUE = "true"
FLAG_EMPTY_VALUE = ""

# Metadata column keys that the plugin owns internally.
META_MLFLOW_TAGS = "mlflow_tags"
META_FLAG_TAGS = "flag_tags"
META_RUN_INFO = "run_info"

# Sub-keys inside ``META_RUN_INFO``.
RUN_USER_ID = "user_id"
RUN_LIFECYCLE_STAGE = "lifecycle_stage"
RUN_ARTIFACT_URI = "artifact_uri"
RUN_STATUS = "status"

# ``upload_status`` column values.
UPLOAD_STATUS_UNKNOWN = "unknown"
UPLOAD_STATUS_NOT_UPLOADED = "not_uploaded"
UPLOAD_STATUS_UPLOADING = "uploading"
UPLOAD_STATUS_UPLOADED = "uploaded"
UPLOAD_STATUS_FAILED = "failed"

# Internal ``luml.*`` keys surfaced back to MLflow via ``get_run``. The dedicated
# upload status column is the source of truth for ``luml.upload_status`` (the
# rest live in the ``metadata`` column under ``META_LUML_INTERNAL``).
LUML_UPLOAD_STATUS = "luml.upload_status"
LUML_LOCAL_ONLY = "luml.local_only"
LUML_ARTIFACT_IDS = "luml.artifact_ids"
LUML_ARTIFACT_URLS = "luml.artifact_urls"
LUML_COLLECTION_ID = "luml.collection_id"
LUML_ORBIT_ID = "luml.orbit_id"
LUML_ORGANIZATION_ID = "luml.organization_id"
LUML_UPLOAD_ERROR = "luml.upload_error"

META_LUML_INTERNAL = "luml_internal"


def is_flag_shaped(value: str | None) -> bool:
    """Return ``True`` if a tag value is flag-shaped (``"true"`` or ``""``)."""
    return value == FLAG_TRUE_VALUE or value == FLAG_EMPTY_VALUE


def _encode_flag(key: str, value: str) -> str:
    """Encode a flag-shaped tag onto the SDK's flat ``tags`` list.

    The encoding must distinguish ``"true"`` from ``""`` on read-back, so
    keys are stored as ``"key"`` for ``"true"`` and ``"key="`` for ``""``.
    """
    if value == FLAG_TRUE_VALUE:
        return key
    return f"{key}="


def _decode_flag(flag: str) -> tuple[str, str]:
    """Inverse of :func:`_encode_flag`. Returns ``(key, value)``."""
    if flag.endswith("="):
        return flag[:-1], FLAG_EMPTY_VALUE
    return flag, FLAG_TRUE_VALUE


def write_tag(tracker: ThreadSafeTracker, run_id: str, key: str, value: str) -> None:
    """Write a single MLflow run tag to the SDK store via the routing rule.

    * ``luml.*`` keys are reserved — user writes go through ``unsupported``
      (warn → log + ignore; raise → ``MlflowException``).
    * ``mlflow.*`` keys are stored on the experiment ``metadata`` column under
      the ``mlflow_tags`` map, silently (no warning).
    * Flag-shaped values (``"true"``/``""``) on any other key are appended to
      the SDK's flat ``tags`` list (encoded to preserve the value).
    * Any other value is logged as a luml static param with a warning, with
      no round-trip path.
    """
    if key.startswith(RESERVED_TAG_PREFIX):
        unsupported(
            f"Tag key {key!r} uses the reserved 'luml.*' namespace; "
            "set via the sync layer, not via set_tag",
        )
        return

    if key.startswith(MLFLOW_TAG_PREFIX):
        _set_mlflow_tag(tracker, run_id, key, value)
        return

    if is_flag_shaped(value):
        _append_flag_tag(tracker, run_id, key, value)
        return

    logger.warning(
        "[luml-mlflow] tag %r has non-flag value %r; storing as a luml static "
        "param. It will not round-trip via get_run tags.",
        key,
        value,
    )
    tracker.log_static(key, value, experiment_id=run_id)


def write_tags(tracker: ThreadSafeTracker, run_id: str, tags: Iterable[Any]) -> None:
    """Route a batch of MLflow run tags through :func:`write_tag`."""
    for tag in tags:
        write_tag(tracker, run_id, tag.key, tag.value)


def delete_tag(tracker: ThreadSafeTracker, run_id: str, key: str) -> None:
    """Delete an MLflow run tag from the SDK store.

    Mirrors the routing rule of :func:`write_tag`. ``luml.*`` deletes are
    rejected (reserved); other deletes adjust the right slot.
    """
    if key.startswith(RESERVED_TAG_PREFIX):
        unsupported(
            f"Tag key {key!r} uses the reserved 'luml.*' namespace; "
            "delete via the sync layer, not via delete_tag",
        )
        return

    if key.startswith(MLFLOW_TAG_PREFIX):
        _delete_mlflow_tag(tracker, run_id, key)
        return

    _delete_flag_tag(tracker, run_id, key)


def _set_mlflow_tag(
    tracker: ThreadSafeTracker, run_id: str, key: str, value: str
) -> None:
    meta = tracker.get_experiment_metadata(run_id)
    mlflow_tags = dict(meta.get(META_MLFLOW_TAGS) or {})
    mlflow_tags[key] = value
    tracker.update_experiment_metadata(run_id, {META_MLFLOW_TAGS: mlflow_tags})


def _delete_mlflow_tag(tracker: ThreadSafeTracker, run_id: str, key: str) -> None:
    meta = tracker.get_experiment_metadata(run_id)
    mlflow_tags = dict(meta.get(META_MLFLOW_TAGS) or {})
    if key in mlflow_tags:
        mlflow_tags.pop(key)
        tracker.update_experiment_metadata(run_id, {META_MLFLOW_TAGS: mlflow_tags})


def _append_flag_tag(
    tracker: ThreadSafeTracker, run_id: str, key: str, value: str
) -> None:
    record = tracker.get_experiment_record(run_id)
    if record is None:
        return
    encoded = _encode_flag(key, value)
    existing = [t for t in (record.tags or []) if _decode_flag(t)[0] != key]
    existing.append(encoded)
    tracker.update_experiment(run_id, tags=existing)


def _delete_flag_tag(tracker: ThreadSafeTracker, run_id: str, key: str) -> None:
    record = tracker.get_experiment_record(run_id)
    if record is None:
        return
    existing = [t for t in (record.tags or []) if _decode_flag(t)[0] != key]
    tracker.update_experiment(run_id, tags=existing)


def write_run_info_field(
    tracker: ThreadSafeTracker, run_id: str, field: str, value: Any
) -> None:
    """Write a single ``run_info`` field to the experiment ``metadata`` column."""
    meta = tracker.get_experiment_metadata(run_id)
    run_info = dict(meta.get(META_RUN_INFO) or {})
    if value is None:
        run_info.pop(field, None)
    else:
        run_info[field] = value
    tracker.update_experiment_metadata(run_id, {META_RUN_INFO: run_info})


def read_run_info_field(
    tracker: ThreadSafeTracker, run_id: str, field: str, default: Any = None
) -> Any:
    """Read a single ``run_info`` field from the ``metadata`` column."""
    meta = tracker.get_experiment_metadata(run_id)
    run_info = meta.get(META_RUN_INFO) or {}
    return run_info.get(field, default)


def write_luml_internal(
    tracker: ThreadSafeTracker, run_id: str, updates: dict[str, Any]
) -> None:
    """Write plugin-managed ``luml.*`` metadata to the ``metadata`` column.

    Intended for internal use by the sync orchestrator. ``luml.upload_status``
    has its own dedicated column and is set separately.
    """
    meta = tracker.get_experiment_metadata(run_id)
    luml = dict(meta.get(META_LUML_INTERNAL) or {})
    for key, value in updates.items():
        if value is None:
            luml.pop(key, None)
        else:
            luml[key] = value
    tracker.update_experiment_metadata(run_id, {META_LUML_INTERNAL: luml})


def reconstruct_run(
    tracker: ThreadSafeTracker,
    run_id: str,
    artifact_uri_fn: Any,
) -> Run | None:
    """Reconstruct an MLflow :class:`Run` from the luml store.

    Combines native experiment fields (name, created_at, duration, status,
    tags, static_params, dynamic_metrics) with the ``metadata`` column
    (mlflow.* tags, run_info fields, luml.* internal state) and the
    ``upload_status`` column to populate :class:`RunInfo` and :class:`RunData`.
    """
    record = tracker.get_experiment_record(run_id)
    if record is None:
        return None
    data = tracker.get_experiment(run_id)
    metadata = record.metadata or {}
    upload_status = record.upload_status or UPLOAD_STATUS_UNKNOWN
    run_info_meta = metadata.get(META_RUN_INFO) or {}
    mlflow_tags = metadata.get(META_MLFLOW_TAGS) or {}
    luml_internal = metadata.get(META_LUML_INTERNAL) or {}

    start_ms = int(record.created_at.timestamp() * 1000)
    end_ms: int | None = None
    if record.duration is not None:
        end_ms = start_ms + int(record.duration * 1000)

    status = _resolve_run_status(record.status, run_info_meta.get(RUN_STATUS))
    lifecycle_stage = run_info_meta.get(RUN_LIFECYCLE_STAGE) or LifecycleStage.ACTIVE
    artifact_uri = run_info_meta.get(RUN_ARTIFACT_URI) or artifact_uri_fn(run_id)

    info = RunInfo(
        run_id=record.id,
        experiment_id=record.group_id or "",
        user_id=run_info_meta.get(RUN_USER_ID) or "",
        status=status,
        start_time=start_ms,
        end_time=end_ms,
        lifecycle_stage=lifecycle_stage,
        artifact_uri=artifact_uri,
        run_name=record.name,
    )

    tags = _build_run_tags(
        record.tags or [],
        mlflow_tags,
        luml_internal,
        upload_status,
    )
    params = _build_params(data.static_params if data is not None else {})
    metrics = _build_latest_metrics(data.dynamic_metrics if data is not None else {})
    return Run(
        run_info=info,
        run_data=RunData(metrics=metrics, params=params, tags=tags),
    )


def _resolve_run_status(sdk_status: str | None, override_str: str | None) -> int:
    if override_str:
        try:
            return RunStatus.from_string(override_str)
        except Exception:  # noqa: BLE001
            logger.debug(
                "Ignoring unknown MLflow status override %r in metadata",
                override_str,
            )
    if sdk_status is None:
        return RunStatus.RUNNING
    mapping = {
        "active": RunStatus.RUNNING,
        "completed": RunStatus.FINISHED,
        "failed": RunStatus.FAILED,
    }
    return mapping.get(sdk_status, RunStatus.RUNNING)


def _build_run_tags(
    flat_tags: list[str],
    mlflow_tags: dict[str, Any],
    luml_internal: dict[str, Any],
    upload_status: str,
) -> list[RunTag]:
    out: dict[str, str] = {}
    for raw in flat_tags:
        key, value = _decode_flag(raw)
        out[key] = value
    for key, value in mlflow_tags.items():
        out[key] = "" if value is None else str(value)
    for key, value in luml_internal.items():
        out[key] = _json_or_str(value)
    out[LUML_UPLOAD_STATUS] = upload_status
    return [RunTag(k, v) for k, v in out.items()]


def _build_params(static_params: dict[str, Any]) -> list[Param]:
    return [Param(k, _stringify(v)) for k, v in (static_params or {}).items()]


def _build_latest_metrics(
    dynamic_metrics: dict[str, Any],
) -> list[Metric]:
    """Build a Metric per key using the latest (highest-step) value.

    MLflow's RunData.metrics returns the latest value per metric name (history
    is fetched separately via ``get_metric_history``). The SDK ``ExperimentData``
    exposes the full history per key — we collapse it to the latest step here.
    """
    out: list[Metric] = []
    for key, points in (dynamic_metrics or {}).items():
        if not points:
            continue
        latest = max(points, key=lambda p: p.get("step") or 0)
        out.append(
            Metric(
                key=key,
                value=latest["value"],
                timestamp=0,
                step=latest.get("step") or 0,
            )
        )
    return out


def metric_history_to_entities(key: str, history: list[dict[str, Any]]) -> list[Metric]:
    """Convert ``ExperimentTracker.get_experiment_metric_history`` output."""
    out: list[Metric] = []
    for point in history or []:
        timestamp = point.get("logged_at")
        ts_ms = 0
        if timestamp is not None and hasattr(timestamp, "timestamp"):
            ts_ms = int(timestamp.timestamp() * 1000)
        out.append(
            Metric(
                key=key,
                value=point["value"],
                timestamp=ts_ms,
                step=point.get("step") or 0,
            )
        )
    return out


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def _json_or_str(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, list | dict):
        return json.dumps(value)
    return _stringify(value)


__all__ = [
    "LUML_ARTIFACT_IDS",
    "LUML_ARTIFACT_URLS",
    "LUML_COLLECTION_ID",
    "LUML_LOCAL_ONLY",
    "LUML_ORBIT_ID",
    "LUML_ORGANIZATION_ID",
    "LUML_UPLOAD_ERROR",
    "LUML_UPLOAD_STATUS",
    "META_FLAG_TAGS",
    "META_LUML_INTERNAL",
    "META_MLFLOW_TAGS",
    "META_RUN_INFO",
    "MLFLOW_TAG_PREFIX",
    "RESERVED_TAG_PREFIX",
    "RUN_ARTIFACT_URI",
    "RUN_LIFECYCLE_STAGE",
    "RUN_STATUS",
    "RUN_USER_ID",
    "UPLOAD_STATUS_FAILED",
    "UPLOAD_STATUS_NOT_UPLOADED",
    "UPLOAD_STATUS_UNKNOWN",
    "UPLOAD_STATUS_UPLOADED",
    "UPLOAD_STATUS_UPLOADING",
    "delete_tag",
    "is_flag_shaped",
    "metric_history_to_entities",
    "read_run_info_field",
    "reconstruct_run",
    "write_luml_internal",
    "write_run_info_field",
    "write_tag",
    "write_tags",
]
