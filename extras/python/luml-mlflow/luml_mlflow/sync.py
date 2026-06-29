"""Sync orchestrator: upload a finished MLflow run to a luml orbit.

Mirrors ``lumlflow``'s ``ArtifactHandler`` combine-vs-separate logic. Syncing
one run translates to one or more ``luml_api`` ``artifacts.upload`` calls into a
``mixed`` collection named after the MLflow experiment (= luml group). After
upload, the per-run ``luml.*`` metadata is written back (artifact ids/urls,
collection id, status) so the MLflow UI surfaces both the link and the state.

The terminology offset of SPEC.md applies here: an MLflow ``run_id`` is a luml
**experiment** id, and the MLflow experiment name is the luml **group** name —
used as the collection name.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from luml.artifacts.experiment import save_experiment
from luml.artifacts.model import ModelReference
from luml_api._client import LumlClient

from luml_mlflow._tracker import ThreadSafeTracker, get_tracker
from luml_mlflow.config import Settings, get_settings
from luml_mlflow.meta import (
    LUML_ARTIFACT_IDS,
    LUML_ARTIFACT_URLS,
    LUML_COLLECTION_ID,
    LUML_LOCAL_ONLY,
    LUML_ORBIT_ID,
    LUML_ORGANIZATION_ID,
    LUML_UPLOAD_ERROR,
    META_LUML_INTERNAL,
    META_RUN_INFO,
    RUN_ARTIFACT_URI,
    UPLOAD_STATUS_FAILED,
    UPLOAD_STATUS_UPLOADED,
    UPLOAD_STATUS_UPLOADING,
    write_luml_internal,
)
from luml_mlflow.uri import LumlTarget, parse_artifact_uri, parse_tracking_uri

if TYPE_CHECKING:
    from luml.experiments.backends.data_types import Model as DbModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- result types


@dataclass(frozen=True)
class SyncResult:
    """Outcome of syncing a single run."""

    run_id: str
    status: str
    artifact_ids: list[str]
    artifact_urls: list[str]
    collection_id: str | None
    skipped_reason: str | None = None
    error: str | None = None


# ---------------------------------------------------------------- public API


def sync(
    run_id: str,
    *,
    tracking_uri: str | None = None,
    force: bool = False,
    client: LumlClient | None = None,
) -> SyncResult:
    """Sync a single run to its target luml orbit.

    Resolves the target from the run's stored ``artifact_uri`` first, then falls
    back to ``tracking_uri`` if the run has no stored target. Returns a
    :class:`SyncResult` summarising the outcome; local-only or already-uploaded
    runs are reported as skipped with a reason.
    """
    tracker = get_tracker()
    settings = get_settings()
    target = _resolve_target(tracker, run_id, tracking_uri)
    if target is None:
        return SyncResult(
            run_id=run_id,
            status=UPLOAD_STATUS_FAILED,
            artifact_ids=[],
            artifact_urls=[],
            collection_id=None,
            error="Unable to resolve a luml target for the run",
        )
    if target.local_only:
        return SyncResult(
            run_id=run_id,
            status=tracker.get_experiment_upload_status(run_id),
            artifact_ids=[],
            artifact_urls=[],
            collection_id=None,
            skipped_reason="local-only target",
        )

    current_status = tracker.get_experiment_upload_status(run_id)
    if current_status == UPLOAD_STATUS_UPLOADED and not force:
        return SyncResult(
            run_id=run_id,
            status=current_status,
            artifact_ids=_read_internal_list(tracker, run_id, LUML_ARTIFACT_IDS),
            artifact_urls=_read_internal_list(tracker, run_id, LUML_ARTIFACT_URLS),
            collection_id=_read_internal_str(tracker, run_id, LUML_COLLECTION_ID),
            skipped_reason="already uploaded",
        )

    return _do_sync(tracker, settings, target, run_id, client=client)


def sync_experiment(
    experiment_name_or_id: str,
    *,
    tracking_uri: str | None = None,
    force: bool = False,
    client: LumlClient | None = None,
) -> list[SyncResult]:
    """Sync every not-yet-uploaded, non-local run of the given MLflow experiment.

    ``experiment_name_or_id`` may be either the MLflow experiment id (= luml
    group id) or the experiment name. Already-uploaded runs are skipped unless
    ``force=True``.
    """
    tracker = get_tracker()
    group = _resolve_group(tracker, experiment_name_or_id)
    if group is None:
        return []
    results: list[SyncResult] = []
    for record in tracker.list_experiments():
        if record.group_id != group.id:
            continue
        results.append(
            sync(record.id, tracking_uri=tracking_uri, force=force, client=client)
        )
    return results


def status(run_id: str) -> SyncResult:
    """Return a snapshot of a run's upload state (no upload performed)."""
    tracker = get_tracker()
    upload_status = tracker.get_experiment_upload_status(run_id)
    return SyncResult(
        run_id=run_id,
        status=upload_status,
        artifact_ids=_read_internal_list(tracker, run_id, LUML_ARTIFACT_IDS),
        artifact_urls=_read_internal_list(tracker, run_id, LUML_ARTIFACT_URLS),
        collection_id=_read_internal_str(tracker, run_id, LUML_COLLECTION_ID),
        error=_read_internal_str(tracker, run_id, LUML_UPLOAD_ERROR),
    )


