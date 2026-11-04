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

The stack below starts five services next to each other:

| Service | Role |
|---|---|
| `agent` | The Satellite. Runs as an unprivileged user and publishes no port of its own. |
| `reverse-proxy` | Caddy in front of the agent. It is the only service with host ports. |
| `docker-socket-proxy` | The only service that mounts the Docker socket. The agent talks to Docker through it. |
| `greptimedb` | Stores inference events and monitoring results. It sits on an internal network and is protected by a password. |
| `otel-collector` | Receives traces from the agent and the model containers and writes them to GreptimeDB. |

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
    labels:
      df.model-access: "true"
  store-network:
    driver: bridge
    internal: true
  docker-control:
    driver: bridge
    internal: true

volumes:
  greptimedb-data:
  caddy-data:
  caddy-config:

services:
  agent:
    image: ghcr.io/luml-ai/luml-satellite-agent:latest
    networks:
      satellite-network:
        aliases:
          - satellite-agent
      store-network:
      docker-control:
    environment:
      DOCKER_HOST: tcp://docker-socket-proxy:2375
      SATELLITE_TOKEN: ${SATELLITE_TOKEN:?Set SATELLITE_TOKEN in .env}
      PLATFORM_URL: ${PLATFORM_URL:-https://api.luml.ai}
      BASE_URL: ${BASE_URL:-http://localhost}
      MODEL_IMAGE: ${MODEL_IMAGE:-ghcr.io/luml-ai/luml-model-server:latest}
      POLL_INTERVAL_SEC: ${POLL_INTERVAL_SEC:-2}
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4317
      MONITORING_ENABLED: "true"
      MONITORING_FRAME_ANCESTORS: ${MONITORING_FRAME_ANCESTORS:-https://app.luml.ai}
      GREPTIMEDB_HOST: greptimedb
      GREPTIMEDB_USERNAME: ${GREPTIMEDB_USERNAME:?Set GREPTIMEDB_USERNAME in .env}
      GREPTIMEDB_PASSWORD: ${GREPTIMEDB_PASSWORD:?Set GREPTIMEDB_PASSWORD in .env}
    user: "10001:10001"
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
    extra_hosts:
      - "host.docker.internal:host-gateway"
    depends_on:
      - docker-socket-proxy
      - model-server
      - otel-collector
    restart: unless-stopped

  reverse-proxy:
    image: caddy:2.10.2-alpine
    networks:
      - satellite-network
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
      - caddy-config:/config
    environment:
      SATELLITE_SITE: ${SATELLITE_DOMAIN:-:80}
    ports:
      - "${PROXY_BIND:-127.0.0.1}:80:80"
      - "${PROXY_BIND:-127.0.0.1}:443:443"
    depends_on:
      - agent
    restart: unless-stopped

  docker-socket-proxy:
    image: tecnativa/docker-socket-proxy:v0.5.0
    networks:
      - docker-control
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      CONTAINERS: "1"
      IMAGES: "1"
      NETWORKS: "1"
      VOLUMES: "1"
      POST: "1"
      PING: "1"
      VERSION: "1"
      EVENTS: "0"
    restart: unless-stopped

  model-server:
    image: ghcr.io/luml-ai/luml-model-server:latest
    platform: linux/amd64
    command: ["true"]
    restart: "no"

  greptimedb:
    image: greptime/greptimedb:v0.13.1
    command:
      - standalone
      - start
      - --http-addr=0.0.0.0:4000
      - --rpc-addr=0.0.0.0:4001
      - "--user-provider=static_user_provider:cmd:${GREPTIMEDB_USERNAME:?Set GREPTIMEDB_USERNAME in .env}=${GREPTIMEDB_PASSWORD:?Set GREPTIMEDB_PASSWORD in .env}"
    networks:
      - store-network
    volumes:
      - greptimedb-data:/tmp/greptimedb
    restart: unless-stopped

  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.127.0
    command: ["--config=/etc/otel/config.yaml"]
    networks:
      - satellite-network
      - store-network
    environment:
      GREPTIMEDB_USERNAME: ${GREPTIMEDB_USERNAME:?Set GREPTIMEDB_USERNAME in .env}
      GREPTIMEDB_PASSWORD: ${GREPTIMEDB_PASSWORD:?Set GREPTIMEDB_PASSWORD in .env}
    volumes:
      - ./otel-collector-config.yaml:/etc/otel/config.yaml:ro
    depends_on:
      - greptimedb
    restart: unless-stopped
```

The top-level `name: satellite` pins the Compose project name, so the networks and containers are prefixed with `satellite_` regardless of what the working directory is called. The `model-server` service only pulls the model image ahead of time and exits.

The three networks keep the services apart:

- `satellite-network` carries the label `df.model-access: "true"`. The Satellite connects model containers only to its networks with this label, so models can reach the collector by name.
- `store-network` is internal. Only the agent, the collector and GreptimeDB join it, so model containers cannot reach the store.
- `docker-control` is internal and unlabelled. Only the agent and the Docker socket proxy join it, so model containers never reach the Docker API.

The socket proxy allows the Docker API sections the Satellite needs: containers, images, networks, volumes, ping and version. It denies the rest, including exec, builds, secrets and swarm. The agent can still create containers, so treat it as trusted with the host's Docker.

**3. Create `Caddyfile`** in the same directory:

```text
{
	servers {
		protocols h1 h2
	}
}

{$SATELLITE_SITE} {
	reverse_proxy agent:8000 {
		flush_interval -1
	}
}
```

`flush_interval -1` passes streamed inference responses through without buffering.

**4. Create `otel-collector-config.yaml`** in the same directory:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: "0.0.0.0:4317"

extensions:
  basicauth/client:
    client_auth:
      username: ${env:GREPTIMEDB_USERNAME}
      password: ${env:GREPTIMEDB_PASSWORD}

exporters:
  otlphttp/traces:
    endpoint: "http://greptimedb:4000/v1/otlp"
    tls:
      insecure: true
    auth:
      authenticator: basicauth/client
    headers:
      x-greptime-db-name: public
      x-greptime-trace-table-name: otel_traces

  otlphttp/events:
    endpoint: "http://greptimedb:4000/v1/otlp"
    tls:
      insecure: true
    auth:
      authenticator: basicauth/client
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
  extensions: [basicauth/client]
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

**5. Create `.env`** in the same directory. Paste the token from the previous step into `SATELLITE_TOKEN` and generate a password for GreptimeDB, for example with `openssl rand -hex 32`:

```env
# Required: token issued by the platform
SATELLITE_TOKEN=replace-with-your-token

# Required: credentials of the local monitoring store, shared by the agent and the collector
GREPTIMEDB_USERNAME=monitoring
GREPTIMEDB_PASSWORD=replace-with-a-generated-password

# Public base URL of the Satellite (used to report inference endpoints)
BASE_URL=http://localhost
```

| Variable | Default | Meaning |
|---|---|---|
| `SATELLITE_TOKEN` | — | Token issued by Luml. Required. |
| `GREPTIMEDB_USERNAME` | — | User of the local GreptimeDB. Required. Do not use `,`, `=` or `:` in it. |
| `GREPTIMEDB_PASSWORD` | — | Password of the local GreptimeDB. Required. Use a generated hexadecimal value. |
| `BASE_URL` | `http://localhost` | Address other services use to reach the Satellite. Inference endpoints and the monitoring dashboard are published under it. |
| `SATELLITE_DOMAIN` | — | DNS name of the host. When set, the proxy serves HTTPS with a Let's Encrypt certificate. |
| `PROXY_BIND` | `127.0.0.1` | Host interface the proxy listens on. Set `0.0.0.0` to accept connections from other machines. |
| `PLATFORM_URL` | `https://api.luml.ai` | Luml API the Satellite pairs with. |
| `MODEL_IMAGE` | `ghcr.io/luml-ai/luml-model-server:latest` | Image model containers start from. |
| `MONITORING_FRAME_ANCESTORS` | `https://app.luml.ai` | Origins allowed to embed the monitoring dashboard, separated by spaces. |
| `POLL_INTERVAL_SEC` | `2` | How often the Satellite polls Luml for tasks, in seconds. |

**6. Launch the Satellite:**

```bash
docker compose up -d
```

Compose pulls the images and starts the containers in the background. The Satellite connects to Luml using the token, registers its capabilities, and begins polling for tasks. To confirm it is online, return to the **Satellites** module in Luml — the Satellite's status should switch to *Connected*. On the host, `curl http://localhost/livez` answers through the proxy.

On the first deployment the Satellite creates its own Docker network, `luml-satellite-<satellite id>`, and starts model containers in it.

To check the Satellite's logs or stop it later:

```bash
docker compose logs -f agent   # follow the Satellite's logs
docker compose down            # stop and remove the containers
```

Undeploy models through Luml before you run `docker compose down`. Model containers are started by the Satellite, not by Compose, and keep running after the stack stops.

### Reach the Satellite from other machines

By default the proxy serves plain HTTP on `127.0.0.1:80`, so the Satellite answers only on the host itself. For remote access with automatic HTTPS, the host needs a DNS name that resolves to it and open ports 80 and 443. Set three values in `.env` and run `docker compose up -d`:

```env
SATELLITE_DOMAIN=sat.example.com
PROXY_BIND=0.0.0.0
BASE_URL=https://sat.example.com
```

Caddy obtains a certificate for that name, renews it, redirects port 80 to HTTPS and keeps the certificate in the `caddy-data` volume. The Satellite reports `BASE_URL` to Luml when it pairs on start-up. Check the setup with `curl https://sat.example.com/livez`.

To put a TLS proxy of your own in front of the Satellite instead, leave `SATELLITE_DOMAIN` and `PROXY_BIND` unset, point your proxy at `http://127.0.0.1:80` and set `BASE_URL` to your proxy's public URL. Do not publish the agent's port or the Docker socket proxy.

### Update the Satellite

The images are tagged `latest`, so an update is a pull and a restart:

```bash
docker compose pull
docker compose up -d
```

To stay on a fixed release, replace `latest` with a version tag from the package pages, for example `ghcr.io/luml-ai/luml-satellite-agent:v0.4.0` together with `ghcr.io/luml-ai/luml-model-server:v0.4.0`.

Starting with `v0.4.0`, the model server rejects request bodies larger than 16 MiB with `413 Request body too large`.

### Upgrade from a Satellite older than v0.4.0

`v0.4.0` changes the stack, not only the images. A pull alone keeps the old Compose file: the new agent starts, but model containers no longer join the unlabelled `satellite-network` and their traces stop reaching the collector. Replace the configuration files as well:

1. Replace `docker-compose.yml` and `otel-collector-config.yaml` with the versions above and create the `Caddyfile`.
2. Add `GREPTIMEDB_USERNAME` and `GREPTIMEDB_PASSWORD` to `.env`. The existing GreptimeDB data stays in its volume.
3. If other machines reached the Satellite on port 80 before, the new proxy serves only `127.0.0.1` by default. Set `SATELLITE_DOMAIN`, `PROXY_BIND` and `BASE_URL` as described in [Reach the Satellite from other machines](#reach-the-satellite-from-other-machines). To keep plain HTTP on all interfaces, set only `PROXY_BIND=0.0.0.0`.
4. Detach running model containers from the old stack network. Compose recreates `satellite-network` to add its label and cannot remove a network that model containers are still attached to:

   ```bash
   for c in $(docker ps -q --filter label=df.satellite_id --filter network=satellite_satellite-network); do
     docker network disconnect satellite_satellite-network "$c"
   done
   ```

   If the stack runs under another project name, replace `satellite_` with that name and an underscore.

5. Restart the stack on the new configuration:

   ```bash
   docker compose pull
   docker compose down
   docker compose up -d
   ```

The models keep running in the Satellite's own network during these steps. On its first start the new Satellite relaunches each model container once and connects it only to the networks labelled `df.model-access`. Expect a short interruption of inference for each deployment.

### Several Satellites on one host

Several Satellites can share one Docker daemon. Give each Satellite its own token, its own Compose project, its own proxy port and its own `BASE_URL`. For example, run the second stack from its own directory with `name: satellite-two` and change the proxy ports:

```yaml
  reverse-proxy:
    ports:
      - "127.0.0.1:8081:80"
```

Then set `BASE_URL=http://localhost:8081` in that stack's `.env`. A Satellite manages only the containers it started and leaves containers of other Satellites alone.
