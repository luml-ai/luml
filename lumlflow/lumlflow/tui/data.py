"""Data-access facade for the TUI.

The TUI never imports FastAPI and never touches the routers. Every
screen talks to data through `DataFacade`, which owns one shared
`ThreadSafeTracker` and one instance of each handler class
(`ExperimentsHandler`, `ExperimentGroupsHandler`, `ModelsHandler`,
`AnnotationsHandler`, `AuthHandler`, `LumlHandler`, `ArtifactHandler`).

The facade exposes intent-named read/mutate methods that delegate to
the handlers and return the handlers' existing Pydantic schemas
unchanged. It translates the handlers' `ApplicationError` / `NotFound`
into a uniform `Result[T]` the UI can render without knowing about
HTTP.

Blocking handler calls are offloaded to Textual worker threads via
`run_in_worker(...)`. Reads tolerate transient SQLite lock errors with
bounded retry/backoff so a concurrent external writer never crashes
the app.
"""

from __future__ import annotations

import asyncio
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from luml.experiments.tracker import ExperimentTracker

from lumlflow.handlers.annotations import AnnotationsHandler
from lumlflow.handlers.auth import AuthHandler
from lumlflow.handlers.experiment_groups import ExperimentGroupsHandler
from lumlflow.handlers.experiments import ExperimentsHandler
from lumlflow.handlers.luml.artifacts import ArtifactHandler
from lumlflow.handlers.luml.luml import LumlHandler
from lumlflow.handlers.models import ModelsHandler
from lumlflow.infra.exceptions import ApplicationError
from lumlflow.infra.progress_store import ProgressStore
from lumlflow.schemas.annotations import (
    Annotation,
    AnnotationSummary,
    CreateAnnotation,
    UpdateAnnotation,
)
from lumlflow.schemas.auth import SetApiKey
from lumlflow.schemas.base import SortOrder
from lumlflow.schemas.experiment_groups import (
    Group,
    GroupDetails,
    GroupsSortBy,
    PaginatedGroups,
    UpdateGroup,
)
from lumlflow.schemas.experiments import (
    AttachmentRecord,
    Eval,
    EvalColumns,
    EvalTypedColumns,
    Experiment,
    ExperimentDetails,
    ExperimentMetricHistory,
    FileNode,
    PaginatedBatchEvals,
    PaginatedEvals,
    PaginatedExperiments,
    PaginatedTraces,
    SearchValidationResult,
    TraceColumns,
    TraceDetails,
    TracesSortBy,
    TraceState,
    TraceTypedColumns,
    UpdateExperiment,
)
from lumlflow.schemas.luml import (
    Orbit,
    Organization,
    PaginatedCollections,
    UploadArtifactForm,
    UploadFileForm,
    UploadModelForm,
)
from lumlflow.schemas.models import Model, UpdateModel

# Retry envelope for transient SQLite lock errors. Reads only — mutations
# bubble up so the user can see the failure.
_LOCK_RETRY_ATTEMPTS = 5
_LOCK_RETRY_INITIAL_DELAY = 0.02  # 20ms; doubles each retry
_LOCK_RETRY_MAX_DELAY = 0.5


@dataclass(frozen=True)
class FacadeError:
    """A uniform error shape the UI renders.

    `code` mirrors the handlers' HTTP status semantics so screens can
    map it to a UX without depending on FastAPI:

    - 404: missing/not-found  → friendly empty state
    - 409: constraint failure → explanatory toast
    - 400: bad input          → inline validation
    - 401: auth required      → publish flow gate
    - 502: upstream failure   → "could not reach …" toast
    - 500: anything else      → generic error toast (app stays usable)
    """

    code: int
    message: str

    @property
    def is_not_found(self) -> bool:
        return self.code == 404

    @property
    def is_conflict(self) -> bool:
        return self.code == 409

    @property
    def is_validation(self) -> bool:
        return self.code == 400


