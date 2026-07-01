import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from agent.clients.model_server_client import ModelServerError
from agent.handlers.model_server_handler import (
    ModelServerHandler,
    _extract_safe_inputs,
)
from agent.monitoring.instrumentation import InferenceInstrumentation
from agent.monitoring.testing import FakeTelemetry
from agent.schemas.deployments import LocalDeployment

DEP_ID = "dep-instr-1"


def _local_deployment(
    *,
    monitoring_enabled: bool = True,
    secrets: dict[str, str] | None = None,
) -> LocalDeployment:
    return LocalDeployment(
        deployment_id=DEP_ID,
        dynamic_attributes_secrets=secrets,
        monitoring_enabled=monitoring_enabled,
    )


class TestDisabledRecordsNothing:
    @respx.mock
    async def test_no_telemetry_when_monitoring_disabled(
        self,
        fake_telemetry: FakeTelemetry,
        mock_model_server: respx.MockRouter,
    ) -> None:
        handler = ModelServerHandler(telemetry=fake_telemetry.setup)
        handler.deployments[DEP_ID] = _local_deployment(monitoring_enabled=False)

        result, event_id = await handler.model_compute(
            DEP_ID, {"dynamic_attributes": {"x": 1}}
        )

        assert result == {"prediction": 42}
        assert event_id is None
        assert len(fake_telemetry.events) == 0
        assert len(fake_telemetry.spans) == 0

    @respx.mock
    async def test_no_telemetry_when_no_instrumentation(
        self,
        mock_model_server: respx.MockRouter,
    ) -> None:
        handler = ModelServerHandler(telemetry=None)
        handler.deployments[DEP_ID] = _local_deployment(monitoring_enabled=True)

        result, event_id = await handler.model_compute(
            DEP_ID, {"dynamic_attributes": {"x": 1}}
        )

        assert result == {"prediction": 42}
        assert event_id is None


class TestHappyPath:
    @respx.mock
    async def test_records_event_metrics_span(
        self,
        fake_telemetry: FakeTelemetry,
        mock_model_server: respx.MockRouter,
    ) -> None:
        handler = ModelServerHandler(telemetry=fake_telemetry.setup)
        handler.deployments[DEP_ID] = _local_deployment()

        result, event_id = await handler.model_compute(
            DEP_ID, {"dynamic_attributes": {"feature_a": 1.0}}
        )

        assert result == {"prediction": 42}
        assert event_id is not None
        uuid.UUID(event_id)

        assert len(fake_telemetry.events) == 1
        evt = fake_telemetry.events[0]
        assert evt.event_id == event_id
        assert evt.deployment_id == DEP_ID
        assert evt.status == "success"
        assert evt.latency_ms > 0
        assert evt.inputs == {"feature_a": 1.0}
        assert evt.output == {"prediction": 42}
        assert evt.trace_id is not None
        assert evt.span_id is not None

        spans = fake_telemetry.spans
        assert len(spans) == 1
        assert spans[0].name == "inference"
        assert spans[0].attributes["deployment_id"] == DEP_ID
        assert spans[0].attributes["event_id"] == event_id

        metrics = fake_telemetry.get_metrics()
        assert "inference.requests" in metrics
        assert "inference.latency_ms" in metrics

    @respx.mock
    async def test_event_id_is_valid_uuid(
        self,
        fake_telemetry: FakeTelemetry,
        mock_model_server: respx.MockRouter,
    ) -> None:
        handler = ModelServerHandler(telemetry=fake_telemetry.setup)
        handler.deployments[DEP_ID] = _local_deployment()

        _, event_id = await handler.model_compute(
            DEP_ID, {"dynamic_attributes": {"x": 1}}
        )

        parsed = uuid.UUID(event_id)
        assert parsed.version == 7


