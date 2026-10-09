# Docker satellite

This directory holds the Docker satellite. The satellite runs model deployments as containers
on one Docker daemon. `satellite/docker-compose.yml` starts a stand with the agent, the
telemetry collector and GreptimeDB.

## One network per satellite

The satellite creates its own Docker network on the first deployment. It names the network
`luml-satellite-<satellite id>`. The satellite joins it under two aliases:

1. `satellite-agent`
2. `satellite-agent-<satellite id>`

The satellite creates model containers in that network. It tells each model to reach it by the
second, satellite-specific name.

The satellite also connects each model container to the networks it belongs to itself. The
telemetry collector of its stack therefore stays reachable by name.

### Use an existing network instead

Set `DOCKER_NETWORK_NAME` to the name of an existing network. In this mode:

1. The satellite creates no network.
2. The satellite refuses to start a deployment when the named network does not exist. It does
   not build a new bridge under a misspelled name.
3. If Compose already attached the satellite to that network without the satellite-specific
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

A satellite that upgrades onto this behaviour relaunches every model container of the previous
launcher protocol once. Each container then moves to the satellite's network and takes its
address.

## Several satellites on one host

Several satellites can share one daemon. Each satellite is its own process with its own token.
The ownership rules in the repository root's spec apply:

1. A container carries the identity of the satellite that started it in `df.satellite_id`.
2. A satellite counts only its own containers as owned.
3. Orphan cleanup writes a log line for every foreign container and leaves it alone.

Give each satellite its own published port and its own token:

```shell
docker run -d --name agent-one \
  --network my-stack_satellite-network \
  --publish 8081:8000 \
  --volume /var/run/docker.sock:/var/run/docker.sock \
  --env SATELLITE_TOKEN="$FIRST_TOKEN" \
  --env PLATFORM_URL=https://api.luml.ai \
  --env BASE_URL=http://localhost:8081 \
  luml-satellite-agent:latest
```

The model containers of different satellites stay apart, because each satellite addresses its
own network. The satellite-specific alias also lets a model reach its own satellite when two
satellites share a network.