@dataclass(frozen=True)
class Result[T]:
    """Success-or-error envelope returned by every facade method."""

    value: T | None = None
    error: FacadeError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @classmethod
    def success(cls, value: T) -> Result[T]:
        return cls(value=value, error=None)

    @classmethod
    def failure(cls, code: int, message: str) -> Result[T]:
        return cls(value=None, error=FacadeError(code=code, message=message))

    def unwrap(self) -> T:
        """Return the value or raise — convenience for tests."""

        if self.error is not None:
            raise RuntimeError(f"Result is an error: {self.error}")
        # value can legitimately be None for void operations (delete).
        return self.value  # type: ignore[return-value]


def _is_transient_lock(exc: BaseException) -> bool:
    """Return True if the exception looks like a transient SQLite lock."""

    if isinstance(exc, sqlite3.OperationalError):
        msg = str(exc).lower()
        return "locked" in msg or "busy" in msg
    # Some backends wrap sqlite errors in their own exception type with the
    # underlying message preserved.
    msg = str(exc).lower()
    return "database is locked" in msg or "database is busy" in msg


def _to_result(exc: ApplicationError) -> Result[Any]:
    """Map an `ApplicationError`/`NotFound` to a `Result.failure`."""

    return Result.failure(code=exc.status_code, message=exc.message)


