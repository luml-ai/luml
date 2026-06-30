---
sidebar_label: Satellite Instrumentation Spec
title: Satellite Inference Instrumentation & Collection Spec
---

# Proposals

## Problem

The Satellite serves model inference but records nothing about it. When a deployed
model is queried through the Satellite Agent there is no request-level history:
no inputs, no outputs, no latency, no error record, no trace. Without this raw
collection layer none of the downstream live-monitoring features (runtime health,
data quality, drift, alerts, the dashboard) can ever be built, because they all
read from data that does not exist yet.

This spec is the **first slice** of the larger Live Monitoring architecture. It is
deliberately scoped to one thing: **make inference instrumentation and local
collection work on the Satellite.** Everything that consumes the collected data
(dashboard, Monitoring API, query layer, worker, drift/quality calculations,
Platform iframe launch, target submission) is explicitly out of scope here and
will be specified separately.

## Solution at a glance

Add an instrumentation point in the Satellite Agent around the single call that
forwards an inference request to the model-server container. In `full` monitoring
mode this wrapper:

- assigns a local `event_id` (UUIDv7) and preserves or generates a client
  `request_id`,
- times the forwarded call,
- captures the model input payload (secret-safe), the output or error, status,
  and latency,
- emits a span, runtime metrics, and a structured inference-event log record over
  OpenTelemetry,
- does all of this **best-effort** so monitoring never blocks or alters inference.

Telemetry is exported over OTLP to a co-located **OpenTelemetry Collector**, which
writes into a co-located **GreptimeDB** instance. Both are shipped as part of the
Satellite `docker-compose` stack and left idle until a `full` deployment exists.

Monitoring is per-deployment. The mode (`off` / `full`) is read from the existing
`satellite_parameters` dictionary on the deployment, so no Platform schema change
is required for this slice.

## Why this approach

- **Agent-level instrumentation** keeps monitoring independent of model code and
  preserves the current serving contract. Model runtimes do not need to change.
- **OpenTelemetry + Collector + GreptimeDB** matches the target architecture of the
  full monitoring spec, so this slice is a real foundation and not throwaway work.
- **`satellite_parameters` for mode** avoids a cross-team Platform contract change
  while still supporting mixed `off`/`full` deployments on one Satellite.
- **Best-effort, non-blocking** honors the non-negotiable rule that inference
  availability outranks monitoring availability.

# Design

## Scope boundary

In scope (this spec):

- per-deployment `off` / `full` monitoring mode, read from `satellite_parameters`
- local event identity: `event_id` (UUIDv7) and `request_id` (preserved or generated)
- inference instrumentation wrapper in the Agent serving path
- structured inference events, runtime metrics, and trace spans
- OpenTelemetry SDK export to a co-located Collector → GreptimeDB
- `docker-compose` services for the Collector and GreptimeDB
- pytest test infrastructure for the Satellite Agent (does not exist today)

Out of scope (later specs): Monitoring API, dashboard UI, Platform iframe / launch
token, query layer, Monitoring Worker, drift / data-quality / performance
calculations, reference profiles, alerts, target submission, container lifecycle
management of the monitoring services.

## Current inference path (grounding)

The single capture point is the forward call to the model server:

```text
client
  -> agent_api.py  POST /deployments/{deployment_id}/compute   (verify_token)
  -> ModelServerHandler.model_compute(deployment_id, body)     (agent/handlers/model_server_handler.py)
  -> ModelServerClient.compute(deployment_id, body)            (agent/clients/model_server_client.py)
  -> http://sat-{deployment_id}:{MODEL_SERVER_PORT}/compute
```

Relevant existing files:

- `satellite/agent/agent_api.py` — FastAPI app; `compute` endpoint.
- `satellite/agent/handlers/model_server_handler.py` — `ModelServerHandler`;
  `model_compute`, `add_deployment`, `add_single_deployment`, `sync_deployments`.
- `satellite/agent/clients/model_server_client.py` — `ModelServerClient.compute`,
  raises `ModelServerError(status_code, detail)` on model failure.
- `satellite/agent/schemas/deployments.py` — `Deployment` (has
  `satellite_parameters: dict[str, int | str] | None`), `LocalDeployment`.
