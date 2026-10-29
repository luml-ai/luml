# Docker satellite

This directory holds the Docker satellite. The satellite runs model deployments as containers
on one Docker daemon. `satellite/docker-compose.yml` starts a stand with the agent, the
telemetry collector and GreptimeDB.

## Agent access

The agent image runs as UID/GID `10001:10001`. Compose drops its Linux capabilities and
disables privilege escalation. It has no Docker socket mount and publishes no host port.

Only `docker-socket-proxy` mounts the Docker socket, read-only, and it publishes no host
port. The proxy allows the Docker API sections needed for deployment and cache cleanup:
containers, images, networks, volumes, ping and version. Writes are enabled for lifecycle
operations; other API sections, including exec, builds, secrets and swarm, are denied by
the proxy's defaults. The read-only mount does not make Docker API operations read-only.
The agent remains trusted with container creation and therefore with host-level Docker
capabilities; this proxy is not a sandbox for a compromised agent.

The proxy and agent share the internal `docker-control` network. It carries no
`df.model-access` label, so model containers never join it. Model containers continue to
join the satellite's workload and telemetry networks.

Caddy forwards HTTP requests to the agent, preserving authorization headers, paths and
streaming responses. By default it serves plain HTTP on `127.0.0.1:80` on the host, so
local access remains at `http://localhost`. Do not publish the agent's port or the Docker
API proxy. The GreptimeDB port is independent of the agent ingress.

### Remote access with automatic HTTPS

The host needs a DNS name that resolves to it and open ports 80 and 443. Set three values
in `satellite/.env` and run `docker compose up -d`:

```shell
SATELLITE_DOMAIN=sat.example.com
PROXY_BIND=0.0.0.0
BASE_URL=https://sat.example.com
```

Caddy obtains a Let's Encrypt certificate for that name, renews it, redirects port 80 to
HTTPS and keeps the certificate in the `caddy-data` volume across restarts. The agent
reports `BASE_URL` to the platform when it pairs on start-up. Check with
`curl https://sat.example.com/livez`. Existing remote installations must set these values
when upgrading.

Without `SATELLITE_DOMAIN` the proxy stays on plain HTTP, and without `PROXY_BIND` it stays
on the loopback interface. That default also suits a TLS proxy of your own on the host in
front of `http://127.0.0.1:80`; then set `BASE_URL` to that proxy's public URL instead.

## One network per satellite

The satellite creates its own Docker network on the first deployment. It names the network
`luml-satellite-<satellite id>`. The satellite joins it under two aliases:

1. `satellite-agent`
2. `satellite-agent-<satellite id>`

The satellite creates model containers in that network. It tells each model to reach it by the
second, satellite-specific name.

The satellite also connects each model container to its own networks that carry the Docker
network label `df.model-access=true`. Compose labels `satellite-network` this way so the
telemetry collector stays reachable by name. Unlabelled networks stay private to the agent.

GreptimeDB joins only the internal `store-network`, shared with the agent and collector.
Model containers cannot resolve or connect directly to the store, and the store publishes no
host ports. Set `GREPTIMEDB_USERNAME` and `GREPTIMEDB_PASSWORD` in `satellite/.env` before
starting Compose; both are required. Use a username without `,`, `=` or `:` and a generated
hexadecimal password, for example with `openssl rand -hex 32`. The store, agent and collector
use these credentials for Basic authentication.

### Use an existing network instead

Set `DOCKER_NETWORK_NAME` to the name of an existing network. In this mode:

1. The satellite creates no network.
2. The satellite refuses to start a deployment when the named network does not exist. It does
   not build a new bridge under a misspelled name.
3. Keep stores and other private services off this network. To let models reach an additional
   agent network (for example one with a collector), create it with `--label df.model-access=true`.
4. If Compose already attached the satellite to that network without the satellite-specific
   alias, models get its container name instead. That name resolves there in the same way.

## Model containers belong to their stack

A satellite that runs inside a Compose stack copies the stack's project label onto every model
container it creates. The models then appear next to their own satellite, collector and store
instead of as loose containers.

The label groups them. It does not hand them to Compose. With Compose v5.3, these commands
leave every model container running and print no warning:

1. `docker compose up`
2. `docker compose up --remove-orphans`
3. `docker compose down --remove-orphans`

The stack network then survives the teardown too, because a model container stays attached to
it. The model containers do carry Compose's project label. A Compose release that treats any
such container as an orphan would remove them. In both cases, follow this order:

1. Undeploy through the Platform. This removes the model containers.
2. Run `docker compose down`.

A satellite that upgrades onto launcher protocol 5 relaunches every model container of an older
launcher protocol once. This removes previously inherited private network attachments. Each
container then moves to the satellite's network and takes its address.

## Several satellites on one host

Several satellites can share one daemon. Each satellite is its own process with its own token.
The ownership rules in the repository root's spec apply:

1. A container carries the identity of the satellite that started it in `df.satellite_id`.
2. A satellite counts only its own containers as owned.
3. Orphan cleanup writes a log line for every foreign container and leaves it alone.

Give each satellite its own Compose project, reverse-proxy port and token. For example,
create `satellite/compose.second.yml` to replace the second stack's HTTP port:

```yaml
services:
  reverse-proxy:
    ports: !override
      - "127.0.0.1:8081:80"
  greptimedb:
    ports: !override []
```

With Docker Compose 2.24.4 or newer, start that stack from `satellite/`:

```shell
SATELLITE_TOKEN="$SECOND_TOKEN" BASE_URL=http://localhost:8081 \
  docker compose -p satellite-two -f docker-compose.yml -f compose.second.yml up -d
```

The model containers of different satellites stay apart, because each satellite addresses its
own network. The satellite-specific alias also lets a model reach its own satellite when two
satellites share a network.
