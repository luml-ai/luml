---
sidebar_label: Satellite Instrumentation Spec
title: Satellite Inference Instrumentation & Collection Spec
---

# Proposals

## Problem

The Satellite serves model inference but records nothing about it. When a deployed
model is queried through the Satellite Agent there is no request-level history: no
inputs, no outputs, no latency, no error record, no trace. Without this raw
collection layer none of the downstream live-monitoring features (runtime health,
data quality, drift, alerts) can be built, because they all read from data that
does not exist yet.

This spec is the **first slice** of the larger Live Monitoring architecture,
deliberately scoped to one thing: **make inference instrumentation and local
collection work on the Satellite.** Everything that consumes the collected data
(dashboard, Monitoring API, query layer, worker, drift/quality calculations,
Platform iframe launch, target submission, alerts, reference profiles) is out of
scope here and will be specified separately.

## Solution at a glance

The inference request path has two of our own services:

```text
client → Agent (proxy) → model-server container (fnnx runtime) → back to client
```

We instrument both, in two layers:

- **Agent (layer 1)** — wraps the call that forwards a request to the model server.
  It generates a local `event_id`, times the call, captures the model input
  (secret-safe — only the model's feature inputs are recorded; injected secret
  values are never stored), the output or error, status, and latency, and emits a
  span, runtime metrics, and a structured inference-event log over OpenTelemetry.
  This is the core monitoring data that downstream features need.
- **model-server (layer 2)** — wraps the actual model `compute` in a child span and
  continues the trace using the W3C `traceparent` propagated from the Agent, so the
  Agent and the model server appear as one trace.