class TestModelErrorRecordedAndReraised:
    @respx.mock
    async def test_model_error_records_event_and_raises(
        self,
        fake_telemetry: FakeTelemetry,
    ) -> None:
        respx.get(url__regex=r"http://sat-[^/]+:\d+/healthz").mock(
            return_value=httpx.Response(200, json={"status": "healthy"})
        )
        respx.get(url__regex=r"http://sat-[^/]+:\d+/manifest").mock(
            return_value=httpx.Response(200, json={})
        )
        respx.get(url__regex=r"http://sat-[^/]+:\d+/openapi\.json").mock(
            return_value=httpx.Response(200, json={})
        )
        respx.post(url__regex=r"http://sat-[^/]+:\d+/compute").mock(
            return_value=httpx.Response(422, json={"error": "bad input"})
        )

        handler = ModelServerHandler(telemetry=fake_telemetry.setup)
        handler.deployments[DEP_ID] = _local_deployment()

        with pytest.raises(ModelServerError) as exc_info:
            await handler.model_compute(
                DEP_ID, {"dynamic_attributes": {"x": 1}}
            )

        assert exc_info.value.status_code == 422
        assert exc_info.value.detail == "bad input"

        assert len(fake_telemetry.events) == 1
        evt = fake_telemetry.events[0]
        assert evt.status == "error"
        assert evt.status_code == 422
        assert "bad input" in evt.error
        assert evt.event_id is not None

        metrics = fake_telemetry.get_metrics()
        assert "inference.errors" in metrics
        assert "inference.requests" in metrics

    @respx.mock
    async def test_runtime_error_records_and_raises(
        self,
        fake_telemetry: FakeTelemetry,
    ) -> None:
        respx.post(url__regex=r"http://sat-[^/]+:\d+/compute").mock(
            side_effect=httpx.ConnectError("connection refused")
        )

        handler = ModelServerHandler(telemetry=fake_telemetry.setup)
        handler.deployments[DEP_ID] = _local_deployment()

        with pytest.raises(RuntimeError, match="Model server request failed"):
            await handler.model_compute(
                DEP_ID, {"dynamic_attributes": {"x": 1}}
            )

        assert len(fake_telemetry.events) == 1
        evt = fake_telemetry.events[0]
        assert evt.status == "error"
        assert evt.status_code is None


class TestTelemetryFailureDoesNotBreakInference:
    @respx.mock
    async def test_broken_event_exporter_still_returns_result(
        self,
        fake_telemetry: FakeTelemetry,
        mock_model_server: respx.MockRouter,
    ) -> None:
        original_emit = fake_telemetry.event_exporter.emit
        fake_telemetry.event_exporter.emit = lambda e: (_ for _ in ()).throw(
            RuntimeError("exporter down")
        )

        handler = ModelServerHandler(telemetry=fake_telemetry.setup)
        handler.deployments[DEP_ID] = _local_deployment()

        result, event_id = await handler.model_compute(
            DEP_ID, {"dynamic_attributes": {"x": 1}}
        )

        assert result == {"prediction": 42}
        assert event_id is not None

        fake_telemetry.event_exporter.emit = original_emit


class TestSecretsAbsentFromEvent:
    @respx.mock
    async def test_secret_backed_attrs_excluded_from_inputs(
        self,
        fake_telemetry: FakeTelemetry,
        mock_model_server: respx.MockRouter,
    ) -> None:
        handler = ModelServerHandler(telemetry=fake_telemetry.setup)
        handler.deployments[DEP_ID] = _local_deployment(
            secrets={"api_key": "secret-uuid-123"},
        )

        with patch.object(
            ModelServerHandler,
            "get_compute_missing_secrets",
            new_callable=AsyncMock,
            return_value={"feature_a": 1.0, "api_key": "super-secret-value"},
        ):
            result, event_id = await handler.model_compute(
                DEP_ID,
                {"dynamic_attributes": {"feature_a": 1.0}},
            )

        assert result == {"prediction": 42}
        assert len(fake_telemetry.events) == 1
        evt = fake_telemetry.events[0]
        assert evt.inputs == {"feature_a": 1.0}
        assert "api_key" not in (evt.inputs or {})

    @respx.mock
    async def test_no_secrets_all_inputs_recorded(
        self,
        fake_telemetry: FakeTelemetry,
        mock_model_server: respx.MockRouter,
    ) -> None:
        handler = ModelServerHandler(telemetry=fake_telemetry.setup)
        handler.deployments[DEP_ID] = _local_deployment(secrets=None)

        result, _ = await handler.model_compute(
            DEP_ID,
            {"dynamic_attributes": {"a": 1, "b": 2}},
        )

        assert result == {"prediction": 42}
        evt = fake_telemetry.events[0]
        assert evt.inputs == {"a": 1, "b": 2}


