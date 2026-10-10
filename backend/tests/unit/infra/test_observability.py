import json
import logging
import os
import subprocess
import sys
import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from luml.infra.observability import SanitizedSpanExporter, configure_observability
from luml.settings import config
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.sdk.util.instrumentation import InstrumentationScope
from opentelemetry.trace import Status, StatusCode
from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine, text


@pytest.fixture
def captured_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[InMemorySpanExporter]:
    for signal in ("TRACES", "LOGS", "METRICS"):
        monkeypatch.setenv(f"OTEL_{signal}_EXPORTER", "otlp")
    exporter = InMemorySpanExporter()
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    platform_logger = logging.getLogger("luml.platform_admin")
    original_platform_handlers = platform_logger.handlers[:]
    original_platform_propagation = platform_logger.propagate
    app_logger = logging.getLogger("luml")
    original_app_level = app_logger.level
    with (
        patch("luml.infra.observability.OTLPSpanExporter", return_value=exporter),
        patch("luml.infra.observability.BatchSpanProcessor", SimpleSpanProcessor),
    ):
        yield exporter
    root.handlers[:] = original_handlers
    platform_logger.handlers[:] = original_platform_handlers
    platform_logger.propagate = original_platform_propagation
    app_logger.setLevel(original_app_level)
    HTTPXClientInstrumentor().uninstrument()
    SQLAlchemyInstrumentor().uninstrument()


@pytest.mark.parametrize("token", [None, SecretStr(""), SecretStr("  ")])
def test_no_token_does_not_configure_or_export(token: SecretStr | None) -> None:
    app = FastAPI()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    settings = config.model_copy(update={"LOGFIRE_TOKEN": token})
    with (
        patch("luml.infra.observability.logfire.configure") as configure,
        patch("luml.infra.observability.OTLPSpanExporter") as exporter,
    ):
        configure_observability(app, engine, settings)
    configure.assert_not_called()
    exporter.assert_not_called()
    assert TestClient(app).get("/openapi.json").status_code == 200
    engine.dispose()


@pytest.mark.parametrize("environment", ["dev", "staging", "prod"])
def test_exported_telemetry_is_useful_and_contains_no_request_or_sql_data(
    captured_telemetry: InMemorySpanExporter, environment: str, http_server: str
) -> None:
    app = FastAPI()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    settings = config.model_copy(
        update={
            "LOGFIRE_TOKEN": SecretStr("test-token"),
            "LOGFIRE_ENVIRONMENT": environment,
            "LOGFIRE_SERVICE_VERSION": "test-version",
        }
    )
    configure_observability(app, engine, settings)

    @app.get("/items/{item_id}")
    def items(item_id: str, email: str) -> dict[str, bool]:
        with engine.connect() as connection:
            connection.execute(text("SELECT 'sql-private-value'"))
        with httpx.Client() as outgoing:
            assert (
                outgoing.get(
                    f"{http_server}/outgoing-private-value?api_key=http-private-value",
                    headers={"Authorization": "Bearer header-private-value"},
                ).status_code
                == 200
            )
        logging.getLogger("luml.test").info(
            "DSN %s",
            "postgresql://person:db-private-value@localhost/test",
            extra={
                "opaque": "log-extra-private-value",
                "http.route": "log-route-private-value",
                "db.system": "log-db-private-value",
            },
        )
        return {"ok": True}

    @app.post("/items")
    def create_item(payload: dict[str, str]) -> dict[str, bool]:
        return {"ok": True}

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/failure")
    def failure() -> None:
        raise RuntimeError("exception-private-value")

    client = TestClient(app, raise_server_exceptions=False)
    assert (
        client.get("/items/path-private-value?email=person@example.com").status_code
        == 200
    )
    assert (
        client.post("/items", json={"opaque": "body-private-value"}).status_code == 200
    )
    assert client.get("/failure").status_code == 500
    assert client.get("/health?token=health-private-value").status_code == 200
    spans = captured_telemetry.get_finished_spans()
    assert not any((s.attributes or {}).get("http.route") == "/health" for s in spans)

    serialized = json.dumps([json.loads(span.to_json()) for span in spans])
    for private_value in (
        "sql-private-value",
        "db-private-value",
        "log-extra-private-value",
        "log-route-private-value",
        "log-db-private-value",
        "exception-private-value",
        "path-private-value",
        "person@example.com",
        "health-private-value",
        "outgoing-private-value",
        "http-private-value",
        "header-private-value",
        "body-private-value",
    ):
        assert private_value not in serialized
    assert any(
        (s.attributes or {}).get("http.route") == "/items/{item_id}" for s in spans
    )
    assert any((s.attributes or {}).get("http.status_code") == 500 for s in spans)
    assert any((s.attributes or {}).get("db.system") == "sqlite" for s in spans)
    assert any(s.kind.name == "CLIENT" and s.name == "HTTP GET" for s in spans)
    assert sum(s.name == "database query" for s in spans) == 1
    assert any(
        (s.attributes or {}).get("logfire.logger_name") == "luml.test" for s in spans
    )
    assert any(
        (event.attributes or {}).get("exception.type") == "RuntimeError"
        for span in spans
        for event in span.events
    )
    for span in spans:
        assert span.resource.attributes["service.name"] == "luml-backend"
        assert span.resource.attributes["service.version"] == "test-version"
        assert span.resource.attributes["deployment.environment.name"] == environment
    engine.dispose()