class DataFacade:
    """One-stop data layer for every TUI screen.

    The facade is constructed once at app start with a shared tracker
    and one instance of each handler. All public methods return
    `Result[Schema]` — never raise — and are safe to call from worker
    threads. Read methods retry transient SQLite lock errors with
    exponential backoff so a concurrent external writer never crashes
    the app.

    The facade is *not* responsible for thread-offloading the calls;
    that is the screen's job via `run_in_worker(...)`. Every method on
    the facade is synchronous and blocking — call it on a worker thread.
    """

    def __init__(
        self,
        *,
        tracker: ExperimentTracker | None = None,
        progress_store: ProgressStore | None = None,
        retry_attempts: int = _LOCK_RETRY_ATTEMPTS,
        retry_initial_delay: float = _LOCK_RETRY_INITIAL_DELAY,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        # Lazy import: avoids construction of the default tracker (and a
        # filesystem touch) for callers that pass their own.
        if tracker is None:
            from lumlflow.settings import get_tracker

            tracker = get_tracker()
        self.tracker = tracker
        self.progress_store = progress_store or ProgressStore()
        self._retry_attempts = max(1, retry_attempts)
        self._retry_initial_delay = retry_initial_delay
        self._sleep = sleep or time.sleep
        # Serialize every tracker access. Screens fan reads out across
        # Textual worker threads (e.g. the metrics grid fetches one
        # history per chart concurrently); a shared SQLite tracker is not
        # safe under truly concurrent access, so we funnel all handler
        # calls through this lock. Held only around each call — never
        # across the retry backoff sleeps — so a slow read cannot starve
        # the others beyond its own duration.
        self._lock = threading.RLock()

        self.groups = ExperimentGroupsHandler(tracker=tracker)
        self.experiments = ExperimentsHandler(tracker=tracker)
        self.models = ModelsHandler(tracker=tracker)
        self.annotations = AnnotationsHandler(tracker=tracker)
        self.auth = AuthHandler()
        self.luml = LumlHandler(tracker=tracker)
        self.artifacts = ArtifactHandler(progress_store=self.progress_store)
        # ArtifactHandler accepts tracker only via its super; override it
        # so all handlers share the same tracker instance.
        self.artifacts.tracker = tracker

    # ----- core helpers -----

    def _read[T](self, fn: Callable[[], T]) -> Result[T]:
        """Run a read with bounded retry on transient SQLite lock errors."""

        delay = self._retry_initial_delay
        last_exc: BaseException | None = None
        for attempt in range(self._retry_attempts):
            try:
                with self._lock:
                    return Result.success(fn())
            except ApplicationError as exc:
                # Handlers wrap underlying errors in ApplicationError(500). If
                # the underlying cause is a transient lock, treat as transient
                # and retry — otherwise surface the mapped error to the UI.
                cause = exc.__cause__ or exc.__context__
                transient = cause is not None and _is_transient_lock(cause)
                if not transient:
                    return _to_result(exc)
                last_exc = exc
            except Exception as exc:
                if not _is_transient_lock(exc):
                    # Unexpected non-ApplicationError — map to 500 so the UI
                    # surfaces a generic error toast and stays usable.
                    return Result.failure(500, str(exc))
                last_exc = exc

            # Transient: back off before the next attempt (no sleep on the last).
            if attempt + 1 < self._retry_attempts:
                self._sleep(min(delay, _LOCK_RETRY_MAX_DELAY))
                delay *= 2

        # Exhausted all retries on transient lock errors.
        return Result.failure(
            500,
            f"database busy after {self._retry_attempts} retries: {last_exc!s}"
            if last_exc is not None
            else "database busy",
        )

    def _mutate[T](self, fn: Callable[[], T]) -> Result[T]:
        """Run a mutation. No retry — the user sees the failure."""

        try:
            with self._lock:
                return Result.success(fn())
        except ApplicationError as exc:
            return _to_result(exc)
        except Exception as exc:
            return Result.failure(500, str(exc))

    # ----- groups -----

    def list_groups(
        self,
        *,
        limit: int = 100,
        cursor: str | None = None,
        sort_by: GroupsSortBy = GroupsSortBy.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
        search: str | None = None,
    ) -> Result[PaginatedGroups]:
        return self._read(
            lambda: self.groups.get_experiment_groups(
                limit=limit,
                cursor_str=cursor,
                sort_by=sort_by,
                order=order,
                search=search,
            )
        )

    def get_group(self, group_id: str) -> Result[GroupDetails]:
        return self._read(lambda: self.groups.get_experiment_group_details(group_id))

    def update_group(self, group_id: str, body: UpdateGroup) -> Result[Group]:
        return self._mutate(lambda: self.groups.update_experiment_group(group_id, body))

    def delete_group(self, group_id: str) -> Result[None]:
        return self._mutate(lambda: self.groups.delete_experiment_group(group_id))

    def list_group_experiments(
        self,
        group_id: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
        sort_by: str = "created_at",
        order: SortOrder = SortOrder.DESC,
        search: str | None = None,
    ) -> Result[PaginatedExperiments]:
        return self._read(
            lambda: self.groups.list_group_experiments(
                group_id,
                limit=limit,
                cursor_str=cursor,
                sort_by=sort_by,
                order=order,
                search=search,
            )
        )

    def list_groups_experiments(
        self,
        group_ids: list[str],
        *,
        limit: int = 20,
        cursor: str | None = None,
        sort_by: str = "created_at",
        order: SortOrder = SortOrder.DESC,
        search: str | None = None,
    ) -> Result[PaginatedExperiments]:
        return self._read(
            lambda: self.groups.list_groups_experiments(
                group_ids,
                limit=limit,
                cursor_str=cursor,
                sort_by=sort_by,
                order=order,
                search=search,
            )
        )

    def validate_experiments_search(
        self, query: str | None
    ) -> Result[SearchValidationResult]:
        return self._read(lambda: self.groups.validate_search(query))

    # ----- experiments -----

    def get_experiment(self, experiment_id: str) -> Result[ExperimentDetails]:
        return self._read(lambda: self.experiments.get_experiment(experiment_id))

    def update_experiment(
        self, experiment_id: str, body: UpdateExperiment
    ) -> Result[Experiment]:
        return self._mutate(
            lambda: self.experiments.update_experiment(experiment_id, body)
        )

    def delete_experiment(self, experiment_id: str) -> Result[None]:
        return self._mutate(lambda: self.experiments.delete_experiment(experiment_id))

    def get_metric_history(
        self, experiment_id: str, key: str, *, max_points: int = 1000
    ) -> Result[ExperimentMetricHistory]:
        return self._read(
            lambda: self.experiments.get_experiment_metric_history(
                experiment_id, key, max_points=max_points
            )
        )

    def list_traces(
        self,
        experiment_id: str,
        *,
        limit: int = 20,
        cursor: str | None = None,
        sort_by: TracesSortBy = TracesSortBy.EXECUTION_TIME,
        order: SortOrder = SortOrder.DESC,
        search: str | None = None,
        filters: list[str] | None = None,
        states: list[TraceState] | None = None,
    ) -> Result[PaginatedTraces]:
        return self._read(
            lambda: self.experiments.get_experiment_traces(
                experiment_id,
                limit=limit,
                cursor=cursor,
                sort_by=sort_by,
                order=order,
                search=search,
                filters=filters,
                states=states,
            )
        )

    def get_trace(self, experiment_id: str, trace_id: str) -> Result[TraceDetails]:
        return self._read(lambda: self.experiments.get_trace(experiment_id, trace_id))

    def list_evals(
        self,
        experiment_id: str,
        *,
        limit: int = 20,
        cursor: str | None = None,
        sort_by: str = "created_at",
        order: SortOrder = SortOrder.DESC,
        dataset_id: str | None = None,
        search: str | None = None,
        filters: list[str] | None = None,
    ) -> Result[PaginatedEvals]:
        return self._read(
            lambda: self.experiments.get_experiment_evals(
                experiment_id,
                limit=limit,
                cursor=cursor,
                sort_by=sort_by,
                order=order,
                dataset_id=dataset_id,
                search=search,
                filters=filters,
            )
        )

    def list_evals_for_compare(
        self,
        experiment_ids: list[str],
        *,
        limit: int = 20,
        cursor: str | None = None,
        dataset_id: str | None = None,
        search: str | None = None,
        filters: list[str] | None = None,
    ) -> Result[PaginatedBatchEvals]:
        return self._read(
            lambda: self.experiments.get_experiment_evals_for_compare(
                experiment_ids,
                limit=limit,
                cursor=cursor,
                dataset_id=dataset_id,
                search=search,
                filters=filters,
            )
        )

    def get_eval(self, experiment_id: str, eval_id: str) -> Result[Eval]:
        return self._read(lambda: self.experiments.get_eval(experiment_id, eval_id))

    def get_eval_dataset_ids(self, experiment_id: str) -> Result[list[str]]:
        return self._read(
            lambda: self.experiments.get_experiment_eval_dataset_ids(experiment_id)
        )

    def get_eval_average_scores(
        self,
        experiment_id: str,
        *,
        dataset_id: str | None = None,
        search: str | None = None,
        filters: list[str] | None = None,
    ) -> Result[dict[str, float]]:
        return self._read(
            lambda: self.experiments.get_experiment_eval_average_scores(
                experiment_id,
                dataset_id=dataset_id,
                search=search,
                filters=filters,
            )
        )

    def get_trace_columns(self, experiment_id: str) -> Result[TraceColumns]:
        return self._read(
            lambda: self.experiments.get_experiment_trace_columns(experiment_id)
        )

    def get_trace_typed_columns(self, experiment_id: str) -> Result[TraceTypedColumns]:
        return self._read(
            lambda: self.experiments.get_experiment_trace_typed_columns(experiment_id)
        )

    def get_eval_columns(
        self, experiment_id: str, *, dataset_id: str | None = None
    ) -> Result[EvalColumns]:
        return self._read(
            lambda: self.experiments.get_experiment_eval_columns(
                experiment_id, dataset_id=dataset_id
            )
        )

    def get_eval_typed_columns(
        self, experiment_id: str, *, dataset_id: str | None = None
    ) -> Result[EvalTypedColumns]:
        return self._read(
            lambda: self.experiments.get_experiment_eval_typed_columns(
                experiment_id, dataset_id=dataset_id
            )
        )

    def validate_evals_filter(
        self, filter_strings: list[str]
    ) -> Result[list[SearchValidationResult]]:
        return self._read(
            lambda: self.experiments.validate_evals_filter(filter_strings)
        )

    def validate_traces_filter(
        self, filter_strings: list[str]
    ) -> Result[list[SearchValidationResult]]:
        return self._read(
            lambda: self.experiments.validate_traces_filter(filter_strings)
        )

    # ----- attachments -----

    def list_attachments(self, experiment_id: str) -> Result[list[AttachmentRecord]]:
        return self._read(lambda: self.experiments.list_attachments(experiment_id))

    def list_attachments_tree(
        self, experiment_id: str, *, parent_path: str | None = None
    ) -> Result[list[FileNode]]:
        return self._read(
            lambda: self.experiments.list_attachments_tree(
                experiment_id, parent_path=parent_path
            )
        )

    def get_attachment(self, experiment_id: str, file_path: str) -> Result[bytes]:
        return self._read(
            lambda: self.experiments.get_attachment(experiment_id, file_path)
        )

    # ----- models -----

    def list_experiment_models(self, experiment_id: str) -> Result[list[Model]]:
        return self._read(lambda: self.models.list_experiment_models(experiment_id))

    def get_model(self, model_id: str) -> Result[Model]:
        return self._read(lambda: self.models.get_model(model_id))

    def update_model(self, model_id: str, body: UpdateModel) -> Result[Model]:
        return self._mutate(lambda: self.models.update_model(model_id, body))

    def delete_model(self, model_id: str) -> Result[None]:
        return self._mutate(lambda: self.models.delete_model(model_id))

    # ----- annotations -----

    def create_eval_annotation(
        self,
        experiment_id: str,
        dataset_id: str,
        eval_id: str,
        body: CreateAnnotation,
    ) -> Result[Annotation]:
        return self._mutate(
            lambda: self.annotations.create_eval_annotation(
                experiment_id, dataset_id, eval_id, body
            )
        )

    def list_eval_annotations(
        self, experiment_id: str, dataset_id: str, eval_id: str
    ) -> Result[list[Annotation]]:
        return self._read(
            lambda: self.annotations.get_eval_annotations(
                experiment_id, dataset_id, eval_id
            )
        )

    def update_eval_annotation(
        self, experiment_id: str, annotation_id: str, body: UpdateAnnotation
    ) -> Result[Annotation]:
        return self._mutate(
            lambda: self.annotations.update_eval_annotation(
                experiment_id, annotation_id, body
            )
        )

    def delete_eval_annotation(
        self, experiment_id: str, annotation_id: str
    ) -> Result[None]:
        return self._mutate(
            lambda: self.annotations.delete_eval_annotation(
                experiment_id, annotation_id
            )
        )

    def create_span_annotation(
        self,
        experiment_id: str,
        trace_id: str,
        span_id: str,
        body: CreateAnnotation,
    ) -> Result[Annotation]:
        return self._mutate(
            lambda: self.annotations.create_span_annotation(
                experiment_id, trace_id, span_id, body
            )
        )

    def list_span_annotations(
        self, experiment_id: str, trace_id: str, span_id: str
    ) -> Result[list[Annotation]]:
        return self._read(
            lambda: self.annotations.get_span_annotations(
                experiment_id, trace_id, span_id
            )
        )

    def update_span_annotation(
        self, experiment_id: str, annotation_id: str, body: UpdateAnnotation
    ) -> Result[Annotation]:
        return self._mutate(
            lambda: self.annotations.update_span_annotation(
                experiment_id, annotation_id, body
            )
        )

    def delete_span_annotation(
        self, experiment_id: str, annotation_id: str
    ) -> Result[None]:
        return self._mutate(
            lambda: self.annotations.delete_span_annotation(
                experiment_id, annotation_id
            )
        )

    def get_trace_annotation_summary(
        self, experiment_id: str, trace_id: str
    ) -> Result[AnnotationSummary]:
        return self._read(
            lambda: self.annotations.get_trace_annotation_summary(
                experiment_id, trace_id
            )
        )

    def get_eval_annotation_summary(
        self, experiment_id: str, dataset_id: str
    ) -> Result[AnnotationSummary]:
        return self._read(
            lambda: self.annotations.get_eval_annotation_summary(
                experiment_id, dataset_id
            )
        )

    # ----- auth + cloud -----

    def has_api_key(self) -> Result[bool]:
        return self._read(lambda: self.auth.has_api_key())

    def set_api_key(self, api_key: str) -> Result[None]:
        return self._mutate(lambda: self.auth.set_api_key(SetApiKey(api_key=api_key)))

    def list_organizations(self) -> Result[list[Organization]]:
        return self._read(lambda: self.luml.get_luml_organizations())

    def list_orbits(self, organization_id: str) -> Result[list[Orbit]]:
        return self._read(lambda: self.luml.get_luml_orbits(organization_id))

    def list_collections(
        self,
        organization_id: str,
        orbit_id: str,
        *,
        start_after: str | None = None,
        limit: int = 50,
        search: str | None = None,
    ) -> Result[PaginatedCollections]:
        return self._read(
            lambda: self.luml.get_luml_collections(
                organization_id,
                orbit_id,
                start_after=start_after,
                limit=limit,
                search=search,
            )
        )

    def upload_artifact(self, data: UploadArtifactForm, job_id: str) -> Result[None]:
        """Run the upload synchronously. Progress is reported via the
        shared `ProgressStore` (`facade.progress_store`)."""

        return self._mutate(lambda: self.artifacts.upload_artifact(data, job_id))

    def upload_model_artifact(
        self, data: UploadModelForm, job_id: str
    ) -> Result[None]:
        """Upload one specific linked model as a cloud artifact."""

        return self._mutate(lambda: self.artifacts.upload_model(data, job_id))

    def upload_file_artifact(
        self, data: UploadFileForm, job_id: str
    ) -> Result[None]:
        """Upload an arbitrary file from disk as a cloud artifact.

        The manual counterpart of `upload_artifact` — nothing is derived
        from a tracked experiment. Progress flows through the same
        shared `ProgressStore`."""

        return self._mutate(lambda: self.artifacts.upload_file(data, job_id))


# ----- async/worker offload helpers -----


def run_in_thread[T](fn: Callable[[], T]) -> asyncio.Future[T]:
    """Run a blocking callable on a background daemon thread.

    Returns a `Future` that resolves on the current event loop. This is
    the low-level primitive; screens normally use `run_in_worker` (the
    Textual-flavored wrapper) so the work is tracked as a Textual
    Worker and benefits from the framework's cancellation/lifecycle.
    """

    loop = asyncio.get_event_loop()
    future: asyncio.Future[T] = loop.create_future()

    def target() -> None:
        try:
            result = fn()
        except BaseException as exc:  # pragma: no cover - defensive
            loop.call_soon_threadsafe(future.set_exception, exc)
            return
        loop.call_soon_threadsafe(future.set_result, result)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return future


def run_in_worker[T](
    node: Any,
    fn: Callable[[], T],
    *,
    name: str = "",
    group: str = "facade",
    exclusive: bool = False,
) -> Any:
    """Schedule a blocking facade call on a Textual worker thread.

    Textual's event loop is single-threaded; SQLite handler calls
    block. We must never run them on the loop. `node` is the App or
    Screen whose worker pool owns the task — its lifecycle bounds the
    work (cancelled when the screen is popped, etc.).

    The returned `Worker` exposes `result` (sync access once finished)
    and is awaitable via `await worker.wait()`.
    """

    return node.run_worker(
        fn,
        name=name,
        group=group,
        thread=True,
        exclusive=exclusive,
        exit_on_error=False,
    )


__all__ = (
    "DataFacade",
    "FacadeError",
    "Result",
    "run_in_thread",
    "run_in_worker",
)