class TestExtractSafeInputs:
    def test_excludes_secret_keys(self) -> None:
        body = {"dynamic_attributes": {"feature": 1.0, "api_key": "val"}}
        dep = _local_deployment(secrets={"api_key": "secret-id"})
        result = _extract_safe_inputs(body, dep)
        assert result == {"feature": 1.0}
        assert "api_key" not in result

    def test_no_secrets_returns_all(self) -> None:
        body = {"dynamic_attributes": {"a": 1, "b": 2}}
        dep = _local_deployment(secrets=None)
        result = _extract_safe_inputs(body, dep)
        assert result == {"a": 1, "b": 2}

    def test_no_dynamic_attributes_returns_none(self) -> None:
        body = {"other_key": "value"}
        dep = _local_deployment()
        result = _extract_safe_inputs(body, dep)
        assert result is None

    def test_empty_dynamic_attributes(self) -> None:
        body = {"dynamic_attributes": {}}
        dep = _local_deployment(secrets={"api_key": "secret-id"})
        result = _extract_safe_inputs(body, dep)
        assert result == {}


class TestTraceContextPropagation:
    @respx.mock
    async def test_traceparent_header_sent(
        self,
        fake_telemetry: FakeTelemetry,
    ) -> None:
        captured_headers: dict[str, str] = {}

        def capture_request(request: httpx.Request) -> httpx.Response:
            for k, v in request.headers.items():
                if k.lower() == "traceparent":
                    captured_headers["traceparent"] = v
            return httpx.Response(200, json={"prediction": 42})

        respx.post(url__regex=r"http://sat-[^/]+:\d+/compute").mock(
            side_effect=capture_request
        )

        handler = ModelServerHandler(telemetry=fake_telemetry.setup)
        handler.deployments[DEP_ID] = _local_deployment()

        await handler.model_compute(
            DEP_ID, {"dynamic_attributes": {"x": 1}}
        )

        assert "traceparent" in captured_headers
        parts = captured_headers["traceparent"].split("-")
        assert len(parts) == 4
        assert parts[0] == "00"


class TestInferenceInstrumentationUnit:
    async def test_instrumented_compute_success(
        self,
        fake_telemetry: FakeTelemetry,
    ) -> None:
        instr = InferenceInstrumentation(fake_telemetry.setup)

        async def forward_fn(*, extra_headers: dict[str, str] | None = None) -> dict:
            return {"result": "ok"}

        result, event_id = await instr.instrumented_compute(
            deployment_id="dep-unit",
            safe_inputs={"x": 1},
            forward_fn=forward_fn,
        )

        assert result == {"result": "ok"}
        assert event_id is not None
        assert len(fake_telemetry.events) == 1
        assert fake_telemetry.events[0].status == "success"

    async def test_instrumented_compute_error(
        self,
        fake_telemetry: FakeTelemetry,
    ) -> None:
        instr = InferenceInstrumentation(fake_telemetry.setup)

        async def forward_fn(*, extra_headers: dict[str, str] | None = None) -> dict:
            raise ModelServerError(500, "internal")

        with pytest.raises(ModelServerError):
            await instr.instrumented_compute(
                deployment_id="dep-unit",
                safe_inputs={"x": 1},
                forward_fn=forward_fn,
            )

        assert len(fake_telemetry.events) == 1
        assert fake_telemetry.events[0].status == "error"
        assert fake_telemetry.events[0].status_code == 500