def test_unapproved_export_destination_is_rejected() -> None:
    with pytest.raises(ValidationError):
        config.model_validate(
            {**config.model_dump(), "LOGFIRE_BASE_URL": "https://untrusted.example"}
        )


def test_export_failure_does_not_fail_a_request(
    captured_telemetry: InMemorySpanExporter,
) -> None:
    app = FastAPI()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    configure_observability(
        app,
        engine,
        config.model_copy(update={"LOGFIRE_TOKEN": SecretStr("test-token")}),
    )
    with patch.object(
        captured_telemetry, "export", side_effect=RuntimeError("offline")
    ):
        assert TestClient(app).get("/openapi.json").status_code == 200
    engine.dispose()


@pytest.fixture
def http_server() -> Generator[str]:
    class RequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass

    server = HTTPServer(("127.0.0.1", 0), RequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def test_export_boundary_removes_untrusted_names_metadata_and_error_details() -> None:
    target = InMemorySpanExporter()
    exporter = SanitizedSpanExporter(target, Resource({"service.name": "luml-backend"}))
    span = ReadableSpan(
        name="span-private-value",
        attributes={"unknown": "attribute-private-value"},
        resource=Resource({"dsn": "resource-private-value"}),
        status=Status(StatusCode.ERROR, "status-private-value"),
        instrumentation_scope=InstrumentationScope("scope-private-value"),
        start_time=1,
        end_time=2,
    )
    exporter.export([span])
    exported = target.get_finished_spans()[0]
    assert "private-value" not in exported.to_json()
    assert exported.status.status_code == StatusCode.ERROR
    assert exported.start_time == 1
    assert exported.end_time == 2


def test_backend_and_migration_import_without_observability_configuration() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from luml.server import app; from utils.db import migrate_db; "
            "assert app.openapi()['info']['title'] == 'LUML AI API'",
        ],
        env={**os.environ, "PYTEST_VERSION": "1", "LOGFIRE_TOKEN": ""},
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0


def test_legacy_otlp_settings_cannot_bypass_the_export_filter(
    captured_telemetry: InMemorySpanExporter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:1")
    engine = create_engine("sqlite://")
    with (
        patch("logfire._internal.config.OTLPSpanExporter") as trace_exporter,
        patch("logfire._internal.config.OTLPLogExporter") as log_exporter,
        patch("logfire._internal.config.OTLPMetricExporter") as metric_exporter,
    ):
        configure_observability(
            FastAPI(),
            engine,
            config.model_copy(update={"LOGFIRE_TOKEN": SecretStr("test-token")}),
        )
    trace_exporter.assert_not_called()
    log_exporter.assert_not_called()
    metric_exporter.assert_not_called()
    engine.dispose()


@pytest.mark.parametrize("propagate", [True, False])
def test_platform_admin_logs_are_forwarded_once(
    captured_telemetry: InMemorySpanExporter, propagate: bool
) -> None:
    platform_logger = logging.getLogger("luml.platform_admin")
    platform_logger.propagate = propagate
    engine = create_engine("sqlite://")
    configure_observability(
        FastAPI(),
        engine,
        config.model_copy(update={"LOGFIRE_TOKEN": SecretStr("test-token")}),
    )
    logging.getLogger("luml.platform_admin.audit").info("audit-private-value")
    spans = captured_telemetry.get_finished_spans()
    audit_spans = [
        span
        for span in spans
        if (span.attributes or {}).get("logfire.logger_name")
        == "luml.platform_admin.audit"
    ]
    assert len(audit_spans) == 1
    assert "audit-private-value" not in audit_spans[0].to_json()
    engine.dispose()