# ---------------------------------------------------------------- internals


def _do_sync(
    tracker: ThreadSafeTracker,
    settings: Settings,
    target: LumlTarget,
    run_id: str,
    *,
    client: LumlClient | None = None,
) -> SyncResult:
    tracker.set_experiment_upload_status(run_id, UPLOAD_STATUS_UPLOADING)
    try:
        owned_client = client is None
        if client is None:
            client = _build_client(settings, target)
        try:
            collection_id = _resolve_or_create_collection(
                client, tracker, run_id, settings
            )
            artifact_ids, artifact_urls = _upload_run(
                tracker,
                client,
                run_id,
                collection_id,
                settings,
                target,
            )
        finally:
            if owned_client:
                _close_client(client)
    except Exception as exc:  # noqa: BLE001
        tracker.set_experiment_upload_status(run_id, UPLOAD_STATUS_FAILED)
        write_luml_internal(tracker, run_id, {LUML_UPLOAD_ERROR: str(exc)})
        logger.exception("[luml-mlflow] sync failed for run %s", run_id)
        return SyncResult(
            run_id=run_id,
            status=UPLOAD_STATUS_FAILED,
            artifact_ids=[],
            artifact_urls=[],
            collection_id=None,
            error=str(exc),
        )

    write_luml_internal(
        tracker,
        run_id,
        {
            LUML_ARTIFACT_IDS: artifact_ids,
            LUML_ARTIFACT_URLS: artifact_urls,
            LUML_COLLECTION_ID: collection_id,
            LUML_ORBIT_ID: target.orbit,
            LUML_ORGANIZATION_ID: target.org,
            LUML_UPLOAD_ERROR: None,
        },
    )
    tracker.set_experiment_upload_status(run_id, UPLOAD_STATUS_UPLOADED)
    return SyncResult(
        run_id=run_id,
        status=UPLOAD_STATUS_UPLOADED,
        artifact_ids=artifact_ids,
        artifact_urls=artifact_urls,
        collection_id=collection_id,
    )


def _upload_run(
    tracker: ThreadSafeTracker,
    client: LumlClient,
    run_id: str,
    collection_id: str,
    settings: Settings,
    target: LumlTarget,
) -> tuple[list[str], list[str]]:
    models = tracker.get_models(experiment_id=run_id)
    mode = settings.LUML_MLFLOW_UPLOAD_MODE
    embed = mode == "auto" and len(models) == 1
    with_experiment = not embed

    artifact_ids: list[str] = []
    artifact_urls: list[str] = []
    tags = _run_flag_tags(tracker, run_id)

    for model in models:
        artifact = _upload_model(
            tracker,
            client,
            run_id,
            collection_id,
            model,
            embed=embed,
            tags=tags,
        )
        artifact_ids.append(artifact.id)
        url = _artifact_url(settings, target, collection_id, artifact.id)
        artifact_urls.append(url)

    if with_experiment:
        artifact = _upload_experiment(
            tracker,
            client,
            run_id,
            collection_id,
            tags=tags,
        )
        artifact_ids.append(artifact.id)
        url = _artifact_url(settings, target, collection_id, artifact.id)
        artifact_urls.append(url)

    return artifact_ids, artifact_urls


