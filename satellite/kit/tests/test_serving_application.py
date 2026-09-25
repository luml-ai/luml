import gzip
import json
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import cast

import httpx
import pytest
from fastapi import FastAPI

from luml_satellite import AuthorizationVerdict
from luml_satellite.monitoring import InferenceInstrumentation
from luml_satellite.monitoring.ingest.testing import FakeTelemetry
from luml_satellite.serving import (
    PassThroughTransform,
    SecretUnavailable,
    StartingGate,
    create_artifact_router,
    create_serving_application,
)
from luml_satellite.wire import ArtifactDownload
from luml_satellite.workload import (
    ArtifactResolver,
    DeploymentMetadata,
    InferenceOutcome,
    LocalDeployment,
    NoOpRecorder,
    RecordingPolicy,
    RecordingSession,
)

DEPLOYMENT_ID = "10000000-0000-0000-0000-000000000001"
OTHER_DEPLOYMENT_ID = "10000000-0000-0000-0000-000000000002"
AUTHORIZATION = {"Authorization": "Bearer good"}


class FakeAuthorizer:
    def __init__(self, verdicts: Mapping[str, AuthorizationVerdict] | None = None) -> None:
        self.verdicts = dict(verdicts or {"good": AuthorizationVerdict.ALLOWED})
        self.calls: list[str] = []

    async def authorize(self, api_key: str) -> AuthorizationVerdict:
        self.calls.append(api_key)
        return self.verdicts.get(api_key, AuthorizationVerdict.DENIED)


class FakeSecretSource:
    def __init__(self, values: Mapping[str, str] | None = None) -> None:
        self.values = dict(values or {})
        self.calls: list[tuple[str, dict[str, str]]] = []
        self.unavailable: str | None = None

    async def resolve(
        self,
        deployment_id: str,
        secrets: Mapping[str, str],
    ) -> Mapping[str, str]:
        self.calls.append((deployment_id, dict(secrets)))
        if self.unavailable is not None:
            raise SecretUnavailable(self.unavailable)
        return {name: self.values[name] for name in secrets}


@dataclass
class CapturedSession:
    event_id: str | None
    headers: dict[str, str] = field(default_factory=dict)
    outcomes: list[InferenceOutcome] = field(default_factory=list)

    @property
    def upstream_headers(self) -> Mapping[str, str]:
        return self.headers

    async def complete(self, outcome: InferenceOutcome) -> None:
        self.outcomes.append(outcome)


class CapturingRecorder:
    def __init__(self, *, event_ids: bool = True, headers: Mapping[str, str] | None = None) -> None:
        self.event_ids = event_ids
        self.headers = dict(headers or {})
        self.inputs: list[object | None] = []
        self.policies: list[RecordingPolicy] = []
        self.sessions: list[CapturedSession] = []

    async def start(
        self,
        deployment_id: str,
        inputs: object | None,
        policy: RecordingPolicy,
    ) -> RecordingSession:
        self.inputs.append(inputs)
        self.policies.append(policy)
        event_id = f"event-{len(self.sessions) + 1}" if self.event_ids else None
        session = CapturedSession(event_id, self.headers.copy())
        self.sessions.append(session)
        return session


class Registry:
    def __init__(self, *deployments: LocalDeployment) -> None:
        self.deployments = {deployment.deployment_id: deployment for deployment in deployments}

    def get_deployment(self, deployment_id: str) -> LocalDeployment | None:
        return self.deployments.get(deployment_id)

    def list_deployments(self) -> tuple[LocalDeployment, ...]:
        return tuple(self.deployments.values())


def local_deployment(
    deployment_id: str = DEPLOYMENT_ID,
    *,
    monitoring: bool = True,
    secrets: Mapping[str, str] | None = None,
    policy: RecordingPolicy | None = None,
) -> LocalDeployment:
    return LocalDeployment(
        deployment_id=deployment_id,
        dynamic_attributes_secrets=dict(secrets or {}),
        openapi_schema={"openapi": "3.1.0", "paths": {"/compute": {}}},
        monitoring_enabled=monitoring,
        metadata=DeploymentMetadata(name=f"deployment-{deployment_id[-1]}", status="active"),
        upstream_url=f"http://model-{deployment_id}",
        recording_policy=policy or RecordingPolicy(),
    )


