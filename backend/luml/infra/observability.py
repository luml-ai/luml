import logging
import os
import re
from collections.abc import Sequence
from typing import Any, Protocol

import logfire
from fastapi import FastAPI
from logfire import ScrubbingOptions, ScrubMatch
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.sdk.util.instrumentation import InstrumentationScope
from opentelemetry.trace import Status
from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import AsyncEngine

from luml.handlers.platform_admin import PLATFORM_ADMIN_LOGGER
from luml.settings import Settings

SCRUBBING_PATTERNS = (
    r"\btoken\b",
    r"\bdsn\b",
    r"\bbearer\b",
    r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+",
    r"://[^\s/@]+@",
)

STACK_LOCATION_LINE = re.compile(r'^\s*File ".*", line \d+, in .+$')


def redact(_match: ScrubMatch) -> str:
    return "[Scrubbed]"


SCRUBBING = ScrubbingOptions(extra_patterns=SCRUBBING_PATTERNS, callback=redact)

ScrubPath = tuple[str | int, ...]


class Scrubber(Protocol):
    def scrub_value(
        self, path: ScrubPath, value: object
    ) -> tuple[object, Sequence[object]]: ...


class SanitizedSpanExporter(SpanExporter):
    ATTRIBUTE_NAMES = frozenset(
        {
            "http.method",
            "http.request.method",
            "http.status_code",
            "http.response.status_code",
            "http.route",
            "db.system",
            "db.system.name",
            "code.filepath",
            "code.lineno",
            "code.function",
            "logfire.logger_name",
            "logfire.level_num",
            "logfire.span_type",
        }
    )

    def __init__(
        self,
        exporter: SpanExporter,
        resource: Resource,
        scrubber: Scrubber | None = None,
    ) -> None:
        self.exporter = exporter
        self.resource = resource
        self.scrubber = scrubber

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        sanitized = []
        for span in spans:
            source = span.attributes or {}
            attributes = {
                key: value
                for key, value in source.items()
                if key in self.ATTRIBUTE_NAMES
            }
            message = template = None
            if "logfire.logger_name" in attributes:
                attributes = {
                    key: value
                    for key, value in attributes.items()
                    if not key.startswith(("http.", "db."))
                }
                name = "application log"
                message = self._scrub(
                    ("attributes", "logfire.msg"), source.get("logfire.msg")
                )
                template = self._scrub(
                    ("attributes", "logfire.msg_template"),
                    source.get("logfire.msg_template"),
                )
            elif "http.route" in attributes:
                method = attributes.get("http.method", "HTTP")
                name = f"{method} {attributes['http.route']}"
            elif "http.method" in attributes:
                name = f"HTTP {attributes['http.method']}"
            elif "db.system" in attributes:
                name = (
                    "database connection"
                    if span.name == "connect"
                    else "database query"
                )
            else:
                name = "application operation"
            attributes["logfire.msg"] = message or name
            attributes["logfire.msg_template"] = template or name
            events = [
                self._exception_event(index, event)
                for index, event in enumerate(span.events)
                if event.attributes and "exception.type" in event.attributes
            ]
            sanitized.append(
                ReadableSpan(
                    name=name,
                    context=span.context,
                    parent=span.parent,
                    resource=self.resource,
                    attributes=attributes,
                    events=events,
                    kind=span.kind,
                    status=Status(span.status.status_code),
                    start_time=span.start_time,
                    end_time=span.end_time,
                    instrumentation_scope=InstrumentationScope("luml.observability"),
                )
            )
        return self.exporter.export(sanitized)

    def _exception_event(self, index: int, event: Event) -> Event:
        source = event.attributes or {}
        path: ScrubPath = ("otel_events", index, "attributes")
        attributes: dict[str, Any] = {"exception.type": source["exception.type"]}
        message = self._scrub(
            (*path, "exception.message"), source.get("exception.message")
        )
        if message is not None:
            attributes["exception.message"] = message
        stacktrace = source.get("exception.stacktrace")
        if isinstance(stacktrace, str) and self.scrubber is not None:
            attributes["exception.stacktrace"] = "\n".join(
                line
                if STACK_LOCATION_LINE.match(line)
                else self._scrub((*path, "exception.stacktrace", number), line) or ""
                for number, line in enumerate(stacktrace.splitlines())
            )
        return Event(name="exception", attributes=attributes, timestamp=event.timestamp)

    def _scrub(self, path: ScrubPath, value: object) -> str | None:
        if value is None or self.scrubber is None:
            return None
        return str(self.scrubber.scrub_value(path, str(value))[0])

    def shutdown(self) -> None:
        self.exporter.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self.exporter.force_flush(timeout_millis)


def configure_observability(
    app: FastAPI, engine: AsyncEngine | Engine, settings: Settings
) -> None:
    if (
        not settings.LOGFIRE_TOKEN
        or not settings.LOGFIRE_TOKEN.get_secret_value().strip()
    ):
        return

    resource = Resource(
        {
            "service.name": "luml-backend",
            "service.version": settings.LOGFIRE_SERVICE_VERSION,
            "deployment.environment.name": settings.LOGFIRE_ENVIRONMENT,
        }
    )
    exporter = OTLPSpanExporter(
        endpoint=f"{settings.LOGFIRE_BASE_URL}/v1/traces",
        headers={"Authorization": settings.LOGFIRE_TOKEN.get_secret_value()},
    )
    os.environ.update(
        OTEL_TRACES_EXPORTER="none",
        OTEL_LOGS_EXPORTER="none",
        OTEL_METRICS_EXPORTER="none",
    )
    sanitized = SanitizedSpanExporter(exporter, resource)
    instance = logfire.configure(
        local=True,
        send_to_logfire=False,
        console=False,
        metrics=False,
        inspect_arguments=False,
        add_baggage_to_attributes=False,
        distributed_tracing=False,
        scrubbing=SCRUBBING,
        service_name="luml-backend",
        service_version=settings.LOGFIRE_SERVICE_VERSION,
        environment=settings.LOGFIRE_ENVIRONMENT,
        additional_span_processors=[BatchSpanProcessor(sanitized)],
    )
    sanitized.scrubber = instance.config.scrubber
    instance.instrument_fastapi(
        app,
        capture_headers=False,
        excluded_urls=r"/health(?:/|\?|$)",
        request_attributes_mapper=lambda _request, _attributes: None,
    )
    instance.instrument_sqlalchemy(engine=engine)
    instance.instrument_httpx()
    handler = logfire.LogfireLoggingHandler(
        logfire_instance=instance, fallback=logging.NullHandler()
    )
    logging.getLogger("luml").setLevel(logging.INFO)
    logging.getLogger().addHandler(handler)
    platform_logger = logging.getLogger(PLATFORM_ADMIN_LOGGER)
    if not platform_logger.propagate:
        platform_logger.addHandler(handler)