def _upload_model(
    tracker: ThreadSafeTracker,
    client: LumlClient,
    run_id: str,
    collection_id: str,
    model: DbModel,
    *,
    embed: bool,
    tags: list[str] | None,
) -> Any:
    if not model.path:
        raise ValueError(f"Model {model.name!r} has no file path")
    model_path = str(tracker.backend.base_path / model.path)
    temp_path: str | None = None
    try:
        if embed:
            fd, temp_path = tempfile.mkstemp(suffix=Path(model_path).suffix)
            os.close(fd)
            shutil.copy2(model_path, temp_path)
            tracker.link_to_model(ModelReference(temp_path), run_id)
            upload_path = temp_path
        else:
            upload_path = model_path
        return client.artifacts.upload(
            file_path=upload_path,
            name=model.name,
            tags=tags,
            collection_id=collection_id,
        )
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)


def _upload_experiment(
    tracker: ThreadSafeTracker,
    client: LumlClient,
    run_id: str,
    collection_id: str,
    *,
    tags: list[str] | None,
) -> Any:
    record = tracker.get_experiment_record(run_id)
    if record is None:
        raise ValueError(f"Run {run_id!r} not found in the local tracker")
    fd, output_path = tempfile.mkstemp(suffix=".luml")
    os.close(fd)
    try:
        save_experiment(tracker, run_id, output_path)
        return client.artifacts.upload(
            file_path=output_path,
            name=record.name,
            tags=tags,
            collection_id=collection_id,
        )
    finally:
        Path(output_path).unlink(missing_ok=True)


def _resolve_or_create_collection(
    client: LumlClient,
    tracker: ThreadSafeTracker,
    run_id: str,
    settings: Settings,
) -> str:
    """Find or create the ``mixed`` collection named after the run's group."""
    from luml_api._types import CollectionType

    record = tracker.get_experiment_record(run_id)
    if record is None:
        raise ValueError(f"Run {run_id!r} not found in the local tracker")
    collection_name = record.group_name
    if not collection_name:
        raise ValueError(
            f"Run {run_id!r} has no experiment group; cannot resolve a collection"
        )

    existing = client.collections.get(collection_name)
    if existing is not None:
        if str(existing.type) == CollectionType.MIXED.value:
            return existing.id
        return _handle_collection_conflict(client, collection_name, existing, settings)

    created = client.collections.create(
        description=f"MLflow experiment {collection_name!r}",
        name=collection_name,
        type=CollectionType.MIXED,
    )
    return created.id


def _handle_collection_conflict(
    client: LumlClient,
    name: str,
    existing: Any,
    settings: Settings,
) -> str:
    from luml_api._types import CollectionType

    if settings.LUML_MLFLOW_COLLECTION_CONFLICT == "raise":
        raise ValueError(
            f"Collection {name!r} exists with type {existing.type!r}, not 'mixed'; "
            "set LUML_MLFLOW_COLLECTION_CONFLICT=suffix to use a renamed mixed "
            "collection instead"
        )
    suffix_name = f"{name} (mlflow)"
    existing_suffixed = client.collections.get(suffix_name)
    if existing_suffixed is not None and str(existing_suffixed.type) == (
        CollectionType.MIXED.value
    ):
        return existing_suffixed.id
    created = client.collections.create(
        description=f"MLflow experiment {name!r} (renamed; non-mixed collision)",
        name=suffix_name,
        type=CollectionType.MIXED,
    )
    return created.id