async def app_client(application: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application),
        base_url="http://satellite",
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_routes_authorization_unknown_route_and_openapi_contract() -> None:
    async def upstream(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"prediction": 42})

    gate = StartingGate()
    gate.mark_ready()
    authorizer = FakeAuthorizer(
        {
            "good": AuthorizationVerdict.ALLOWED,
            "target": AuthorizationVerdict.ALLOWED,
            "denied": AuthorizationVerdict.DENIED,
            "unavailable": AuthorizationVerdict.UNAVAILABLE,
        }
    )
    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    application = create_serving_application(
        Registry(local_deployment()),
        authorizer,
        FakeSecretSource(),
        upstream_client=upstream_client,
        starting_gate=gate,
    )
    try:
        async for client in app_client(application):
            missing = await client.post(
                "/satellites/deployments/inference-access",
                json={"api_key": "target"},
            )
            allowed = await client.post(
                "/satellites/deployments/inference-access",
                headers=AUTHORIZATION,
                json={"api_key": "target"},
            )
            denied = await client.post(
                "/satellites/deployments/inference-access",
                headers=AUTHORIZATION,
                json={"api_key": "denied"},
            )
            unavailable = await client.post(
                "/satellites/deployments/inference-access",
                headers=AUTHORIZATION,
                json={"api_key": "unavailable"},
            )
            unknown = await client.get("/does-not-exist")
            monitoring_unknown = await client.get("/monitoring/does-not-exist")
            live = await client.get("/livez")
            schema_response = await client.get(
                f"/deployments/{DEPLOYMENT_ID}/openapi.json",
                headers=AUTHORIZATION,
            )
            document = application.openapi()
    finally:
        await upstream_client.aclose()

    assert missing.status_code == 403
    assert allowed.json() == {"authorized": True}
    assert denied.json() == {"authorized": False}
    assert unavailable.status_code == 502
    assert unavailable.json() == {"detail": "Authorization failed"}
    assert unknown.json() == {"detail": "Not Found", "code": "unknown_route"}
    assert monitoring_unknown.json() == {"detail": "Not Found"}
    assert live.status_code == 200
    assert schema_response.json() == {"openapi": "3.1.0", "paths": {"/compute": {}}}
    assert "/livez" not in document["paths"]
    inference_access = document["paths"]["/satellites/deployments/inference-access"]["post"]
    assert inference_access["security"] == [{"HTTPBearer": []}]
    expected_operations = {
        ("post", "/satellites/deployments/inference-access"): "satellite",
        ("get", "/healthz"): "satellite",
        ("get", "/deployments"): "deployment",
        ("post", "/deployments/{deployment_id}/compute"): "deployment",
        ("get", "/deployments/{deployment_id}/openapi.json"): "deployment",
    }
    for (method, path), facet in expected_operations.items():
        operation = document["paths"][path][method]
        assert operation["tags"] == [facet]
        assert operation["security"] == [{"HTTPBearer": []}]
        assert operation["summary"]
        assert operation["description"]
    compute = document["paths"]["/deployments/{deployment_id}/compute"]["post"]
    assert compute["requestBody"]["content"]["application/json"]["schema"] == {
        "additionalProperties": True,
        "title": "Body",
        "type": "object",
    }
    assert compute["responses"]["200"]["content"]["application/json"]["schema"]["type"] == "object"
    assert "/deployments/{deployment_id}/openapi.json" in document["paths"]