Monitoring is **per-deployment**: a deployment setting (`monitoring_enabled` in the
deployment's `satellite_parameters`) decides whether monitoring happens for that
deployment. Telemetry is exported over OTLP to a co-located **OpenTelemetry
Collector**, which writes into a co-located **GreptimeDB**. Both are shipped in the
Satellite `docker-compose` stack.

All instrumentation is **best-effort**: monitoring never blocks or alters inference.

## Why this approach

- **Agent-level capture** keeps the core monitoring data independent of model code
  and preserves the current serving contract.
- **model-server child span** gives a meaningful trace (visibility into model
  execution time) without depending on the user's model internals.
- **Per-deployment setting** lets each deployment opt into monitoring; no Platform
  schema change is needed because the flag rides in the existing
  `satellite_parameters`.
- **OpenTelemetry + Collector + GreptimeDB** matches the target architecture of the
  full monitoring spec, so this slice is a real foundation, not throwaway work.
- **Best-effort, non-blocking** honors the rule that inference availability outranks
  monitoring availability.

# Design

## Scope boundary

In scope (this spec):

- per-deployment `monitoring_enabled` setting, read from `satellite_parameters`
- local event identity: a single `event_id` (UUIDv7)
- Agent inference instrumentation: structured event, runtime metrics, one span
- model-server child span + W3C trace-context propagation from the Agent
- OpenTelemetry SDK export from both components to a co-located Collector → GreptimeDB
- `docker-compose` services for the Collector and GreptimeDB
- pytest test infrastructure for the Satellite (does not exist today)

Out of scope (later specs): Monitoring API, dashboard UI, Platform iframe / launch
token, query layer, Monitoring Worker, drift / data-quality / performance
calculations, reference profiles, alerts, delayed targets and realized-performance
metrics, user model-internal spans, container lifecycle management of the monitoring
services.

## Request path & the two services (grounding)

There are two of our services in the inference path, and the real inference runs in
a third place — a conda subprocess. An inference request travels as follows:

1. The Agent receives `POST /deployments/{deployment_id}/compute` in `agent_api.py`
   (after `verify_token`).
2. The endpoint calls `ModelServerHandler.model_compute` in
   `agent/handlers/model_server_handler.py`.
3. That calls `ModelServerClient.compute` in `agent/clients/model_server_client.py`,
   which sends an HTTP POST to `http://sat-{deployment_id}:{MODEL_SERVER_PORT}/compute`.
4. Inside the model-server container, the request reaches the conda subprocess
   (`conda_worker.py`, the `/compute` handler), which runs `compute_model` →
   `handler.compute_async`, i.e. the actual model.


## Per-deployment enablement

Monitoring for a deployment is gated by a boolean `monitoring_enabled` read from
that deployment's `satellite_parameters`. The value is parsed leniently (`true` mean enabled); an absent or unrecognized value means disabled. The
parsing is exposed as a small helper next to the deployment schema so both the
deployment-registration paths can reuse it.

- `LocalDeployment` gains a `monitoring_enabled` boolean, defaulting to disabled
  (opt-in).
- `ModelServerHandler.add_single_deployment` gains a `monitoring_enabled` parameter
  and stores it on the `LocalDeployment`.
- `add_deployment(deployment: Deployment)` derives the flag from
  `deployment.satellite_parameters` and passes it down.
- `sync_deployments` derives the flag from each `dep.get("satellite_parameters")`
  dict and passes it down.

Satellite-level infra availability is separate and governs whether anything can be
exported at all (`settings.py`):

- `MONITORING_ENABLED: bool = True` — global kill switch.
- `OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None` — Collector OTLP endpoint; if
  unset, telemetry providers are no-op even for enabled deployments.
- `OTEL_SERVICE_NAME: str = "satellite-agent"`.

A deployment is monitored **iff** `LocalDeployment.monitoring_enabled` is true **and**
`MONITORING_ENABLED` is true **and** an OTLP endpoint is configured. Otherwise the
inference path runs exactly as today and records nothing.

## Event identity

- `event_id` — generated by the Agent per inference with `uuid.uuid7()` (Python 3.14
  stdlib, time-sortable). It is the storage identity (primary key) of the inference
  row and the correlation id carried on the span and the structured log.
- The Agent optionally echoes it to the client in an `X-Event-Id` response header so
  a caller can refer to a specific inference later.

The client-supplied `request_id` used for delayed-target joins is **out of scope**
here and will be added with the targets spec; for now the single `event_id` is
enough.

## Agent instrumentation (layer 1)

New package `satellite/agent/monitoring/`:

| File | Responsibility |
| --- | --- |
| `__init__.py` | exports `instrument_inference`, `get_telemetry`, models |
| `otel.py` | one-time OpenTelemetry SDK setup (Tracer/Meter/Logger providers, OTLP exporters, resource attrs, the runtime instruments); reads config from settings; returns a `Telemetry` holder that **no-ops** when `MONITORING_ENABLED` is false or the endpoint is unset |
| `events.py` | `InferenceEvent` pydantic model and the metric/attribute key constants |
| `instrumentation.py` | `instrument_inference(...)` async context manager that times the forward call, captures input/output/status/latency, and emits span + metrics + structured log event, all best-effort |

### `InferenceEvent` (events.py)

The structured inference event carries these fields:

| Field | Type | Notes |
| --- | --- | --- |
| `event_id` | string | UUIDv7 |
| `deployment_id` | string | |
| `status` | string | `success` or `error` |
| `status_code` | integer, optional | model-server HTTP status on error |
| `latency_ms` | number | forward-call latency |
| `inputs` | object, optional | model feature payload, secret-stripped |
| `output` | object, optional | model output payload (success only) |
| `error` | string, optional | error detail (error only) |
| `trace_id` | string, optional | OpenTelemetry trace id |
| `span_id` | string, optional | OpenTelemetry span id |
| `timestamp` | string | ISO-8601 UTC |

### Runtime metrics (OTel instruments, created once in otel.py)

| Instrument | Type | Attributes |
| --- | --- | --- |
| `inference.requests` | counter | `deployment_id`, `status` |
| `inference.errors` | counter | `deployment_id`, `status_code` |
| `inference.latency_ms` | histogram | `deployment_id`, `status` |

### Recorded fields

In a monitored deployment the Agent wraps the forward call and records: deployment
id, `event_id`, model input payload (secret-safe), output payload or error detail,
status, latency, and OpenTelemetry `trace_id` / `span_id`.

### Export

- Single export path: Agent OTel SDK → OTLP/HTTP → OpenTelemetry Collector →
  GreptimeDB.
- The inference event is emitted as an **OTel log record** whose attributes carry
  the `InferenceEvent` fields and whose body is the JSON event. Runtime metrics use
  the instruments above. The forward call is wrapped in a span.
- Exporters are batched so emission does not add request latency.

### Trace-context propagation

When monitoring is active the Agent injects the current span context into the
outgoing model-server request as a W3C `traceparent` header (OpenTelemetry
propagator) inside `ModelServerClient.compute`, so the model-server child span nests
under the Agent span.

### Best-effort guarantees (implemented in instrumentation.py / otel.py)

- Every telemetry call (span start/end, metric record, log emit, context injection)
  is individually wrapped so an exporter or SDK failure is swallowed and logged at
  WARNING, never raised.
- A monitoring failure never blocks authorization, never blocks forwarding, and
  never changes the model response body or status.
- On model failure a failed inference event + error metric are still emitted, then
  the original `ModelServerError` is re-raised unchanged so the endpoint returns the
  same status/detail as today.

### Wiring into `model_compute`

`ModelServerHandler.model_compute` resolves the deployment, then:

1. If the deployment is not monitored (flag off, or infra unavailable), it injects
   secrets and forwards to the model server exactly as today, recording nothing.
2. Otherwise it captures the secret-safe inputs **before** secret injection, injects
   secrets, and generates an `event_id`.
3. It opens the instrumentation context and forwards the request to the model server
   (which now carries the `traceparent` header).
4. On success it records the output on the event; on `ModelServerError` it records
   the status code and detail, then re-raises the same error unchanged; any other
   exception is recorded as an error and re-raised.

The instrumentation context owns timing, the span, the metrics, and emitting the
structured event, so the serving logic stays unchanged apart from the gate and the
record calls.

### Secret safety

`get_compute_missing_secrets` injects orbit secret values into
`body["dynamic_attributes"]`. The captured `inputs` for the inference event must be
taken **before** secret injection and must exclude any dynamic attribute that is
secret-backed (`deployment.dynamic_attributes_secrets`). Secret values must never
appear in a recorded inference event, span attribute, or log record.

## model-server instrumentation (layer 2)

The model server runs `/compute` inside the conda-env subprocess
(`conda_worker.py`). To produce a child span that joins the Agent's trace:

- **Read headers** in the ASGI layer: `base_service.py` currently ignores
  `scope["headers"]`. Extend the POST dispatch so the `traceparent` header is parsed
  and made available to the `/compute` handler.
- **OTel setup in the worker**: `conda_worker.py` initializes a TracerProvider + OTLP
  exporter (reads `OTEL_EXPORTER_OTLP_ENDPOINT` from env) once at startup.
- **Child span**: in the `/compute` handler, extract the parent context from
  `traceparent` and start a span around `compute_model`; record status/error.
- **Conda env deps**: add `opentelemetry-sdk` and
  `opentelemetry-exporter-otlp-proto-http` to the model environment in
  `ModelHandler._get_default_env_spec` so they exist inside the worker's env.
- **Env wiring**: `DeployTask._get_container_env` adds `OTEL_EXPORTER_OTLP_ENDPOINT`
  and `OTEL_SERVICE_NAME` (e.g. `model-server-{deployment_id}`) to the container env;
  the conda subprocess inherits it.

Layer 2 is best-effort too: any OTel failure in the worker must not affect the model
response. If the model server is unmonitored or OTel is unavailable, `/compute`
behaves exactly as today.

## Local storage model

GreptimeDB is the local source of truth. Logical datasets for this slice:

| Dataset | Purpose |
| --- | --- |
| `inference_events` | request-level inputs, outputs, status, latency, and errors |
| `runtime_metrics` | request volume, latency, and errors |
| `otel_traces` | Agent and model-server spans with deployment attributes |
| `otel_logs` | local operational logs with deployment attributes |

The two spans (Agent parent + model-server child) share one trace id in
`otel_traces`.

## docker-compose additions

Add two services on the existing `satellite-network`:

- `otel-collector` (`otel/opentelemetry-collector-contrib`): OTLP receiver on `4318`
  (HTTP); pipeline exports traces, metrics, and logs to GreptimeDB; config mounted
  from `satellite/otel/collector-config.yaml`.
- `greptimedb` (`greptime/greptimedb`): exposes its OTLP ingest and query ports;
  named volume for persistence.
- `agent` env gains `MONITORING_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT` (default
  `http://otel-collector:4318`), and `OTEL_SERVICE_NAME`.

`collector-config.yaml` defines the OTLP receiver and the GreptimeDB exporter for
traces, metrics, and logs.

## Test infrastructure

The Satellite has no tests today. Add:

- dev deps in `satellite/pyproject.toml`: `pytest`, `pytest-asyncio`, and
  `respx`/`pytest-httpx` for mocking the model-server HTTP call.
- `satellite/tests/` with `conftest.py` providing an in-memory telemetry capture
  fixture (a fake exporter that records emitted spans, metrics, and log events) so
  tests assert what was collected without a real Collector/GreptimeDB.
- pytest config (asyncio mode, testpaths) in `pyproject.toml`.

# Scenarios

## Scenario: monitoring disabled for the deployment records nothing
**Given** a deployment whose `satellite_parameters` does not set
`monitoring_enabled` (or sets it false)
**When** an inference request is sent to `/deployments/{id}/compute`
**Then** the model response is returned normally **and** no inference event, metric,
or span is emitted for that request.

## Scenario: infra not configured is a no-op
**Given** a deployment with `monitoring_enabled = true` but no
`OTEL_EXPORTER_OTLP_ENDPOINT` configured (or `MONITORING_ENABLED = false`)
**When** an inference request is forwarded
**Then** nothing is emitted and inference proceeds normally.

## Scenario: monitored deployment happy path
**Given** a deployment with `monitoring_enabled = true` and a configured OTLP
endpoint
**When** a valid inference request is forwarded and the model server returns output
**Then** an `InferenceEvent` with a UUIDv7 `event_id`, `status = "success"`,
populated `inputs`/`output`, and `latency_ms` is emitted, the `inference.requests`
counter and `inference.latency_ms` histogram are recorded, an Agent span wraps the
forward call, and the same model output is returned to the client.

## Scenario: event id is generated and echoed
**Given** a monitored deployment
**When** an inference request is forwarded
**Then** the Agent generates a UUIDv7 `event_id`, records it on the event/span, and
returns it in the `X-Event-Id` response header.

## Scenario: trace continuity across Agent and model server
**Given** a monitored deployment
**When** an inference request is forwarded
**Then** the Agent injects a `traceparent` header, and the model-server child span
shares the same trace id as the Agent span in `otel_traces`.

## Scenario: model failure still records and still errors
**Given** a monitored deployment whose model server returns HTTP 500
**When** an inference request is forwarded
**Then** a failed `InferenceEvent` (`status = "error"`, `status_code = 500`,
populated `error`) and the `inference.errors` counter are emitted, **and** the
endpoint still raises the original `ModelServerError` so the client receives the
same 500/detail as before instrumentation existed.

## Scenario: telemetry backend down does not break inference
**Given** a monitored deployment and an unreachable/failing OTLP endpoint
**When** an inference request is forwarded and the model server returns output
**Then** the telemetry emission error is swallowed and logged at WARNING, **and** the
client still receives the correct model output with normal latency.

## Scenario: model-server OTel failure does not break inference
**Given** a monitored deployment whose worker cannot export spans
**When** `/compute` runs
**Then** the span error is swallowed and the model response is returned unchanged.

## Scenario: secret-backed inputs are never recorded
**Given** a monitored deployment with a dynamic attribute backed by an orbit secret
**When** an inference request is forwarded and the secret value is injected into the
compute body
**Then** the recorded inference event `inputs` contain the model feature payload but
**do not** contain the secret value or the secret-backed dynamic attribute.

## Scenario: enablement flag survives registration
**Given** a deployment with `satellite_parameters.monitoring_enabled = true`
**When** the deployment is registered via `add_deployment` or `sync_deployments`
**Then** its `LocalDeployment.monitoring_enabled` is true; an absent/invalid value
yields false.

# Tasks

- [ ] **Task 1 — Per-deployment enablement plumbing + pytest infrastructure**
  - [ ] Add a `monitoring_enabled(satellite_parameters)` helper in
        `satellite/agent/schemas/deployments.py`; export from `agent/schemas`.
  - [ ] Add `monitoring_enabled: bool = False` to `LocalDeployment`.
  - [ ] Add `monitoring_enabled` param to
        `ModelServerHandler.add_single_deployment`; set it on the stored
        `LocalDeployment`.
  - [ ] Derive the flag in `add_deployment` (from `deployment.satellite_parameters`)
        and in `sync_deployments` (from `dep.get("satellite_parameters")`), passing
        it through.
  - [ ] Add dev deps (`pytest`, `pytest-asyncio`, `respx`/`pytest-httpx`) and pytest
        config to `satellite/pyproject.toml`; create `satellite/tests/` with
        `conftest.py`.
  - [ ] Tests: flag parsed from `satellite_parameters`; missing/invalid → false;
        flag survives `add_deployment` and `sync_deployments`.

- [ ] **Task 2 — Agent OpenTelemetry runtime setup**
  - [ ] Add `opentelemetry-sdk` and `opentelemetry-exporter-otlp-proto-http` to
        `satellite/pyproject.toml`.
  - [ ] Add `MONITORING_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`
        to `satellite/agent/settings.py`.
  - [ ] Create `satellite/agent/monitoring/otel.py` (providers, OTLP exporters,
        resource attrs, the three instruments, a `get_telemetry()` accessor that
        returns a no-op holder when disabled or the endpoint is unset) and
        `events.py` (`InferenceEvent` + key constants).
  - [ ] Tests: disabled/unset config yields a no-op holder that emits nothing and
        never raises; enabled config builds providers and instruments.

- [ ] **Task 3 — Agent inference instrumentation wired into serving path**
  - [ ] Create `satellite/agent/monitoring/instrumentation.py` with
        `instrument_inference(...)` and its `recorder`
        (`record_success`/`record_error`), emitting span + metrics + structured log
        event, every telemetry call individually best-effort.
  - [ ] Add a secret-safe input capture helper; capture before
        `get_compute_missing_secrets` in `model_compute`; exclude secret-backed
        dynamic attributes.
  - [ ] Update `ModelServerHandler.model_compute` to gate on `monitoring_enabled` +
        infra, generate `event_id` (`uuid.uuid7()`), wrap the forward call, and
        re-raise `ModelServerError` unchanged after recording.
  - [ ] Inject the `traceparent` header in `ModelServerClient.compute` from the
        active span context (best-effort).
  - [ ] Echo `X-Event-Id` from the `compute` endpoint in
        `satellite/agent/agent_api.py`.
  - [ ] Tests (fake exporter): disabled → nothing; happy path → event + metrics +
        span; `event_id` echoed; model error → error event emitted and
        `ModelServerError` still raised; exporter failure → inference still succeeds;
        secrets absent from event.

- [ ] **Task 4 — model-server child span + trace-context propagation**
  - [ ] Extend `satellite/model_server/services/base_service.py` to parse request
        headers from `scope["headers"]` and expose `traceparent` to the `/compute`
        handler.
  - [ ] Initialize OTel (TracerProvider + OTLP exporter) once in
        `satellite/model_server/conda_worker.py`; wrap `compute_model` in a child
        span continued from the propagated context; best-effort.
  - [ ] Add `opentelemetry-sdk` + `opentelemetry-exporter-otlp-proto-http` to the
        model conda env in `ModelHandler._get_default_env_spec`.
  - [ ] Wire `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_SERVICE_NAME` into the
        model-server container env via `DeployTask._get_container_env`.
  - [ ] Tests where feasible (header parsing in `base_service.py`; span created when
        `traceparent` present; `/compute` unaffected when OTel disabled/fails).

- [ ] **Task 5 — docker-compose monitoring stack**
  - [ ] Add `otel-collector` and `greptimedb` services to
        `satellite/docker-compose.yml` on `satellite-network`, with a GreptimeDB
        volume.
  - [ ] Add `satellite/otel/collector-config.yaml` with an OTLP receiver and a
        GreptimeDB exporter for traces, metrics, and logs.
  - [ ] Wire `MONITORING_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT` (default
        `http://otel-collector:4318`), and `OTEL_SERVICE_NAME` into the `agent`
        service env and `.env.example`.
  - [ ] Document local bring-up and a manual smoke check: send one inference to a
        monitored deployment, confirm an `inference_events` row and a two-span trace
        (Agent parent + model-server child) land in GreptimeDB; flip the deployment
        flag off and confirm nothing is recorded while inference still succeeds.
