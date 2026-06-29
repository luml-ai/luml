"""In-memory rendezvous for spans whose owning run is not yet known.

MLflow's V3 trace exporter (``mlflow.tracing.export.mlflow_v3``) logs a trace's
spans and its trace info through two *separate* store calls — ``log_spans`` and
``start_trace`` — and, with async trace logging on (the default), dispatches both
onto a worker thread pool, so they run concurrently. Only ``start_trace`` carries
``mlflow.sourceRun`` — the sole signal of which run (= luml experiment = SQLite
db) owns the trace — so ``log_spans`` cannot persist a span until ``start_trace``
resolves the run.

This buffer is the rendezvous between those two racing calls. Under a single lock
it makes the park-vs-flush decision atomic so no interleaving can lose a span:

* ``add`` (from ``log_spans``) parks spans for a not-yet-resolved trace, **or** —
  if ``resolve`` already ran for that trace — declines to park and hands the
  resolution back so the caller writes (or drops) the spans immediately.
* ``resolve`` (from ``start_trace``) records the owning run (``None`` => the trace
  is runless and rejected) and returns any already-parked spans to flush.

Because both read ``_resolved`` and mutate ``_pending`` under the same lock,
whichever call runs second observes the other's effect: an ``add`` that lands
after ``resolve`` is routed (not orphaned), and a ``resolve`` that lands after
``add`` drains the parked spans.

The pending buffer is bounded by trace count and age. Traces whose ``start_trace``
never arrives (root span never finalized, process killed mid-trace) are evicted
with a warning, so memory cannot grow without bound and drops are never silent.
This mirrors MLflow's own semantics for incomplete traces: a trace with no
completed root span is never attached to a run by any backend.
"""

import atexit
import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache

from mlflow.entities import Span

logger = logging.getLogger(__name__)

_DEFAULT_MAX_PENDING_TRACES = 2048
_DEFAULT_TTL_SECONDS = 3600.0


@dataclass
class _Pending:
    first_seen: float
    spans: list[Span] = field(default_factory=list)


class PendingSpanBuffer:
    def __init__(
        self,
        max_pending_traces: int = _DEFAULT_MAX_PENDING_TRACES,
        ttl_seconds: float = _DEFAULT_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_pending_traces = max_pending_traces
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._pending: OrderedDict[str, _Pending] = OrderedDict()
        self._resolved: OrderedDict[str, str | None] = OrderedDict()

    def add(self, trace_id: str, spans: list[Span]) -> tuple[bool, str | None]:
        """Park ``spans`` for a not-yet-resolved trace, or report a prior resolution.

        Returns ``(resolved, run_id)``:

        * ``(False, None)`` — the trace is unresolved; ``spans`` were parked and the
          caller does nothing until ``resolve`` drains them.
        * ``(True, run_id)`` — ``resolve`` already ran for this trace, so ``spans``
          were **not** parked. ``run_id`` is the owning run to write them to, or
          ``None`` if the trace was rejected as runless and the caller drops them.
        """
        if not spans:
            return False, None
        with self._lock:
            self._evict_expired()
            if trace_id in self._resolved:
                self._resolved.move_to_end(trace_id)
                return True, self._resolved[trace_id]
            entry = self._pending.get(trace_id)
            if entry is None:
                entry = _Pending(first_seen=self._clock())
                self._pending[trace_id] = entry
            entry.spans.extend(spans)
            self._pending.move_to_end(trace_id)
            self._evict_overflow()
            return False, None

    def resolve(self, trace_id: str, run_id: str | None) -> list[Span]:
        """Record a trace's owning run and return its parked spans to flush.

        ``run_id`` is the owning run id, or ``None`` to reject a runless trace.
        Parked spans are returned either way (the caller writes them when a run is
        given, drops them when ``None``). After ``resolve``, a later ``add`` for the
        same trace short-circuits via the recorded resolution instead of parking, so
        spans racing in behind ``start_trace`` are never orphaned.
        """
        with self._lock:
            self._resolved[trace_id] = run_id
            self._resolved.move_to_end(trace_id)
            while len(self._resolved) > self._max_pending_traces:
                self._resolved.popitem(last=False)
            entry = self._pending.pop(trace_id, None)
            return entry.spans if entry is not None else []

    def drain(self) -> dict[str, int]:
        """Clear the buffer, returning ``{trace_id: span_count}`` of what was held."""
        with self._lock:
            held = {tid: len(e.spans) for tid, e in self._pending.items()}
            self._pending.clear()
            return held

    def _evict_expired(self) -> None:
        now = self._clock()
        expired = [
            tid
            for tid, entry in self._pending.items()
            if now - entry.first_seen > self._ttl_seconds
        ]
        for tid in expired:
            entry = self._pending.pop(tid)
            logger.warning(
                "[luml-mlflow] dropping %d buffered span(s) for trace %r: no "
                "start_trace within %.0fs, run never resolved",
                len(entry.spans),
                tid,
                self._ttl_seconds,
            )

    def _evict_overflow(self) -> None:
        while len(self._pending) > self._max_pending_traces:
            tid, entry = self._pending.popitem(last=False)
            logger.warning(
                "[luml-mlflow] dropping %d buffered span(s) for oldest pending "
                "trace %r: pending-trace cap of %d exceeded",
                len(entry.spans),
                tid,
                self._max_pending_traces,
            )


@cache
def get_buffer() -> PendingSpanBuffer:
    """Return the process-wide pending-span buffer."""
    return PendingSpanBuffer()


def reset_buffer() -> None:
    """Drop the process-wide buffer (tests only)."""
    get_buffer.cache_clear()


@atexit.register
def _warn_on_undrained_spans() -> None:
    held = get_buffer().drain()
    if not held:
        return
    logger.warning(
        "[luml-mlflow] %d span(s) across %d trace(s) never received a "
        "start_trace and were not persisted: %s",
        sum(held.values()),
        len(held),
        ", ".join(sorted(held)),
    )