@pytest.mark.asyncio
async def test_starting_gate_only_blocks_deployment_routes() -> None:
    async def upstream(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"prediction": 42})

    gate = StartingGate()
    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    application = create_serving_application(
        Registry(local_deployment()),
        FakeAuthorizer(),
        FakeSecretSource(),
        upstream_client=upstream_client,
        starting_gate=gate,
    )

    class StaticArtifactResolver:
        async def resolve_download(
            self,
            deployment_id: str,
            token: str | None,
        ) -> ArtifactDownload:
            return ArtifactDownload(url="https://store/artifact", artifact_id="artifact")

    application.include_router(
        create_artifact_router(cast(ArtifactResolver, StaticArtifactResolver()))
    )

    @application.get("/monitoring/test")
    async def monitoring_route() -> dict[str, bool]:
        return {"available": True}

    try:
        async for client in app_client(application):
            before = [
                await client.get("/deployments", headers=AUTHORIZATION),
                await client.post(
                    f"/deployments/{DEPLOYMENT_ID}/compute",
                    headers=AUTHORIZATION,
                    json={"inputs": {"x": 1}},
                ),
                await client.get(
                    f"/deployments/{DEPLOYMENT_ID}/openapi.json",
                    headers=AUTHORIZATION,
                ),
            ]
            inference_access = await client.post(
                "/satellites/deployments/inference-access",
                headers=AUTHORIZATION,
                json={"api_key": "good"},
            )
            live = await client.get("/livez")
            artifact = await client.get(
                f"/satellites/deployments/{DEPLOYMENT_ID}/artifact",
                headers={"X-Artifact-Token": "token"},
            )
            monitoring = await client.get("/monitoring/test")
            compute_without_bearer = await client.post(
                f"/deployments/{DEPLOYMENT_ID}/compute",
                json={"inputs": {"x": 1}},
            )
            gate.mark_ready()
            after = [
                await client.get("/deployments", headers=AUTHORIZATION),
                await client.post(
                    f"/deployments/{DEPLOYMENT_ID}/compute",
                    headers=AUTHORIZATION,
                    json={"inputs": {"x": 1}},
                ),
                await client.get(
                    f"/deployments/{DEPLOYMENT_ID}/openapi.json",
                    headers=AUTHORIZATION,
                ),
            ]
    finally:
        await upstream_client.aclose()

    assert [(response.status_code, response.json()) for response in before] == [
        (503, {"detail": "Satellite starting"}),
        (503, {"detail": "Satellite starting"}),
        (503, {"detail": "Satellite starting"}),
    ]
    assert inference_access.status_code == 200
    assert live.status_code == 200
    assert artifact.status_code == 200
    assert monitoring.status_code == 200
    assert compute_without_bearer.status_code == 403
    assert [response.status_code for response in after] == [200, 200, 200]


@pytest.mark.asyncio
async def test_single_deployment_and_not_hosted_modes() -> None:
    async def upstream(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"prediction": 42})

    gate = StartingGate(starting=False)
    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    registry = Registry(local_deployment(), local_deployment(OTHER_DEPLOYMENT_ID))
    single = create_serving_application(
        registry,
        FakeAuthorizer(),
        FakeSecretSource(),
        upstream_client=upstream_client,
        starting_gate=gate,
        single_deployment_id=DEPLOYMENT_ID,
    )
    not_hosted = create_serving_application(
        registry,
        FakeAuthorizer(),
        FakeSecretSource(),
        upstream_client=upstream_client,
        starting_gate=StartingGate(starting=False),
        not_hosted=True,
    )
    try:
        async for client in app_client(single):
            listing = await client.get("/deployments", headers=AUTHORIZATION)
            other = await client.post(
                f"/deployments/{OTHER_DEPLOYMENT_ID}/compute",
                headers=AUTHORIZATION,
                json={},
            )
        async for client in app_client(not_hosted):
            disabled = await client.post(
                f"/deployments/{DEPLOYMENT_ID}/compute",
                headers=AUTHORIZATION,
                json={},
            )
            schema = await client.get(
                f"/deployments/{DEPLOYMENT_ID}/openapi.json",
                headers=AUTHORIZATION,
            )
    finally:
        await upstream_client.aclose()

    assert [item["deployment_id"] for item in listing.json()] == [DEPLOYMENT_ID]
    assert other.json()["code"] == "deployment_not_hosted"
    assert disabled.json()["code"] == "deployment_not_hosted"
    assert schema.status_code == 200


