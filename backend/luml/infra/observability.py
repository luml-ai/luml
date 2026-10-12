import logging
import os
from collections.abc import Sequence

import logfire
from fastapi import FastAPI
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


class SanitizedSpanExporter(SpanExporter):
    # free-form values can contain secrets even when their keys look harmless
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

    def __init__(self, exporter: SpanExporter, resource: Resource) -> None:
        self.exporter = exporter
        self.resource = resource

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        sanitized = []
        for span in spans:
            attributes = {
                key: value
                for key, value in (span.attributes or {}).items()
                if key in self.ATTRIBUTE_NAMES
            }
            if "logfire.logger_name" in attributes:
                attributes = {
                    key: value
                    for key, value in attributes.items()
                    if not key.startswith(("http.", "db."))
                }
                name = "application log"
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
            attributes["logfire.msg"] = name
            attributes["logfire.msg_template"] = name
            events = [
                Event(
                    name="exception",
                    attributes={"exception.type": event.attributes["exception.type"]},
                    timestamp=event.timestamp,
                )
                for event in span.events
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
    # legacy otlp environment variables must not create an unfiltered exporter
    os.environ.update(
        OTEL_TRACES_EXPORTER="none",
        OTEL_LOGS_EXPORTER="none",
        OTEL_METRICS_EXPORTER="none",
    )
    instance = logfire.configure(
        local=True,
        send_to_logfire=False,
        console=False,
        metrics=False,
        inspect_arguments=False,
        add_baggage_to_attributes=False,
        distributed_tracing=False,
        service_name="luml-backend",
        service_version=settings.LOGFIRE_SERVICE_VERSION,
        environment=settings.LOGFIRE_ENVIRONMENT,
        additional_span_processors=[
            BatchSpanProcessor(SanitizedSpanExporter(exporter, resource))
        ],
    )
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
