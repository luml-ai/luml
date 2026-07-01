# Local Bring-up & Smoke Test

## Prerequisites

- Docker and Docker Compose installed
- A valid `SATELLITE_TOKEN` from the Platform

## Bring up the stack

```bash
cd satellite
cp .env.example .env
# Edit .env and set SATELLITE_TOKEN
docker compose up -d
```

This starts four services on the `satellite-network`:

| Service | Purpose |
|---------|---------|
| `greptimedb` | Time-series store for telemetry |
| `otel-collector` | Receives OTLP from Agent/model-servers, routes to GreptimeDB |
| `agent` | Satellite Agent (exports to `otel-collector:4317`) |
| `model-image` | Base model-server image (exits immediately; used as build cache) |

Wait for all services to be healthy:

```bash
docker compose ps
```

## Deploy a monitored model

Create a deployment on the Platform with `satellite_parameters.monitoring_enabled = true`.
The Agent picks it up on its next sync cycle (default 2 s).

## Send an inference request

```bash
curl -s -D- http://localhost/deployments/<DEPLOYMENT_ID>/compute \
  -H "Content-Type: application/json" \
  -d '{"dynamic_attributes": {"feature_a": 1.0, "feature_b": 2.0}}'
```

A successful response includes:
- HTTP 200 with the model output in the body
- An `X-Event-Id` header containing the UUIDv7 event identifier

## Verify telemetry in GreptimeDB

Query the GreptimeDB HTTP API (port 4000 on the host is not exposed by
default; exec into the container or add a port mapping):

```bash
# Inference event
docker compose exec greptimedb curl -s \
  'http://localhost:4000/v1/sql?sql=SELECT+*+FROM+inference_events+ORDER+BY+greptime_timestamp+DESC+LIMIT+5'

# Two-span trace (Agent parent + model-server child)
docker compose exec greptimedb curl -s \
  'http://localhost:4000/v1/sql?sql=SELECT+*+FROM+otel_traces+ORDER+BY+greptime_timestamp+DESC+LIMIT+5'

# Runtime metrics
docker compose exec greptimedb curl -s \
  'http://localhost:4000/v1/sql?sql=SELECT+*+FROM+runtime_metrics+ORDER+BY+greptime_timestamp+DESC+LIMIT+5'
```

### Expected results

- **`inference_events`** contains a row with the `event_id`, `deployment_id`,
  `status=success`, populated `inputs` and `output`, and `latency_ms`.
- **`otel_traces`** contains two spans sharing the same `trace_id`: one from
  `satellite-agent` (the forward call) and one from `satellite-model-server`
  (`model.execute`).
- **`runtime_metrics`** shows counters for `inference.requests` and a histogram
  for `inference.latency_ms`.

## Verify monitoring-disabled produces nothing

Set `monitoring_enabled = false` on the deployment (or remove it), wait for a
sync cycle, then send another inference request. The model response should
still return normally, but no new rows should appear in the GreptimeDB tables.