@pytest.mark.asyncio
async def test_secret_injection_sampling_and_trace_context(
    fake_telemetry: FakeTelemetry,
) -> None:
    random_values = iter([0.75, 0.25])
    recorder = InferenceInstrumentation(
        fake_telemetry.setup,
        random_source=lambda: next(random_values),
    )
    upstream_bodies: list[dict[str, object]] = []
    upstream_trace_headers: list[str | None] = []

    async def upstream(request: httpx.Request) -> httpx.Response:
        upstream_bodies.append(json.loads(await request.aread()))
        upstream_trace_headers.append(request.headers.get("traceparent"))
        return httpx.Response(200, json={"prediction": 42})

    deployment = local_deployment(
        secrets={"api_key": "secret-id"},
        policy=RecordingPolicy(sample_rate=0.5, body_max_bytes=1024),
    )
    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    application = create_serving_application(
        Registry(deployment),
        FakeAuthorizer(),
        FakeSecretSource({"api_key": "super-secret"}),
        recorder=recorder,
        upstream_client=upstream_client,
        starting_gate=StartingGate(starting=False),
    )
    try:
        async for client in app_client(application):
            responses = [
                await client.post(
                    f"/deployments/{DEPLOYMENT_ID}/compute",
                    headers=AUTHORIZATION,
                    json={"inputs": {"x": 1}, "dynamic_attributes": {"feature": index}},
                )
                for index in range(2)
            ]
    finally:
        await upstream_client.aclose()

    for body in upstream_bodies:
        dynamic_attributes = body["dynamic_attributes"]
        assert isinstance(dynamic_attributes, dict)
        assert dynamic_attributes["api_key"] == "super-secret"
    assert all(header is not None and header.startswith("00-") for header in upstream_trace_headers)
    assert all(response.headers.get("x-event-id") for response in responses)
    assert len(fake_telemetry.events) == 2
    assert fake_telemetry.events[0].bodies_sampled is False
    assert fake_telemetry.events[0].inputs is None
    assert fake_telemetry.events[0].output is None
    assert fake_telemetry.events[1].bodies_sampled is True
    assert fake_telemetry.events[1].inputs == {
        "inputs": {"x": 1},
        "dynamic_attributes": {"feature": 1},
    }
    recorded_inputs = fake_telemetry.events[1].inputs
    assert isinstance(recorded_inputs, dict)
    dynamic_attributes = recorded_inputs["dynamic_attributes"]
    assert isinstance(dynamic_attributes, dict)
    assert "api_key" not in dynamic_attributes
    assert fake_telemetry.events[1].output == {"prediction": 42}
    assert all(
        event.status_code == 200 and event.latency_ms >= 0 for event in fake_telemetry.events
    )


@pytest.mark.asyncio
async def test_monitoring_off_and_noop_recorder_emit_no_event_header() -> None:
    async def upstream(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"prediction": 42},
            headers={"X-Event-Id": "upstream-event"},
        )

    capturing = CapturingRecorder()
    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    off_application = create_serving_application(
        Registry(local_deployment(monitoring=False)),
        FakeAuthorizer(),
        FakeSecretSource(),
        recorder=capturing,
        upstream_client=upstream_client,
        starting_gate=StartingGate(starting=False),
    )
    noop_application = create_serving_application(
        Registry(local_deployment()),
        FakeAuthorizer(),
        FakeSecretSource(),
        recorder=NoOpRecorder(),
        upstream_client=upstream_client,
        starting_gate=StartingGate(starting=False),
    )
    try:
        async for client in app_client(off_application):
            off = await client.post(
                f"/deployments/{DEPLOYMENT_ID}/compute",
                headers=AUTHORIZATION,
                json={"inputs": {"x": 1}},
            )
        async for client in app_client(noop_application):
            noop = await client.post(
                f"/deployments/{DEPLOYMENT_ID}/compute",
                headers=AUTHORIZATION,
                json={"inputs": {"x": 1}},
            )
    finally:
        await upstream_client.aclose()

    assert off.json() == noop.json() == {"prediction": 42}
    assert "x-event-id" not in off.headers
    assert "x-event-id" not in noop.headers
    assert capturing.sessions == []


