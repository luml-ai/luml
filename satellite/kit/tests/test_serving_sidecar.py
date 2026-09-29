import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from luml_satellite.monitoring import InferenceInstrumentation
from luml_satellite.monitoring.ingest.testing import FakeTelemetry
from luml_satellite.serving import (
    CompanionAuthorization,
    CompanionMetadata,
    CompanionRecordingPolicy,
    CompanionRefusedError,
    CompanionSecrets,
    CompanionUnavailableError,
    Sidecar,
    SidecarConfiguration,
)
from luml_satellite.workload import DeploymentMetadata, NoOpRecorder
from tests.helpers import ARTIFACT_ID, DEPLOYMENT_ID

AUTHORIZATION = {"Authorization": "Bearer key"}
COMPANION_TOKEN = "companion-token"


@dataclass
class ControlledSleep:
    calls: asyncio.Queue[float] = field(default_factory=asyncio.Queue)
    resumes: asyncio.Queue[None] = field(default_factory=asyncio.Queue)

    async def __call__(self, seconds: float) -> None:
        await self.calls.put(seconds)
        await self.resumes.get()

    async def next_delay(self) -> float:
        return await asyncio.wait_for(self.calls.get(), timeout=1)

    def release(self) -> None:
        self.resumes.put_nowait(None)


@dataclass
class FakeClock:
    now: float = 0.0

    def __call__(self) -> float:
        return self.now


@dataclass
class FakeCompanion:
    current_metadata: CompanionMetadata
    failure: CompanionUnavailableError | None = None
    metadata_calls: int = 0
    authorization_calls: list[str] = field(default_factory=list)
    secret_values: dict[str, str] = field(default_factory=dict)
    secret_calls: int = 0

    async def metadata(self) -> CompanionMetadata:
        self.metadata_calls += 1
        if self.failure is not None:
            raise self.failure
        return self.current_metadata

    async def authorize(self, api_key: str) -> CompanionAuthorization:
        self.authorization_calls.append(api_key)
        if self.failure is not None:
            raise self.failure
        return CompanionAuthorization(authorized=api_key == "key", ttl_seconds=1)

    async def secrets(self) -> CompanionSecrets:
        self.secret_calls += 1
        if self.failure is not None:
            raise self.failure
        return CompanionSecrets(values=self.secret_values, ttl_seconds=60)


def configuration(**overrides: object) -> SidecarConfiguration:
    values: dict[str, object] = {
        "DEPLOYMENT_ID": DEPLOYMENT_ID,
        "SATELLITE_INTERNAL_URL": "http://satellite:8001",
        "COMPANION_TOKEN": COMPANION_TOKEN,
        "UPSTREAM_MODEL_URL": "http://model:8080",
        "COMPANION_CACHE_TTL_SECONDS": 1,
        "COMPANION_CACHE_REFRESH_AHEAD_SECONDS": 0.25,
        "COMPANION_STALE_ALLOWANCE_SECONDS": 10,
        "RECORDING_SAMPLE_RATE": 1,
    }
    values.update(overrides)
    return SidecarConfiguration.model_validate(values)


def metadata(
    *,
    monitoring: bool = True,
    sample_rate: float = 1.0,
    secret_attributes: list[str] | None = None,
    ttl_seconds: float = 1.0,
) -> CompanionMetadata:
    return CompanionMetadata(
        deployment_id=DEPLOYMENT_ID,
        secret_attributes=secret_attributes or [],
        monitoring_enabled=monitoring,
        metadata=DeploymentMetadata(name="classifier", status="active"),
        artifact_id=ARTIFACT_ID,
        recording_policy=CompanionRecordingPolicy(
            sample_rate=sample_rate,
            body_max_bytes=1024,
        ),
        ttl_seconds=ttl_seconds,
    )


