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
- **model-server (layer 2)** — wraps the actual model execution in a child span and
  continues the trace using the W3C `traceparent` propagated from the Agent, so the
  Agent and the model server appear as one trace.

Monitoring is **per-deployment**: a deployment setting (`monitoring_enabled` in the
deployment's `satellite_parameters`) decides whether monitoring happens for that
deployment. Telemetry is exported over OTLP to a co-located **OpenTelemetry
Collector**, which writes into a co-located **GreptimeDB**. Both are shipped in the
Satellite stack.

All instrumentation is **best-effort**: monitoring never blocks or alters inference.

## Why this approach

- **Agent-level capture** keeps the core monitoring data independent of model code
  and preserves the current serving contract.
- **model-server child span** gives a meaningful trace (visibility into model
  execution time) without depending on the user's model internals.
- **Per-deployment setting** lets each deployment opt into monitoring; no Platform
  schema change is needed because the flag rides in the existing deployment settings.
- **OpenTelemetry + Collector + GreptimeDB** matches the target architecture of the
  full monitoring spec, so this slice is a real foundation, not throwaway work.
- **Best-effort, non-blocking** honors the rule that inference availability outranks
  monitoring availability.

# Design

## Scope boundary

In scope (this spec):

- advertising a monitoring capability from the Satellite to the Platform
- per-deployment `monitoring_enabled` setting, read from `satellite_parameters`
- local event identity: a single `event_id` (UUIDv7)
- Agent inference instrumentation: structured event, runtime metrics, one span
- model-server child span + W3C trace-context propagation from the Agent
- OpenTelemetry export from both components to a co-located Collector → GreptimeDB
- test infrastructure for the Satellite (does not exist today)

Out of scope (later specs): Monitoring API, dashboard UI, Platform iframe / launch
token, query layer, Monitoring Worker, drift / data-quality / performance
calculations, reference profiles, alerts, delayed targets and realized-performance
metrics, user model-internal spans, container lifecycle management of the monitoring
services.

## Request path & the two services

Two of our services sit in the inference path, and the real model execution happens
in a third place — a subprocess:

- The **Agent** is a single per-Satellite proxy. It authorizes the request and
  forwards it to the target model server.
- The **model server** is a per-deployment container. It receives the forwarded
  request and runs the model inside a separate subprocess (the fnnx runtime), which
  is where the actual `compute` happens.

The Agent is the natural place for capturing inputs, outputs, and runtime metrics,
because it sees the full request and response. The model server is the natural place
for a span around model execution. The model runs in a subprocess, so layer 2 must
reach into that subprocess — this is why it needs its own telemetry setup rather than
riding on the Agent's.

## Capability advertisement

Monitoring is a Satellite capability, and the Platform must never assume it. The
Satellite already advertises its capabilities to the Platform when it pairs; this
slice adds a monitoring capability to that advertisement, so the Platform knows this
Satellite can instrument and collect inference telemetry.

The Platform relies only on the advertised capability: it offers and enables the
per-deployment monitoring setting only for Satellites that advertise monitoring
support, and treats monitoring as unavailable for Satellites that do not. A Satellite
that cannot monitor must not advertise the capability. (The Platform-side handling is
the Platform's own concern; the requirement here is that the Satellite advertises
truthfully so the Platform never has to assume.)

## Per-deployment enablement

Whether a deployment is monitored is controlled by a `monitoring_enabled` flag in
its `satellite_parameters`, defaulting to off (opt-in). This flag is only meaningful
for Satellites that advertise the monitoring capability. The Agent reads the flag when
it registers or syncs a deployment and applies it on that deployment's inference
path.

Separately, the Satellite must have a telemetry endpoint configured (and a global
kill switch left on) for anything to be exported at all. A deployment is monitored
only when both hold: its flag is on **and** telemetry is configured. Otherwise the
inference path runs exactly as today and records nothing.

## Event identity

Each monitored inference gets a single `event_id`, generated by the Agent as a
time-sortable UUIDv7. It is the storage identity of the inference row and the
correlation id carried on the span and the structured log. The Agent echoes it to
the client in an `X-Event-Id` response header so a caller can refer to a specific
inference later.

A client-supplied correlation id for delayed-target joins is out of scope here; the
single `event_id` is enough for now.

## Agent instrumentation (layer 1)

The Agent gains a monitoring component with three responsibilities: a one-time
telemetry setup that builds the tracer, metrics, and event exporter and **no-ops**
cleanly when monitoring is not configured; the definition of the inference-event
shape; and an instrumentation wrapper used around the forward call.

### Inference event

For a monitored inference the Agent records one structured event with these fields:

| Field | Type | Notes |
| --- | --- | --- |
| `event_id` | string | UUIDv7 |
| `deployment_id` | string | |
| `status` | string | `success` or `error` |
| `status_code` | integer, optional | model-server status on error |
| `latency_ms` | number | forward-call latency |
| `inputs` | object, optional | model feature payload, secret-stripped |
| `output` | object, optional | model output payload (success only) |
| `error` | string, optional | error detail (error only) |
| `trace_id` | string, optional | OpenTelemetry trace id |
| `span_id` | string, optional | OpenTelemetry span id |
| `timestamp` | string | ISO-8601 UTC |

### Runtime metrics

| Instrument | Type | Attributes |
| --- | --- | --- |
| `inference.requests` | counter | `deployment_id`, `status` |
| `inference.errors` | counter | `deployment_id`, `status_code` |
| `inference.latency_ms` | histogram | `deployment_id`, `status` |

### Export

- Single export path: Agent → OTLP → OpenTelemetry Collector → GreptimeDB.
- The inference event is emitted as a log record carrying the event fields; runtime
  metrics use the instruments above; the forward call is wrapped in a span.
- Export is batched so emission does not add request latency.

### Trace-context propagation

When monitoring is active the Agent injects its current span context into the
outgoing model-server request as a W3C `traceparent` header, so the model-server
child span nests under the Agent span.

### Best-effort guarantees

- Every telemetry action (span, metric, log, context injection) is individually
  guarded so an exporter or SDK failure is swallowed and logged at warning level,
  never raised.
- A monitoring failure never blocks authorization, never blocks forwarding, and
  never changes the model response body or status.
- On model failure a failed inference event and error metric are still recorded,
  then the original model error is returned to the client unchanged.

### Recording flow

For a monitored inference the Agent resolves the deployment, then:

1. captures the secret-safe inputs **before** secrets are injected;
2. generates the `event_id`;
3. wraps the forward call with instrumentation (timing, span, metrics) and forwards
   the request, now carrying the `traceparent` header;
4. on success records the output; on failure records the status and error, then
   re-raises the original error unchanged.

If the deployment is not monitored, the forward call runs as today and nothing is
recorded.

### Secret safety

Before forwarding, the Agent injects orbit-secret values into the request. The
inputs recorded for the inference event must be captured **before** that injection
and must exclude any secret-backed attribute. Secret values must never appear in a
recorded event, span attribute, or log record.

## model-server instrumentation (layer 2)

The model server runs the model inside a subprocess. To produce a child span that
joins the Agent's trace:

- **Continue the trace**: the model server reads the incoming `traceparent` header
  (its request layer does not read headers today, so this must be added) and
  continues the trace from it.
- **Span around execution**: the model-server request handler wraps the model
  execution in a child span and records status and errors on it.
- **Telemetry at runtime**: the telemetry dependencies and the endpoint configuration
  must be available inside the model-server runtime (including the model's own
  environment) so the worker can export spans.

Layer 2 is best-effort too: any telemetry failure in the model server must not affect
the model response. If the model server is unmonitored or telemetry is unavailable,
execution behaves exactly as today.

## Local storage

GreptimeDB is the local source of truth. Logical datasets for this slice:

| Dataset | Purpose |
| --- | --- |
| `inference_events` | request-level inputs, outputs, status, latency, and errors |
| `runtime_metrics` | request volume, latency, and errors |
| `otel_traces` | Agent and model-server spans with deployment attributes |
| `otel_logs` | local operational logs with deployment attributes |

The two spans (Agent parent + model-server child) share one trace id in
`otel_traces`.

## Infrastructure

The Satellite stack gains two co-located services:

- an **OpenTelemetry Collector** that receives telemetry over OTLP and forwards it to
  GreptimeDB;
- a **GreptimeDB** instance that stores telemetry, with persistent local storage.

Both ship with the Satellite and are configured through its stack definition; the
Agent and the model servers are pointed at the Collector, and the Collector at
GreptimeDB.

## Test infrastructure

The Satellite has no tests today. This slice adds a test setup (a test runner with
async support and HTTP mocking for the model-server call) and a shared fake-telemetry
fixture that records emitted events, metrics, and spans, so tests can assert what
would be collected without a live Collector or GreptimeDB.

# Scenarios

## Scenario: monitoring disabled for the deployment records nothing
**Given** a deployment whose settings do not enable monitoring
**When** an inference request is sent to it
**Then** the model response is returned normally **and** no inference event, metric,
or span is emitted for that request.

## Scenario: telemetry not configured is a no-op
**Given** a deployment with monitoring enabled but no telemetry endpoint configured
on the Satellite (or the global kill switch off)
**When** an inference request is forwarded
**Then** nothing is emitted and inference proceeds normally.

## Scenario: monitored deployment happy path
**Given** a monitored deployment on a Satellite with telemetry configured
**When** a valid inference request is forwarded and the model returns output
**Then** an inference event with an `event_id`, success status, populated inputs and
output, and latency is recorded, the request and latency metrics are updated, an
Agent span wraps the forward call, and the same model output is returned to the
client.

## Scenario: event id is generated and echoed
**Given** a monitored deployment
**When** an inference request is forwarded
**Then** the Agent generates an `event_id`, records it on the event and span, and
returns it in the `X-Event-Id` response header.

## Scenario: trace continuity across Agent and model server
**Given** a monitored deployment
**When** an inference request is forwarded
**Then** the Agent propagates trace context and the model-server child span shares the
same trace as the Agent span.

## Scenario: model failure still records and still errors
**Given** a monitored deployment whose model returns an error
**When** an inference request is forwarded
**Then** a failed inference event (error status, status code, error detail) and the
error metric are recorded, **and** the client still receives the same error as before
instrumentation existed.

## Scenario: telemetry backend down does not break inference
**Given** a monitored deployment and an unreachable or failing telemetry backend
**When** an inference request is forwarded and the model returns output
**Then** the telemetry error is swallowed and logged at warning level, **and** the
client still receives the correct model output with normal latency.

## Scenario: model-server telemetry failure does not break inference
**Given** a monitored deployment whose model server cannot export spans
**When** the model executes
**Then** the span error is swallowed and the model response is returned unchanged.

## Scenario: secret-backed inputs are never recorded
**Given** a monitored deployment with an attribute backed by an orbit secret
**When** an inference request is forwarded and the secret value is injected
**Then** the recorded event inputs contain the model feature payload but **do not**
contain the secret value or the secret-backed attribute.

## Scenario: enablement flag survives registration
**Given** a deployment whose settings enable monitoring
**When** the Agent registers or syncs that deployment
**Then** it is treated as monitored; an absent or invalid flag is treated as off.

## Scenario: Satellite advertises its monitoring capability
**Given** a Satellite that supports monitoring instrumentation
**When** it pairs with the Platform
**Then** its advertised capabilities include monitoring, so the Platform can rely on
the advertisement instead of assuming support.

# Tasks

- [x] **Task 1 — Monitoring capability, per-deployment flag + test setup**
  - [x] Advertise a monitoring capability in the Satellite's capabilities sent to the
        Platform at pairing, so the Platform never has to assume monitoring support.
  - [x] Read the `monitoring_enabled` flag from a deployment's settings and carry it
        on the Agent's record of that deployment, across every path that registers or
        syncs deployments; default off, absent/invalid means off.
  - [x] Add the base Satellite test setup (test runner with async support and HTTP
        mocking for the model-server call).
  - [x] Tests: capabilities include monitoring; flag read correctly; absent/invalid
        means off; flag preserved through deployment registration and sync.

- [x] **Task 2 — Agent telemetry setup**
  - [x] Add OpenTelemetry to the Agent and define its settings (telemetry endpoint
        and global kill switch).
  - [x] Provide the telemetry component that builds the tracer, metrics, and event
        exporter and is a no-op when monitoring is not configured.
  - [x] Define the inference-event shape and the runtime metrics.
  - [x] Add a shared fake-telemetry fixture that captures emitted events, metrics, and
        spans, so this and later tasks can assert collected data without a live
        Collector or GreptimeDB.
  - [x] Tests: no-op when disabled or unconfigured, never raising; active when
        configured.

- [ ] **Task 3 — Agent inference instrumentation**
  - [ ] Wrap the Agent's forward-to-model call so that, for a monitored deployment,
        it captures secret-safe inputs, generates the `event_id`, records the event,
        metrics, and span, and propagates trace context to the model server.
  - [ ] Return the `event_id` to the client in the `X-Event-Id` header.
  - [ ] Keep everything best-effort and re-raise model errors unchanged after
        recording.
  - [ ] Tests: disabled records nothing; happy path records event + metrics + span;
        `event_id` echoed; model error recorded and still raised; telemetry failure
        does not break inference; secrets absent from the event.

- [ ] **Task 4 — model-server child span**
  - [ ] Make the model server read the incoming trace context and wrap model
        execution in a child span continued from it, exporting to the Collector;
        best-effort.
  - [ ] Ensure the telemetry dependencies and endpoint are available inside the
        model-server runtime.
  - [ ] Tests where feasible: span created when trace context is present; execution
        unaffected when telemetry is off or failing.

- [ ] **Task 5 — Collector + GreptimeDB in the Satellite stack**
  - [ ] Add the OpenTelemetry Collector and GreptimeDB to the Satellite stack, with
        the Collector configured to store telemetry in GreptimeDB and the Agent
        pointed at the Collector.
  - [ ] Configure the Collector to route each signal to its dataset: inference-event
        log records to `inference_events`, metrics to `runtime_metrics`, spans to
        `otel_traces`, and operational logs to `otel_logs`.
  - [ ] Set the telemetry-endpoint and kill-switch values for the Agent (and model
        servers) in the stack so both export to the co-located Collector.
  - [ ] Document local bring-up and a manual smoke check: one inference to a monitored
        deployment produces an inference event and a two-span trace in GreptimeDB;
        disabling the deployment flag records nothing while inference still works.