@pytest.mark.asyncio
async def test_caller_supplied_secret_attribute_is_not_replaced_or_recorded() -> None:
    upstream_body: dict[str, object] = {}

    async def upstream(request: httpx.Request) -> httpx.Response:
        upstream_body.update(json.loads(await request.aread()))
        return httpx.Response(200, json={"prediction": 42})

    secrets = FakeSecretSource({"api_key": "stored-secret"})
    recorder = CapturingRecorder()
    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    application = create_serving_application(
        Registry(local_deployment(secrets={"api_key": "secret-id"})),
        FakeAuthorizer(),
        secrets,
        recorder=recorder,
        upstream_client=upstream_client,
        starting_gate=StartingGate(starting=False),
    )
    try:
        async for client in app_client(application):
            response = await client.post(
                f"/deployments/{DEPLOYMENT_ID}/compute",
                headers=AUTHORIZATION,
                json={"dynamic_attributes": {"api_key": "caller-value", "feature": 1}},
            )
    finally:
        await upstream_client.aclose()

    assert response.status_code == 200
    assert upstream_body["dynamic_attributes"] == {
        "api_key": "caller-value",
        "feature": 1,
    }
    assert secrets.calls == []
    assert recorder.inputs == [{"dynamic_attributes": {"feature": 1}}]


@pytest.mark.asyncio
async def test_transformed_request_is_declared_as_json_without_a_caller_content_type() -> None:
    upstream_content_type: str | None = None

    async def upstream(request: httpx.Request) -> httpx.Response:
        nonlocal upstream_content_type
        upstream_content_type = request.headers.get("content-type")
        assert json.loads(await request.aread())["dynamic_attributes"] == {
            "api_key": "stored-secret"
        }
        return httpx.Response(200, json={"prediction": 42})

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    application = create_serving_application(
        Registry(local_deployment(secrets={"api_key": "secret-id"})),
        FakeAuthorizer(),
        FakeSecretSource({"api_key": "stored-secret"}),
        upstream_client=upstream_client,
        starting_gate=StartingGate(starting=False),
    )
    try:
        async for client in app_client(application):
            response = await client.post(
                f"/deployments/{DEPLOYMENT_ID}/compute",
                headers=AUTHORIZATION,
                content=b"{}",
            )
    finally:
        await upstream_client.aclose()

    assert response.status_code == 200
    assert upstream_content_type == "application/json"


@pytest.mark.asyncio
async def test_recording_and_injection_caps_apply_independently(
    fake_telemetry: FakeTelemetry,
) -> None:
    recorder = InferenceInstrumentation(fake_telemetry.setup, random_source=lambda: 0.0)
    upstream_bodies: list[dict[str, object]] = []

    async def upstream(request: httpx.Request) -> httpx.Response:
        upstream_bodies.append(json.loads(await request.aread()))
        return httpx.Response(200, json={"prediction": 42})

    deployment = local_deployment(
        secrets={"api_key": "secret-id"},
        policy=RecordingPolicy(body_max_bytes=1024),
    )
    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    application = create_serving_application(
        Registry(deployment),
        FakeAuthorizer(),
        FakeSecretSource({"api_key": "secret"}),
        recorder=recorder,
        upstream_client=upstream_client,
        starting_gate=StartingGate(starting=False),
        injection_body_max_bytes=2048,
    )
    try:
        async for client in app_client(application):
            forwarded = await client.post(
                f"/deployments/{DEPLOYMENT_ID}/compute",
                headers=AUTHORIZATION,
                json={"inputs": {"payload": "x" * 1400}},
            )
            rejected = await client.post(
                f"/deployments/{DEPLOYMENT_ID}/compute",
                headers=AUTHORIZATION,
                json={"inputs": {"payload": "x" * 3000}},
            )
    finally:
        await upstream_client.aclose()

    assert forwarded.status_code == 200
    assert upstream_bodies[0]["dynamic_attributes"] == {"api_key": "secret"}
    assert fake_telemetry.events[0].bodies_sampled is False
    assert fake_telemetry.events[0].inputs is None
    assert fake_telemetry.events[0].output is None
    assert rejected.status_code == 413
    assert len(upstream_bodies) == 1
    assert [event.status_code for event in fake_telemetry.events] == [200, 413]
    assert rejected.headers.get("x-event-id") == fake_telemetry.events[1].event_id