def upstream_transport(
    trace_headers: list[str | None] | None = None,
    bodies: list[dict[str, object]] | None = None,
) -> httpx.MockTransport:
    async def upstream(request: httpx.Request) -> httpx.Response:
        responses = {
            "/healthz": httpx.Response(200, json={"status": "healthy"}),
            "/manifest": httpx.Response(
                200,
                json={"producer_tags": ["luml.ai::tabular_monitoring:v1"]},
            ),
            "/openapi.json": httpx.Response(200, json={"openapi": "3.1.0", "paths": {}}),
            "/reference_profile": httpx.Response(
                200,
                json={
                    "profile_status": "ready",
                    "feature_summaries": {"numerical_features": {"x": {"mean": 1}}},
                },
            ),
        }
        if request.url.path == "/compute":
            if trace_headers is not None:
                trace_headers.append(request.headers.get("traceparent"))
            if bodies is not None:
                bodies.append(json.loads(await request.aread()))
            return httpx.Response(200, json={"prediction": 42})
        return responses[request.url.path]

    return httpx.MockTransport(upstream)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        CompanionUnavailableError("satellite down"),
        CompanionRefusedError(404),
    ],
    ids=["satellite-down", "not-registered"],
)
async def test_sidecar_boot_is_independent_of_companion_metadata(
    failure: CompanionUnavailableError,
) -> None:
    sleeper = ControlledSleep()
    companion = FakeCompanion(metadata(), failure=failure)
    sidecar = Sidecar(
        configuration(),
        companion=companion,
        upstream_transport=upstream_transport(),
        recorder=NoOpRecorder(),
        sleep=sleeper,
    )
    await sidecar.start()
    await sleeper.next_delay()

    async with (
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=sidecar.application),
            base_url="http://sidecar",
        ) as serving,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=sidecar.internal_application),
            base_url="http://sidecar-internal",
        ) as internal,
    ):
        live = await serving.get("/livez")
        compute_before_metadata = await serving.post(
            f"/deployments/{DEPLOYMENT_ID}/compute",
            headers=AUTHORIZATION,
            json={"inputs": {"x": 1}},
        )
        unguarded_internal = await internal.get("/manifest")
        guarded_internal = await internal.get(
            "/manifest",
            headers={"Authorization": f"Bearer {COMPANION_TOKEN}"},
        )

        companion.failure = None
        sleeper.release()
        assert await sleeper.next_delay() == 1
        compute_after_metadata = await serving.post(
            f"/deployments/{DEPLOYMENT_ID}/compute",
            headers=AUTHORIZATION,
            json={"inputs": {"x": 1}},
        )

    await sidecar.aclose()

    assert live.status_code == 200
    assert compute_before_metadata.status_code == 503
    assert unguarded_internal.status_code == 403
    assert guarded_internal.status_code == 200
    assert compute_after_metadata.status_code == 200
    assert compute_after_metadata.json() == {"prediction": 42}


@pytest.mark.asyncio
async def test_sidecar_keeps_serving_cached_authorization_and_secrets_during_restart() -> None:
    clock = FakeClock()
    sleeper = ControlledSleep()
    companion = FakeCompanion(
        metadata(secret_attributes=["password"], ttl_seconds=60),
        secret_values={"password": "first"},
    )
    upstream_bodies: list[dict[str, object]] = []
    sidecar = Sidecar(
        configuration(
            COMPANION_CACHE_TTL_SECONDS=60,
            COMPANION_CACHE_REFRESH_AHEAD_SECONDS=15,
            COMPANION_STALE_ALLOWANCE_SECONDS=600,
        ),
        companion=companion,
        upstream_transport=upstream_transport(bodies=upstream_bodies),
        recorder=NoOpRecorder(),
        clock=clock,
        sleep=sleeper,
    )
    await sidecar.start()
    assert await sleeper.next_delay() == 60

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=sidecar.application),
        base_url="http://sidecar",
    ) as client:
        initial = await client.post(
            f"/deployments/{DEPLOYMENT_ID}/compute",
            headers=AUTHORIZATION,
            json={"inputs": {"x": 1}},
        )

        companion.failure = CompanionUnavailableError("satellite down")
        clock.now = 61
        during_restart = await client.post(
            f"/deployments/{DEPLOYMENT_ID}/compute",
            headers=AUTHORIZATION,
            json={"inputs": {"x": 2}},
        )

        companion.failure = None
        companion.secret_values = {"password": "second"}
        clock.now = 62
        after_restart = await client.post(
            f"/deployments/{DEPLOYMENT_ID}/compute",
            headers=AUTHORIZATION,
            json={"inputs": {"x": 3}},
        )

    await sidecar.aclose()

    assert [initial.status_code, during_restart.status_code, after_restart.status_code] == [
        200,
        200,
        200,
    ]
    assert [body["dynamic_attributes"] for body in upstream_bodies] == [
        {"password": "first"},
        {"password": "first"},
        {"password": "second"},
    ]
    assert companion.authorization_calls == ["key", "key", "key"]
    assert companion.secret_calls == 3


