from collections.abc import Callable, Sequence
from typing import Any

from opentelemetry.sdk.trace import Event, ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import Link, SpanKind, Status, StatusCode
from opentelemetry.util.types import Attributes


class DataforceSpanExporter(SpanExporter):
    def __init__(
        self,
        log_fn: Callable,
        batch_size: int = 100,
    ) -> None:
        self.log_fn = log_fn
        self.batch_size = batch_size
        self._shutdown = False

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        if self._shutdown:
            return SpanExportResult.FAILURE

        if not spans:
            return SpanExportResult.SUCCESS

        try:
            for span in spans:
                try:
                    self._export_single_span(span)
                except Exception as e:
                    print(f"Failed to export span {span.name}: {e}")  # noqa: T201
                    continue

            return SpanExportResult.SUCCESS

        except Exception:
            return SpanExportResult.FAILURE

    def _export_single_span(self, span: ReadableSpan) -> None:
        trace_id = f"{span.context.trace_id:032x}"  # type: ignore
        span_id = f"{span.context.span_id:016x}"  # type: ignore
        parent_span_id = None

        if span.parent:
            parent_span_id = f"{span.parent.span_id:016x}"

        kind = self._convert_span_kind(span.kind)
        status_code, status_message = self._convert_status(span.status)
        attributes = self._convert_attributes(span.attributes)

        events = self._convert_events(span.events)

        links = self._convert_links(span.links)

        trace_flags = span.context.trace_flags  # type: ignore
        print(f"Exporting span: {span.name} (trace_id={trace_id}, span_id={span_id})")  # noqa: T201

        self.log_fn(
            trace_id=trace_id,
            span_id=span_id,
            name=span.name,
            start_time_unix_nano=span.start_time,
            end_time_unix_nano=span.end_time,
            parent_span_id=parent_span_id,
            kind=kind,
            status_code=status_code,
            status_message=status_message,
            attributes=attributes,
            events=events,
            links=links,
            trace_flags=trace_flags,
        )

    def _convert_span_kind(self, kind: SpanKind) -> int:
        kind_map = {
            "UNSPECIFIED": 0,
            "INTERNAL": 1,
            "SERVER": 2,
            "CLIENT": 3,
            "PRODUCER": 4,
            "CONSUMER": 5,
        }
        return kind_map.get(str(kind).split(".")[-1], 0)

    def _convert_status(self, status: Status) -> tuple[int, str | None]:
        if status is None:
            return 0, None  # UNSET

        status_code_map = {
            StatusCode.UNSET: 0,
            StatusCode.OK: 1,
            StatusCode.ERROR: 2,
        }

        code = status_code_map.get(status.status_code, 0)
        message = status.description if hasattr(status, "description") else None

        return code, message

    def _convert_attributes(
        self, attributes: Attributes | None
    ) -> dict[str, Any] | None:
        if not attributes:
            return None

        result = {}
        for key, value in attributes.items():
            if isinstance(value, str | int | float | bool):
                result[key] = value
            elif isinstance(value, list | tuple):
                result[key] = list(value)
            else:
                result[key] = str(value)

        return result

    def _convert_events(self, events: list[Event]) -> list[dict[str, Any]] | None:
        if not events:
            return None

        result = []
        for event in events:
            event_dict = {
                "name": event.name,
                "timestamp": event.timestamp,
            }

            if hasattr(event, "attributes") and event.attributes:
                event_dict["attributes"] = self._convert_attributes(event.attributes)

            result.append(event_dict)

        return result

    def _convert_links(self, links: list[Link]) -> list[dict[str, Any]] | None:
        if not links:
            return None

        result = []
        for link in links:
            link_dict = {
                "trace_id": f"{link.context.trace_id:032x}",
                "span_id": f"{link.context.span_id:016x}",
                "trace_flags": link.context.trace_flags,
            }

            if hasattr(link, "attributes") and link.attributes:
                link_dict["attributes"] = self._convert_attributes(link.attributes)

            result.append(link_dict)

        return result

    def shutdown(self) -> None:
        self._shutdown = True

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        try:
            return True
        except Exception:
            return False