@pytest.mark.asyncio
async def test_invalid_json_is_local_only_when_the_transform_needs_to_parse_it() -> None:
    upstream_bodies: list[bytes] = []

    async def upstream(request: httpx.Request) -> httpx.Response:
        upstream_bodies.append(await request.aread())
        return httpx.Response(422, json={"error": "upstream rejected body"})

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    monitored = create_serving_application(
        Registry(local_deployment()),
        FakeAuthorizer(),
        FakeSecretSource(),
        recorder=CapturingRecorder(),
        upstream_client=upstream_client,
        starting_gate=StartingGate(starting=False),
    )
    unmonitored = create_serving_application(
        Registry(local_deployment(monitoring=False)),
        FakeAuthorizer(),
        FakeSecretSource(),
        upstream_client=upstream_client,
        starting_gate=StartingGate(starting=False),
    )
    try:
        async for client in app_client(monitored):
            parsed = await client.post(
                f"/deployments/{DEPLOYMENT_ID}/compute",
                headers={**AUTHORIZATION, "Content-Type": "application/json"},
                content=b"not-json",
            )
        async for client in app_client(unmonitored):
            forwarded = await client.post(
                f"/deployments/{DEPLOYMENT_ID}/compute",
                headers={**AUTHORIZATION, "Content-Type": "application/json"},
                content=b"not-json",
            )
    finally:
        await upstream_client.aclose()

    assert parsed.status_code == 422
    assert forwarded.status_code == 422
    assert forwarded.json() == {"detail": "upstream rejected body"}
    assert upstream_bodies == [b"not-json"]


@pytest.mark.asyncio
async def test_upstream_error_keeps_its_status_and_envelope_and_is_recorded(
    fake_telemetry: FakeTelemetry,
) -> None:
    async def upstream(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"error": "bad input"})

    recorder = InferenceInstrumentation(fake_telemetry.setup, random_source=lambda: 0.0)
    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    application = create_serving_application(
        Registry(local_deployment()),
        FakeAuthorizer(),
        FakeSecretSource(),
        recorder=recorder,
        upstream_client=upstream_client,
        starting_gate=StartingGate(starting=False),
    )
    try:
        async for client in app_client(application):
            response = await client.post(
                f"/deployments/{DEPLOYMENT_ID}/compute",
                headers=AUTHORIZATION,
                json={"inputs": {"x": 1}},
            )
    finally:
        await upstream_client.aclose()

    assert response.status_code == 422
    assert response.json() == {"detail": "bad input"}
    assert response.headers["x-event-id"] == fake_telemetry.events[0].event_id
    assert fake_telemetry.events[0].status == "error"
    assert fake_telemetry.events[0].status_code == 422
    assert fake_telemetry.events[0].error == "bad input"


@pytest.mark.asyncio
async def test_buffered_response_drops_consumed_content_encoding() -> None:
    async def upstream(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=gzip.compress(b'{"prediction":42}'),
            headers={
                "Content-Encoding": "gzip",
                "Content-Type": "application/json",
            },
        )

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    application = create_serving_application(
        Registry(local_deployment(monitoring=False)),
        FakeAuthorizer(),
        FakeSecretSource(),
        upstream_client=upstream_client,
        starting_gate=StartingGate(starting=False),
    )
    try:
        async for client in app_client(application):
            response = await client.post(
                f"/deployments/{DEPLOYMENT_ID}/compute",
                headers=AUTHORIZATION,
                json={"inputs": {"x": 1}},
            )
    finally:
        await upstream_client.aclose()

    assert response.json() == {"prediction": 42}
    assert "content-encoding" not in response.headers