@pytest.mark.asyncio
async def test_metadata_refresh_changes_monitoring_and_remote_policy_wins(
    fake_telemetry: FakeTelemetry,
) -> None:
    sleeper = ControlledSleep()
    companion = FakeCompanion(metadata(sample_rate=0.25))
    trace_headers: list[str | None] = []
    recorder = InferenceInstrumentation(fake_telemetry.setup, random_source=lambda: 0.5)
    sidecar = Sidecar(
        configuration(RECORDING_SAMPLE_RATE=1),
        companion=companion,
        upstream_transport=upstream_transport(trace_headers),
        recorder=recorder,
        sleep=sleeper,
    )
    await sidecar.start()
    assert await sleeper.next_delay() == 1

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=sidecar.application),
        base_url="http://sidecar",
    ) as client:
        first = await client.post(
            f"/deployments/{DEPLOYMENT_ID}/compute",
            headers=AUTHORIZATION,
            json={"inputs": {"x": 1}},
        )

        companion.current_metadata = metadata(monitoring=False)
        sleeper.release()
        assert await sleeper.next_delay() == 1
        disabled = await client.post(
            f"/deployments/{DEPLOYMENT_ID}/compute",
            headers=AUTHORIZATION,
            json={"inputs": {"x": 2}},
        )

        companion.current_metadata = metadata(monitoring=True, sample_rate=0.75)
        sleeper.release()
        assert await sleeper.next_delay() == 1
        enabled = await client.post(
            f"/deployments/{DEPLOYMENT_ID}/compute",
            headers=AUTHORIZATION,
            json={"inputs": {"x": 3}},
        )

    await sidecar.aclose()

    assert first.headers.get("x-event-id") is not None
    assert disabled.headers.get("x-event-id") is None
    assert enabled.headers.get("x-event-id") is not None
    assert len(fake_telemetry.events) == 2
    assert fake_telemetry.events[0].bodies_sampled is False
    assert fake_telemetry.events[1].bodies_sampled is True
    assert trace_headers[0] is not None and trace_headers[0].startswith("00-")
    assert trace_headers[1] is None
    assert trace_headers[2] is not None and trace_headers[2].startswith("00-")


@pytest.mark.asyncio
async def test_sidecar_selects_noop_without_an_endpoint_and_monitoring_with_one(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)
    companion = FakeCompanion(metadata())
    without_endpoint = Sidecar(
        configuration(),
        companion=companion,
        upstream_transport=upstream_transport(),
    )
    with_endpoint = Sidecar(
        configuration(OTEL_EXPORTER_OTLP_ENDPOINT="http://collector:4317"),
        companion=companion,
        upstream_transport=upstream_transport(),
    )
    try:
        assert isinstance(without_endpoint.recorder, NoOpRecorder)
        assert isinstance(with_endpoint.recorder, InferenceInstrumentation)
        warnings = [
            record for record in caplog.records if "no telemetry endpoint" in record.getMessage()
        ]
        assert len(warnings) == 1
    finally:
        await without_endpoint.aclose()
        await with_endpoint.aclose()


def test_sidecar_configuration_rejects_shared_ports_and_invalid_refresh_window() -> None:
    with pytest.raises(ValidationError, match="SERVING_PORT and INTERNAL_PORT must differ"):
        configuration(SERVING_PORT=8001)
    with pytest.raises(ValidationError, match="must be less than"):
        configuration(COMPANION_CACHE_REFRESH_AHEAD_SECONDS=1)


def test_serving_image_installs_both_extras_and_runs_as_non_root() -> None:
    dockerfile = (Path(__file__).parents[1] / "Dockerfile.serving").read_text()

    assert "FROM python:3.14-" in dockerfile
    assert "--extra serving --extra monitoring" in dockerfile
    assert "USER 10001:0" in dockerfile
    assert 'CMD ["luml-satellite-sidecar"]' in dockerfile