def _resolve_target(
    tracker: ThreadSafeTracker, run_id: str, tracking_uri: str | None
) -> LumlTarget | None:
    """Resolve the upload target for a run.

    Prefer the run's stored ``artifact_uri`` (set at create-run time) — that
    locks the target in even when the active MLflow tracking URI has changed.
    Fall back to the supplied ``tracking_uri``.
    """
    meta = tracker.get_experiment_metadata(run_id)
    artifact_uri = (meta.get(META_RUN_INFO) or {}).get(RUN_ARTIFACT_URI)
    if artifact_uri:
        try:
            return parse_artifact_uri(artifact_uri).target
        except ValueError:
            logger.warning(
                "[luml-mlflow] could not parse artifact_uri %r for run %s",
                artifact_uri,
                run_id,
            )
    luml_internal = meta.get(META_LUML_INTERNAL) or {}
    if luml_internal.get(LUML_LOCAL_ONLY) == "true":
        return LumlTarget(org=None, orbit=None, local_only=True)
    if tracking_uri:
        return parse_tracking_uri(tracking_uri)
    return None


def _resolve_group(tracker: ThreadSafeTracker, name_or_id: str) -> Any | None:
    group = tracker.get_group(name_or_id)
    if group is not None:
        return group
    for candidate in tracker.list_groups():
        if candidate.name == name_or_id:
            return candidate
    return None


def _run_flag_tags(tracker: ThreadSafeTracker, run_id: str) -> list[str] | None:
    """Decode the run's flat ``tags`` list back into clean tag strings.

    The encoding used by ``meta.py`` stores flag-shaped tags as ``"key"`` or
    ``"key="``. For artifact upload we only need the keys themselves — the
    presence/absence already encodes the flag — so we drop the trailing ``=``
    and emit one tag string per key.
    """
    record = tracker.get_experiment_record(run_id)
    if record is None or not record.tags:
        return None
    out: list[str] = []
    for raw in record.tags:
        key = raw[:-1] if raw.endswith("=") else raw
        out.append(key)
    return out or None


def _artifact_url(
    settings: Settings,
    target: LumlTarget,
    collection_id: str,
    artifact_id: str,
) -> str:
    return settings.LUML_ARTIFACT_URL_TEMPLATE.format(
        web=settings.LUML_WEB_URL.rstrip("/"),
        org=target.org or "",
        orbit=target.orbit or "",
        collection=collection_id,
        artifact_id=artifact_id,
    )


def _build_client(settings: Settings, target: LumlTarget) -> LumlClient:
    api_key = _resolve_api_key(settings)
    if not api_key:
        raise ValueError(
            "No luml API key configured (set LUML_API_KEY or run 'lumlflow auth login')"
        )
    return LumlClient(
        base_url=settings.LUML_BASE_URL,
        api_key=api_key,
        organization=target.org,
        orbit=target.orbit,
    )


def _resolve_api_key(settings: Settings) -> str | None:
    """Resolve the API key, mirroring ``lumlflow``'s lookup order.

    Order: ``LUML_API_KEY`` env (already on ``settings``), then
    ``~/.luml.json``, then the system keyring (if available).
    """
    if settings.LUML_API_KEY:
        return settings.LUML_API_KEY
    luml_json = Path.home() / ".luml.json"
    if luml_json.exists():
        with suppress(OSError, json.JSONDecodeError):
            data = json.loads(luml_json.read_text())
            key = data.get("api_key")
            if key:
                return str(key)
    try:
        import keyring
        import keyring.errors as keyring_errors

        with suppress(keyring_errors.KeyringError, keyring_errors.NoKeyringError):
            key = keyring.get_password("lumlflow", "api_key")
            if key:
                return str(key)
    except ImportError:
        pass
    return None


def _close_client(client: LumlClient) -> None:
    closer = getattr(client, "close", None)
    if callable(closer):
        with suppress(Exception):
            closer()


def _read_internal_list(tracker: ThreadSafeTracker, run_id: str, key: str) -> list[str]:
    meta = tracker.get_experiment_metadata(run_id)
    luml = meta.get(META_LUML_INTERNAL) or {}
    value = luml.get(key)
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def _read_internal_str(tracker: ThreadSafeTracker, run_id: str, key: str) -> str | None:
    meta = tracker.get_experiment_metadata(run_id)
    luml = meta.get(META_LUML_INTERNAL) or {}
    value = luml.get(key)
    if value is None:
        return None
    return str(value)


__all__ = [
    "SyncResult",
    "status",
    "sync",
    "sync_experiment",
]