@pytest.mark.asyncio
async def test_pass_through_drops_encoding_from_an_already_consumed_response() -> None:
    async def upstream(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=gzip.compress(b'{"prediction":42}'),
            headers={
                "Content-Encoding": "gzip",
                "Content-Type": "application/json",
            },
        )

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    application = create_serving_application(
        Registry(local_deployment(monitoring=False)),
        FakeAuthorizer(),
        FakeSecretSource(),
        transform=PassThroughTransform(),
        upstream_client=upstream_client,
        starting_gate=StartingGate(starting=False),
    )
    try:
        async for client in app_client(application):
            response = await client.post(
                f"/deployments/{DEPLOYMENT_ID}/compute",
                headers=AUTHORIZATION,
                content=b"binary request",
            )
    finally:
        await upstream_client.aclose()

    assert response.json() == {"prediction": 42}
    assert "content-encoding" not in response.headers


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "expected_status", "expected_type"),
    [
        (httpx.ReadTimeout("slow model"), 504, "ReadTimeout"),
        (httpx.ConnectError("connection refused"), 502, "ConnectError"),
    ],
)
async def test_upstream_transport_failures_are_named(
    failure: httpx.RequestError,
    expected_status: int,
    expected_type: str,
) -> None:
    async def upstream(request: httpx.Request) -> httpx.Response:
        raise failure

    recorder = CapturingRecorder()
    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    application = create_serving_application(
        Registry(local_deployment()),
        FakeAuthorizer(),
        FakeSecretSource(),
        recorder=recorder,
        upstream_client=upstream_client,
        starting_gate=StartingGate(starting=False),
    )
    try:
        async for client in app_client(application):
            response = await client.post(
                f"/deployments/{DEPLOYMENT_ID}/compute",
                headers=AUTHORIZATION,
                json={"inputs": {"x": 1}},
            )
    finally:
        await upstream_client.aclose()

    assert response.status_code == expected_status
    assert expected_type in response.json()["detail"]
    assert recorder.sessions[0].outcomes[0].status_code == expected_status


@pytest.mark.asyncio
async def test_unavailable_secret_is_named_and_never_forwarded() -> None:
    calls = 0

    async def upstream(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={})

    secrets = FakeSecretSource()
    secrets.unavailable = "api_key"
    recorder = CapturingRecorder()
    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    application = create_serving_application(
        Registry(local_deployment(secrets={"api_key": "secret-id"})),
        FakeAuthorizer(),
        secrets,
        recorder=recorder,
        upstream_client=upstream_client,
        starting_gate=StartingGate(starting=False),
    )
    try:
        async for client in app_client(application):
            response = await client.post(
                f"/deployments/{DEPLOYMENT_ID}/compute",
                headers=AUTHORIZATION,
                json={"inputs": {"x": 1}},
            )
    finally:
        await upstream_client.aclose()

    assert response.status_code == 424
    assert "api_key" in response.json()["detail"]
    assert calls == 0
    assert recorder.sessions[0].outcomes[0].status_code == 424


@pytest.mark.asyncio
async def test_pass_through_streams_a_large_body_without_recording_it() -> None:
    total_received = 0
    largest_chunk = 0
    traceparent: str | None = None

    class ResponseStream(httpx.AsyncByteStream):
        def __init__(self, content: bytes) -> None:
            self.content = content

        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield self.content

    class StreamingTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            nonlocal total_received, largest_chunk, traceparent
            traceparent = request.headers.get("traceparent")
            stream = request.stream
            assert isinstance(stream, httpx.AsyncByteStream)
            async for chunk in stream:
                total_received += len(chunk)
                largest_chunk = max(largest_chunk, len(chunk))
            payload = json.dumps({"received": total_received}).encode()
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                stream=ResponseStream(payload),
            )

    async def body() -> AsyncIterator[bytes]:
        chunk = b"x" * (1024 * 1024)
        for _ in range(50):
            yield chunk

    recorder = CapturingRecorder(headers={"traceparent": "00-trace-span-01"})
    upstream_client = httpx.AsyncClient(transport=StreamingTransport())
    application = create_serving_application(
        Registry(local_deployment(policy=RecordingPolicy(body_max_bytes=4096))),
        FakeAuthorizer(),
        FakeSecretSource(),
        recorder=recorder,
        transform=PassThroughTransform(),
        upstream_client=upstream_client,
        starting_gate=StartingGate(starting=False),
    )
    try:
        async for client in app_client(application):
            response = await client.post(
                f"/deployments/{DEPLOYMENT_ID}/compute",
                headers={**AUTHORIZATION, "Content-Type": "application/octet-stream"},
                content=body(),
            )
    finally:
        await upstream_client.aclose()

    assert response.json() == {"received": 50 * 1024 * 1024}
    assert total_received == 50 * 1024 * 1024
    assert largest_chunk <= 1024 * 1024
    assert recorder.inputs == [None]
    outcome = recorder.sessions[0].outcomes[0]
    assert outcome.status_code == 200
    assert outcome.latency_ms >= 0
    assert outcome.output is None
    assert traceparent == "00-trace-span-01"
    assert response.headers["x-event-id"] == "event-1"