- `satellite/agent/settings.py` — `Settings` (pydantic-settings, env-driven).
- `satellite/docker-compose.yml` — `agent` + `model-image` services.
- `satellite/pyproject.toml` — deps: httpx, aiodocker, pydantic, pydantic-settings,
  fastapi, uvicorn, cashews; Python `>=3.14`; ruff configured, **no pytest, no tests/**.

## Monitoring mode

Add an enum and plumb the mode into the in-memory deployment record.

```python
# agent/schemas/deployments.py
class MonitoringMode(StrEnum):
    OFF = "off"
    FULL = "full"
```

- `LocalDeployment` gains `monitoring_mode: MonitoringMode = MonitoringMode.OFF`.
- A helper parses the mode from a deployment's `satellite_parameters`:

```python
def parse_monitoring_mode(satellite_parameters: dict | None) -> MonitoringMode:
    raw = (satellite_parameters or {}).get("monitoring_mode")
    try:
        return MonitoringMode(str(raw))
    except ValueError:
        return MonitoringMode.OFF   # missing or invalid -> off (safe default)
```

- `ModelServerHandler.add_single_deployment` gains a `monitoring_mode` parameter
  and stores it on the `LocalDeployment`.
- `add_deployment(deployment: Deployment)` derives the mode from
  `deployment.satellite_parameters` and passes it down.
- `sync_deployments` derives the mode from each `dep.get("satellite_parameters")`
  dict and passes it down.

Default is `off`: any deployment whose `satellite_parameters` does not set
`monitoring_mode` records no IO.

## Event identity

- `event_id` — generated by the Satellite per inference, `uuid.uuid7()` (Python
  3.14 stdlib; time-sortable). Local to monitoring storage; never returned to the
  client.
- `request_id` — read from the `X-Request-Id` request header if present and
  non-empty; otherwise generated with `uuid.uuid7()`. Always echoed back to the
  client in the `X-Request-Id` response header so delayed targets and support
  workflows can refer to the same inference.
- The `compute` endpoint signature in `agent_api.py` is extended to accept the
  `X-Request-Id` header and a `Response` so it can set the response header, and to
  pass `request_id` into `model_compute`.

`request_id` is not treated as globally unique; correlation is always scoped by
`deployment_id`.

## Monitoring module

New package `satellite/agent/monitoring/`:

| File | Responsibility |
| --- | --- |
| `__init__.py` | exports `instrument_inference`, `get_telemetry`, models |
| `otel.py` | one-time OpenTelemetry SDK setup: TracerProvider, MeterProvider, LoggerProvider, OTLP exporters, resource attributes; reads config from settings; returns a `Telemetry` holder; no-ops cleanly when monitoring is disabled or the endpoint is unset |
| `events.py` | pydantic models `InferenceEvent` and the metric/attribute key constants |
| `instrumentation.py` | `instrument_inference(...)` async context manager that times the forward call, captures input/output/status/latency, and emits span + metrics + structured log event, all best-effort |

### `InferenceEvent` model (`events.py`)

```python
class InferenceEvent(BaseModel):
    event_id: str            # UUIDv7
    request_id: str          # UUIDv7 (preserved or generated)
    deployment_id: str
    status: str              # "success" | "error"
    status_code: int | None  # model server HTTP status on error
    latency_ms: float
    inputs: dict | None      # model feature payload, secret-stripped
    output: dict | None      # model output payload (success only)
    error: str | None        # error detail (error only)
    trace_id: str | None
    span_id: str | None
    timestamp: str           # ISO-8601 UTC
```

### Runtime metrics (OTel instruments, created once in `otel.py`)

| Instrument | Type | Attributes |
| --- | --- | --- |
| `inference.requests` | counter | `deployment_id`, `status` |
| `inference.errors` | counter | `deployment_id`, `status_code` |
| `inference.latency_ms` | histogram | `deployment_id`, `status` |

### OTel export

- Single export path: Agent OTel SDK → OTLP/HTTP → OpenTelemetry Collector →
  GreptimeDB.
- Inference events are emitted as **OTel log records** whose attributes carry the
  `InferenceEvent` fields and whose body is the JSON event. Runtime metrics use the
  instruments above. The forward call is wrapped in a span.
- Exporters are batched (Batch processors) so emission does not add request
  latency; the network export happens on the SDK's background machinery.
- Config (added to `settings.py`):
  - `MONITORING_ENABLED: bool = True` — global kill switch.
  - `OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None` — Collector OTLP endpoint;
    if unset, telemetry providers are no-op even in `full` mode.
  - `OTEL_SERVICE_NAME: str = "satellite-agent"`.

New dependencies (`pyproject.toml`):

- `opentelemetry-sdk`
- `opentelemetry-exporter-otlp-proto-http`

(`opentelemetry-api` comes transitively; no GreptimeDB client is needed in the
Agent — the Collector owns the GreptimeDB write.)

## Instrumentation wrapper

`instrument_inference` is an async context manager used inside
`ModelServerHandler.model_compute`.


Best-effort guarantees implemented inside `instrument_inference` /
`otel.py`:

- All telemetry calls (span start/end, metric record, log emit) are individually
  wrapped so an exporter or SDK failure is swallowed and logged at WARNING, never
  raised.
- A monitoring failure never blocks authorization, never blocks forwarding, and
  never changes the model response body or status.
- On model failure a failed inference event + error metric are still emitted, then
  the original `ModelServerError` is re-raised unchanged so the endpoint returns
  the same status/detail as today.

### Secret safety

`get_compute_missing_secrets` injects orbit secret values into
`body["dynamic_attributes"]`. The captured `inputs` for the inference event must be
taken **before** secret injection and must exclude any dynamic attribute that is
secret-backed (`deployment.dynamic_attributes_secrets`). Secret values must never
appear in a recorded inference event, span attribute, or log record.

## Service reconciliation (MVP)

For this slice, GreptimeDB and the OTel Collector are shipped in
`docker-compose.yml` and run idle regardless of mode (the full spec's accepted MVP
posture). The Agent does **not** start/stop these containers. Per-deployment mode
gating in `model_compute` is the only thing that decides whether IO is recorded:
`off` deployments must never write raw inference IO even while the shared services
are running.

## docker-compose additions

Add two services on the existing `satellite-network`:

- `otel-collector` (`otel/opentelemetry-collector-contrib`): OTLP receiver on
  `4318` (HTTP); pipeline exports traces, metrics, and logs to GreptimeDB; config
  mounted from `satellite/otel/collector-config.yaml`.
- `greptimedb` (`greptime/greptimedb`): exposes its OTLP ingest and query ports;
  named volume for local persistence.
- `agent` env gains `MONITORING_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT`
  (defaulting to `http://otel-collector:4318`), and `OTEL_SERVICE_NAME`.

A `collector-config.yaml` defines the OTLP receiver and the GreptimeDB exporter for
traces/metrics/logs.

## Test infrastructure

Satellite has no tests today. Add:

- dev deps in `pyproject.toml`: `pytest`, `pytest-asyncio`, `pytest-httpx` (or
  `respx`) for mocking the model-server HTTP call.
- `satellite/tests/` with `conftest.py` providing an in-memory telemetry capture
  fixture (a fake sink/exporter that records emitted events and metrics) so tests
  can assert what was collected without a real Collector/GreptimeDB.
- pytest config (asyncio mode, testpaths) in `pyproject.toml`.

Tests use the fake exporter; no live GreptimeDB/Collector is required for the unit
suite.

# Scenarios

## Scenario: off deployment records nothing
**Given** a deployment whose `satellite_parameters` has no `monitoring_mode` (or
`monitoring_mode = "off"`)
**When** an inference request is sent to `/deployments/{id}/compute`
**Then** the model response is returned normally **and** no inference event, metric,
or span is emitted for that request.

## Scenario: full deployment happy path
**Given** a deployment with `satellite_parameters.monitoring_mode = "full"` and a
configured OTLP endpoint
**When** a valid inference request is forwarded and the model server returns output
**Then** an `InferenceEvent` with a UUIDv7 `event_id`, `status = "success"`,
populated `inputs`/`output`, and `latency_ms` is emitted, the `inference.requests`
counter and `inference.latency_ms` histogram are recorded, a span wraps the forward
call, and the same model output is returned to the client.

## Scenario: client-supplied request id is preserved and echoed
**Given** a `full` deployment
**When** the client sends header `X-Request-Id: abc-123`
**Then** the recorded inference event's `request_id` is `abc-123` **and** the
response includes `X-Request-Id: abc-123`.

## Scenario: missing request id is generated
**Given** a `full` deployment
**When** the client sends no `X-Request-Id` header
**Then** the Satellite generates a UUIDv7 `request_id`, records it on the event, and
returns it in the `X-Request-Id` response header.

## Scenario: model failure still records and still errors
**Given** a `full` deployment whose model server returns HTTP 500
**When** an inference request is forwarded
**Then** a failed `InferenceEvent` (`status = "error"`, `status_code = 500`,
populated `error`) and the `inference.errors` counter are emitted, **and** the
endpoint still raises the original `ModelServerError` so the client receives the
same 500/detail as before instrumentation existed.

## Scenario: telemetry backend down does not break inference
**Given** a `full` deployment and an unreachable/failing OTLP endpoint
**When** an inference request is forwarded and the model server returns output
**Then** the telemetry emission error is swallowed and logged at WARNING, **and**
the client still receives the correct model output with normal latency.

## Scenario: secret-backed inputs are never recorded
**Given** a `full` deployment with a dynamic attribute backed by an orbit secret
**When** an inference request is forwarded and the secret value is injected into the
compute body
**Then** the recorded inference event `inputs` contain the model feature payload but
**do not** contain the secret value or the secret-backed dynamic attribute.

## Scenario: invalid monitoring mode falls back to off
**Given** a deployment whose `satellite_parameters.monitoring_mode = "verbose"`
(not a valid mode)
**When** the deployment is registered via `add_deployment` or `sync_deployments`
**Then** its `LocalDeployment.monitoring_mode` is `off` and its inference records
nothing.

## Scenario: mixed modes on one Satellite
**Given** deployment A is `off` and deployment B is `full` on the same Satellite
**When** requests are sent to both
**Then** A emits no inference IO while B emits inference events and metrics; the
shared Collector/GreptimeDB services run for B without causing A to record IO.

## Scenario: global kill switch
**Given** `MONITORING_ENABLED = false`
**When** a request to a `full` deployment is forwarded
**Then** no telemetry is emitted even though the deployment mode is `full`, and
inference proceeds normally.

# Tasks

- [ ] **Task 1 — Monitoring mode plumbing + pytest infrastructure**
  - [ ] Add `MonitoringMode` StrEnum and `parse_monitoring_mode()` helper in
        `satellite/agent/schemas/deployments.py`; export from `agent/schemas`.
  - [ ] Add `monitoring_mode: MonitoringMode = MonitoringMode.OFF` to
        `LocalDeployment`.
  - [ ] Add `monitoring_mode` param to
        `ModelServerHandler.add_single_deployment`; set it on the stored
        `LocalDeployment`.
  - [ ] Derive mode in `add_deployment` (from `deployment.satellite_parameters`)
        and in `sync_deployments` (from `dep.get("satellite_parameters")`), passing
        it through.
  - [ ] Add dev deps (`pytest`, `pytest-asyncio`, `pytest-httpx`/`respx`) and
        pytest config to `satellite/pyproject.toml`; create `satellite/tests/` with
        `conftest.py`.
  - [ ] Tests: mode parsed from `satellite_parameters`; missing/invalid → `off`;
        mode survives `add_deployment` and `sync_deployments`.

- [ ] **Task 2 — OpenTelemetry runtime setup**
  - [ ] Add `opentelemetry-sdk` and `opentelemetry-exporter-otlp-proto-http` to
        `satellite/pyproject.toml`.
  - [ ] Add `MONITORING_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT`,
        `OTEL_SERVICE_NAME` to `satellite/agent/settings.py`.
  - [ ] Create `satellite/agent/monitoring/otel.py`: one-time provider setup
        (Tracer/Meter/Logger), OTLP exporters, resource attrs, the three runtime
        instruments, and a `get_telemetry()` accessor that returns a no-op holder
        when `MONITORING_ENABLED` is false or the endpoint is unset.
  - [ ] Create `satellite/agent/monitoring/events.py` with `InferenceEvent` and
        attribute/metric key constants.
  - [ ] Tests: disabled/unset config yields a no-op telemetry holder that emits
        nothing and never raises; enabled config builds providers and instruments.

- [ ] **Task 3 — Inference instrumentation wrapper wired into serving path**
  - [ ] Create `satellite/agent/monitoring/instrumentation.py` with the
        `instrument_inference(...)` async context manager and its `recorder`
        (`record_success` / `record_error`), emitting span + metrics + structured
        log event, every telemetry call individually best-effort.
  - [ ] Add a secret-safe input capture helper and use it before
        `get_compute_missing_secrets` in `model_compute`; exclude secret-backed
        dynamic attributes.
  - [ ] Update `ModelServerHandler.model_compute` to accept `request_id`, gate on
        `monitoring_mode`, generate `event_id` (`uuid.uuid7()`), and wrap the
        forward call; re-raise `ModelServerError` unchanged after recording.
  - [ ] Update the `compute` endpoint in `satellite/agent/agent_api.py` to read the
        `X-Request-Id` header (preserve or generate UUIDv7), pass `request_id` into
        `model_compute`, and echo `X-Request-Id` in the response header.
  - [ ] Tests (using the fake exporter): off → nothing emitted; full happy path →
        success event + metrics + span; request id preserved/generated and echoed;
        model error → error event emitted and `ModelServerError` still raised;
        exporter failure → inference still succeeds; secrets absent from event;
        kill switch suppresses emission.

- [ ] **Task 4 — docker-compose monitoring stack**
  - [ ] Add `otel-collector` and `greptimedb` services to
        `satellite/docker-compose.yml` on `satellite-network`, with a GreptimeDB
        volume.
  - [ ] Add `satellite/otel/collector-config.yaml` with an OTLP receiver and a
        GreptimeDB exporter for traces, metrics, and logs.
  - [ ] Wire `MONITORING_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT`
        (default `http://otel-collector:4318`), and `OTEL_SERVICE_NAME` into the
        `agent` service env and `.env.example`.
  - [ ] Document the local bring-up and a manual smoke check (send one inference to
        a `full` deployment, confirm rows land in GreptimeDB) in the satellite
        README or a short note.
