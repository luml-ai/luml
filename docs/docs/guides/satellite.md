---
sidebar_position: 4
---

# How To Connect A Satellite

A Satellite is a compute node you host yourself that executes models and serves inference requests. Before you can deploy, at least one Satellite must be connected to the Orbit. This guide walks through registering the Satellite in Luml and launching it with Docker on a single host. To run the Satellite in a Kubernetes or OpenShift cluster instead, register it the same way and continue with [How To Run A Satellite On Kubernetes](./satellite_kubernetes.md).

## Register the Satellite in Luml

Open the **Satellites** module in the sidebar and click **Create Satellite**. Give it a name, fill in the required fields, and copy the **Token** the platform generates — you will need it to pair the Satellite with Luml.

![](/img/satellite-connect.webp)
![](/img/satellite-connect2.webp)

The dialog does not ask whether the Satellite runs on Docker or Kubernetes. The Satellite reports its kind when it pairs, and Luml shows it on the Satellite card.

## Launch the Satellite with Docker

The Docker Satellite runs every model deployment as a container on the same Docker daemon. It ships as public Docker images on GitHub Container Registry:

| Image | Purpose |
|---|---|
| [`ghcr.io/luml-ai/luml-satellite-agent`](https://github.com/luml-ai/luml/pkgs/container/luml-satellite-agent) | The Satellite itself: pairs with Luml, runs deployments, serves inference and the monitoring dashboard |
| [`ghcr.io/luml-ai/luml-model-server`](https://github.com/luml-ai/luml/pkgs/container/luml-model-server) | The image every model container starts from |

The Satellite stores inference events and monitoring results in GreptimeDB and receives traces through an OpenTelemetry collector. The setup below starts both next to the agent.

**1. Create a working directory** on the host machine:

```bash
mkdir luml-satellite && cd luml-satellite
```

**2. Create `docker-compose.yml`** with the following content:

```yaml
name: satellite

networks:
  satellite-network:
    driver: bridge

volumes:
  greptimedb-data:

services:
  agent:
    image: ghcr.io/luml-ai/luml-satellite-agent:latest
    networks:
      - satellite-network
    environment:
      SATELLITE_TOKEN: ${SATELLITE_TOKEN:?Set SATELLITE_TOKEN in .env}
      PLATFORM_URL: ${PLATFORM_URL:-https://api.luml.ai}
      BASE_URL: ${BASE_URL:-http://localhost}
      MODEL_IMAGE: ${MODEL_IMAGE:-ghcr.io/luml-ai/luml-model-server:latest}
      POLL_INTERVAL_SEC: ${POLL_INTERVAL_SEC:-2}
      MONITORING_ENABLED: "true"
      MONITORING_FRAME_ANCESTORS: ${MONITORING_FRAME_ANCESTORS:-https://app.luml.ai}
      GREPTIMEDB_HOST: greptimedb
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4317
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    user: "0:0"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    ports:
      - "80:8000"
    restart: unless-stopped
    depends_on:
      - model-server
      - otel-collector

  model-server:
    image: ghcr.io/luml-ai/luml-model-server:latest
    platform: linux/amd64
    command: ["true"]

  greptimedb:
    image: greptime/greptimedb:v0.13.1
    command: standalone start --http-addr=0.0.0.0:4000 --rpc-addr=0.0.0.0:4001
    networks:
      - satellite-network
    volumes:
      - greptimedb-data:/tmp/greptimedb
    restart: unless-stopped

  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.127.0
    command: ["--config=/etc/otel/config.yaml"]
    networks:
      - satellite-network
    volumes:
      - ./otel-collector-config.yaml:/etc/otel/config.yaml:ro
    depends_on:
      - greptimedb
    restart: unless-stopped
```

The top-level `name: satellite` pins the Compose project name, so the network and containers are prefixed with `satellite_` regardless of what the working directory is called. The `model-server` service only pulls the model image ahead of time and exits.

**3. Create `otel-collector-config.yaml`** in the same directory:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: "0.0.0.0:4317"

exporters:
  otlphttp/traces:
    endpoint: "http://greptimedb:4000/v1/otlp"
    tls:
      insecure: true
    headers:
      x-greptime-db-name: public
      x-greptime-trace-table-name: otel_traces

  otlphttp/events:
    endpoint: "http://greptimedb:4000/v1/otlp"
    tls:
      insecure: true
    headers:
      x-greptime-db-name: public
      x-greptime-trace-table-name: inference_events

processors:
  filter/traces_main:
    error_mode: ignore
    traces:
      span:
        - 'resource.attributes["service.name"] == "satellite-agent.events"'
  filter/traces_events:
    error_mode: ignore
    traces:
      span:
        - 'resource.attributes["service.name"] != "satellite-agent.events"'

service:
  pipelines:
    traces/main:
      receivers: [otlp]
      processors: [filter/traces_main]
      exporters: [otlphttp/traces]
    traces/events:
      receivers: [otlp]
      processors: [filter/traces_events]
      exporters: [otlphttp/events]
```

**4. Create `.env`** in the same directory and paste the token from the previous step into `SATELLITE_TOKEN`:

```env
# Required: token issued by the platform
SATELLITE_TOKEN=replace-with-your-token

# Public base URL of the Satellite (used to report inference endpoints)
BASE_URL=http://localhost
```

| Variable | Default | Meaning |
|---|---|---|
| `SATELLITE_TOKEN` | — | Token issued by Luml. Required. |
| `BASE_URL` | `http://localhost` | Address other services use to reach the Satellite. Inference endpoints and the monitoring dashboard are published under it. |
| `PLATFORM_URL` | `https://api.luml.ai` | Luml API the Satellite pairs with. |
| `MODEL_IMAGE` | `ghcr.io/luml-ai/luml-model-server:latest` | Image model containers start from. |
| `MONITORING_FRAME_ANCESTORS` | `https://app.luml.ai` | Origins allowed to embed the monitoring dashboard, separated by spaces. |
| `POLL_INTERVAL_SEC` | `2` | How often the Satellite polls Luml for tasks, in seconds. |

**5. Launch the Satellite:**

```bash
docker compose up -d
```

Compose pulls the images and starts the containers in the background. The Satellite connects to Luml using the token, registers its capabilities, and begins polling for tasks. To confirm it is online, return to the **Satellites** module in Luml — the Satellite's status should switch to *Connected*.

On the first deployment the Satellite creates its own Docker network, `luml-satellite-<satellite id>`, and starts model containers in it.

To check the Satellite's logs or stop it later:

```bash
docker compose logs -f agent   # follow the Satellite's logs
docker compose down            # stop and remove the containers
```

Undeploy models through Luml before you run `docker compose down`. Model containers are started by the Satellite, not by Compose, and keep running after the stack stops.

### Update the Satellite

The images are tagged `latest`, so an update is a pull and a restart:

```bash
docker compose pull
docker compose up -d
```

To stay on a fixed release, replace `latest` with a version tag from the package pages, for example `ghcr.io/luml-ai/luml-satellite-agent:v0.3.0` together with `ghcr.io/luml-ai/luml-model-server:v0.3.0`.

When a Satellite older than `v0.3.0` is updated, it relaunches each running model container once on its first start. Each container then moves to the Satellite's own network. Expect a short interruption of inference for those deployments.

### Several Satellites on one host

Several Satellites can share one Docker daemon. Give each Satellite its own token, its own published port and its own `BASE_URL`, for example by running each stack from its own directory with a different `name:` and port mapping. A Satellite manages only the containers it started and leaves containers of other Satellites alone.
